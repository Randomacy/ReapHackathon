#include "osc_sender.h"

#define WIN32_LEAN_AND_MEAN
#include <stdlib.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <cstring>
#include <cstdint>

#pragma comment(lib, "ws2_32.lib")

static SOCKET g_sock = INVALID_SOCKET;
static sockaddr_in g_addr = {};

// Pad length up to next 4-byte boundary
static int pad4(int len) {
    return (len + 3) & ~3;
}

// Swap bytes for big-endian float encoding
static uint32_t float_to_be(float f) {
    uint32_t bits;
    memcpy(&bits, &f, 4);
    return _byteswap_ulong(bits);
}

bool osc_init(const char* ip, int port) {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return false;

    g_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (g_sock == INVALID_SOCKET) return false;

    g_addr.sin_family = AF_INET;
    g_addr.sin_port = htons((u_short)port);
    inet_pton(AF_INET, ip, &g_addr.sin_addr);
    return true;
}

void osc_send(const char* address, const float* values, int count) {
    if (g_sock == INVALID_SOCKET) return;

    // Build type tag string: ,fff...
    char type_tag[32] = ",";
    for (int i = 0; i < count && i < 30; ++i) type_tag[1 + i] = 'f';
    type_tag[1 + count] = '\0';

    int addr_len   = pad4((int)strlen(address) + 1);
    int tag_len    = pad4((int)strlen(type_tag) + 1);
    int floats_len = count * 4;
    int total      = addr_len + tag_len + floats_len;

    char buf[512] = {};
    int offset = 0;

    strncpy_s(buf + offset, sizeof(buf) - offset, address, addr_len);
    offset += addr_len;

    strncpy_s(buf + offset, sizeof(buf) - offset, type_tag, tag_len);
    offset += tag_len;

    for (int i = 0; i < count; ++i) {
        uint32_t be = float_to_be(values[i]);
        memcpy(buf + offset, &be, 4);
        offset += 4;
    }

    sendto(g_sock, buf, total, 0, (sockaddr*)&g_addr, sizeof(g_addr));
}

void osc_close() {
    if (g_sock != INVALID_SOCKET) {
        closesocket(g_sock);
        g_sock = INVALID_SOCKET;
    }
    WSACleanup();
}
