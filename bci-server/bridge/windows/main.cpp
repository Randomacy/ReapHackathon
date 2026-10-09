#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <cstdio>
#include <atomic>
#include <memory>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <cstring>

#include "muse.h"
#include "api/muse_manager_windows.h"
#include "osc_sender.h"

using namespace interaxon::bridge;

static std::atomic<bool> g_quit{ false };

// ---- Producer-consumer queue so callbacks return immediately ----

struct OscPacket {
    char  address[32];
    float values[6];
    int   count;
};

static std::queue<OscPacket>    g_queue;
static std::mutex               g_mutex;
static std::condition_variable  g_cv;

static void sender_thread_fn() {
    while (true) {
        OscPacket pkt;
        {
            std::unique_lock<std::mutex> lk(g_mutex);
            g_cv.wait(lk, [] { return !g_queue.empty() || g_quit.load(); });
            if (g_queue.empty()) break;   // quit and queue drained
            pkt = g_queue.front();
            g_queue.pop();
        }
        osc_send(pkt.address, pkt.values, pkt.count);
    }
    // drain any remaining packets before exit
    std::unique_lock<std::mutex> lk(g_mutex);
    while (!g_queue.empty()) {
        OscPacket pkt = g_queue.front(); g_queue.pop();
        lk.unlock();
        osc_send(pkt.address, pkt.values, pkt.count);
        lk.lock();
    }
}

static void enqueue(const char* address, const float* vals, int count) {
    OscPacket pkt;
    strncpy_s(pkt.address, address, sizeof(pkt.address) - 1);
    pkt.address[sizeof(pkt.address) - 1] = '\0';
    memcpy(pkt.values, vals, count * sizeof(float));
    pkt.count = count;
    {
        std::lock_guard<std::mutex> lk(g_mutex);
        g_queue.push(pkt);
    }
    g_cv.notify_one();
}

BOOL WINAPI ctrl_handler(DWORD type) {
    if (type == CTRL_C_EVENT || type == CTRL_BREAK_EVENT) {
        printf("\nShutting down...\n");
        g_quit.store(true);
        g_cv.notify_all();
        return TRUE;
    }
    return FALSE;
}

// ---- Listener implementations ----

class MyMuseListener : public MuseListener {
public:
    void muse_list_changed() override {}
};

// The preset to request. Kept as one constant so the request and the
// diagnostic below cannot disagree.
//
// PRESET_21 = 4 CH EEG @ 256 Hz + 52 Hz accel/gyro + 32 Hz DRL/REF.
//
// Do NOT retry a 5 CH preset on this headband (MU-06, Muse 2 2024, USB-C).
// Measured 2026-10-02: PRESET_20 and PRESET_50 are both listed as available
// for muse2024 and both were genuinely accepted -- p20/p50 returned rc:0,
// get_preset() echoed the request, and the status ps field tracked it
// (0x51 default -> 0x20 -> 0x50). Even so, get_eeg_channel_count() stayed at
// 4 and AUX_LEFT came through as NaN for 0 of 2556 samples. MU-06 has no
// analog AUX line on its USB-C port, unlike the older micro-USB models.
// Preset acceptance is not evidence that a channel exists.
static const MusePreset kRequestedPreset = MusePreset::PRESET_21;
static const char* const kRequestedPresetName = "PRESET_21";

// Reports what the headband actually negotiated, as opposed to what we asked
// for. An invalid preset is ignored with only a log warning, and even an
// accepted one may not deliver the extra channel -- the channel count is the
// ground truth.
static void print_negotiated_config(const std::shared_ptr<Muse>& muse) {
    auto cfg = muse->get_muse_configuration();
    if (!cfg) {
        printf("[Config] Unavailable.\n");
        return;
    }
    const char* model = "unknown";
    switch (cfg->get_model()) {
        case MuseModel::MU_01: model = "MU-01 (Muse 2014)";        break;
        case MuseModel::MU_02: model = "MU-02 (Muse 2016)";        break;
        case MuseModel::MU_03: model = "MU-03 (Muse 2 / 2018)";    break;
        case MuseModel::MU_04: model = "MU-04 (Muse S 2019)";      break;
        case MuseModel::MU_05: model = "MU-05 (Muse S 2021)";      break;
        case MuseModel::MU_06: model = "MU-06 (Muse 2 2024)";      break;
        case MuseModel::MS_03: model = "MS-03 (Muse S 2025)";      break;
        default: break;
    }
    printf("[Config] Model: %s\n", model);
    printf("[Config] Preset in effect: %d  (requested %s = %d)\n",
           (int)cfg->get_preset(), kRequestedPresetName, (int)kRequestedPreset);
    printf("[Config] EEG channel count: %d\n", cfg->get_eeg_channel_count());
    if (cfg->get_preset() != kRequestedPreset) {
        printf("[Config] >> Preset differs from the request -- the headband\n");
        printf("[Config] >> rejected it and kept its own.\n");
    }
}

class MyConnectionListener : public MuseConnectionListener {
public:
    void receive_muse_connection_packet(const MuseConnectionPacket& packet,
                                        const std::shared_ptr<Muse>& muse) override {
        switch (packet.current_connection_state) {
            case ConnectionState::CONNECTING:    printf("[Status] Connecting...\n");   break;
            case ConnectionState::CONNECTED:     printf("[Status] Connected!\n");
                                                 print_negotiated_config(muse);        break;
            case ConnectionState::DISCONNECTED:  printf("[Status] Disconnected.\n");
                                                 g_quit.store(true);
                                                 g_cv.notify_all();                    break;
            case ConnectionState::NEEDS_UPDATE:  printf("[Status] Firmware update required.\n"); break;
            default: break;
        }
    }
};

class MyDataListener : public MuseDataListener {
public:
    void receive_muse_data_packet(const std::shared_ptr<MuseDataPacket>& packet,
                                  const std::shared_ptr<Muse>&) override {
        switch (packet->packet_type()) {
            case MuseDataPacketType::EEG: {
                // 4 channels only. AUX_LEFT is deliberately not sent: this
                // headband never samples it (see kRequestedPreset), so it
                // would be a NaN that propagates silently through the Python
                // filter chain.
                float vals[4] = {
                    (float)packet->get_eeg_channel_value(Eeg::EEG1),
                    (float)packet->get_eeg_channel_value(Eeg::EEG2),
                    (float)packet->get_eeg_channel_value(Eeg::EEG3),
                    (float)packet->get_eeg_channel_value(Eeg::EEG4),
                };
                enqueue("/muse/eeg", vals, 4);
                break;
            }
            case MuseDataPacketType::ACCELEROMETER: {
                float vals[3] = {
                    (float)packet->get_accelerometer_value(Accelerometer::X),
                    (float)packet->get_accelerometer_value(Accelerometer::Y),
                    (float)packet->get_accelerometer_value(Accelerometer::Z),
                };
                enqueue("/muse/acc", vals, 3);
                break;
            }
            default: break;
        }
    }

    void receive_muse_artifact_packet(const MuseArtifactPacket&,
                                      const std::shared_ptr<Muse>&) override {}
};

int main() {
    printf("Muse 2 OSC Bridge\n");
    printf("Streaming EEG 4ch -> /muse/eeg  |  Accel -> /muse/acc  |  127.0.0.1:7000\n");
    printf("EEG channel order: TP9, AF7, AF8, TP10\n\n");

    CoInitializeEx(NULL, COINIT_MULTITHREADED);

    if (!osc_init("127.0.0.1", 7000)) {
        printf("[Error] Failed to open UDP socket.\n");
        return 1;
    }

    std::thread sender(sender_thread_fn);

    SetConsoleCtrlHandler(ctrl_handler, TRUE);

    auto muse_listener = std::make_shared<MyMuseListener>();
    auto conn_listener = std::make_shared<MyConnectionListener>();
    auto data_listener = std::make_shared<MyDataListener>();

    auto manager = MuseManagerWindows::get_instance();
    manager->set_muse_listener(muse_listener);
    manager->remove_from_list_after(0);

    printf("[Scan] Searching for Muse devices (make sure headband is on)...\n");
    manager->start_listening();

    while (!g_quit.load()) {
        auto muses = manager->get_muses();
        if (!muses.empty()) {
            auto muse = muses[0];
            printf("[Found] %s\n", muse->get_name().c_str());
            manager->stop_listening();

            muse->register_connection_listener(conn_listener);
            muse->register_data_listener(data_listener, MuseDataPacketType::EEG);
            muse->register_data_listener(data_listener, MuseDataPacketType::ACCELEROMETER);
            // See kRequestedPreset above. PPG packets that PRESET_50 enables
            // are simply never listened for, so they cost nothing here.
            muse->set_preset(kRequestedPreset);
            muse->run_asynchronously();
            muse->connect();

            while (!g_quit.load()) Sleep(100);

            muse->disconnect();
            Sleep(500);
            break;
        }
        Sleep(200);
    }

    g_quit.store(true);
    g_cv.notify_all();
    sender.join();

    osc_close();
    CoUninitialize();
    return 0;
}
