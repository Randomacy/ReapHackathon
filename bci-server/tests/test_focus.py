import math

from src.focus import FocusEstimator


def feed(estimator, start, seconds, beta_amplitude, alpha_amplitude,
         offsets=(0, 0, 0, 0)):
    fs = estimator.sample_rate
    for index in range(int(seconds * fs)):
        t = start + index / fs
        beta = beta_amplitude * math.sin(2 * math.pi * 18 * t)
        alpha = alpha_amplitude * math.sin(2 * math.pi * 10 * t)
        estimator.ingest_eeg([offset + beta + alpha for offset in offsets], t)
        if index % (fs // 2) == 0:
            estimator.ingest_acc([0, 0, 1], t)
            result = estimator.evaluate(t)
    return result


def test_sustained_dip_needs_baseline_and_recovery():
    estimator = FocusEstimator(baseline_seconds=1, dip_seconds=2)
    assert feed(estimator, 0, 4, 3, 1).state == "unknown"
    assert feed(estimator, 4, 8, 3, 1).state == "focused"
    assert feed(estimator, 12, 1, 0.2, 3).state != "focus_dip"
    assert feed(estimator, 13, 8, 0.2, 3).state == "focus_dip"
    assert estimator.episode_fired
    assert feed(estimator, 21, 10, 3, 1).state == "focused"
    assert not estimator.episode_fired


def test_dropout_clears_baseline_and_cannot_trigger_dip():
    estimator = FocusEstimator(baseline_seconds=1, dip_seconds=2)
    feed(estimator, 0, 7, 3, 1)
    disconnected = estimator.evaluate(10)
    assert disconnected.state == "unknown"
    assert disconnected.quality == "disconnected"
    assert estimator.baseline is None
    assert estimator.diagnostics(10)["quality_reason"] == "No recent EEG packets."


def test_nonfinite_or_flat_signal_is_poor_quality():
    estimator = FocusEstimator(baseline_seconds=1, dip_seconds=2)
    estimator.ingest_eeg([float("nan")] * 4, 0)
    assert estimator.evaluate(0).state == "unknown"
    result = feed(estimator, 1, 5, 0, 0)
    assert result.state == "unknown"
    assert result.quality == "poor"
    assert "flat EEG channel" in estimator.diagnostics(6)["quality_reason"]


def test_diagnostics_include_bands_and_bounded_local_trace():
    estimator = FocusEstimator(baseline_seconds=1, dip_seconds=2)
    feed(estimator, 0, 7, 3, 1)
    diagnostics = estimator.diagnostics(now=7)
    assert diagnostics["channel_names"] == ["TP9", "AF7", "AF8", "TP10"]
    assert len(diagnostics["eeg"]) == 4
    assert all(0 < len(channel) <= 240 for channel in diagnostics["eeg"])
    assert diagnostics["sample_rate_hz"] == 256.0
    assert diagnostics["baseline_progress"] == 1.0
    assert set(diagnostics["band_powers"]) == {"theta", "alpha", "beta"}
    assert diagnostics["engagement_ratio"] > 0


def test_muse_dc_offset_does_not_hide_focus_feature():
    estimator = FocusEstimator(baseline_seconds=30)
    result = feed(estimator, 0, 7, 3, 1, offsets=(700, 1100, 800, 900))
    diagnostics = estimator.diagnostics(now=7)
    assert result.quality == "good"
    assert result.score is None  # The Tempo event waits for individual calibration.
    assert diagnostics["engagement_ratio"] > 0.20
    assert diagnostics["reference_state"] == "focused"
    assert diagnostics["band_powers"]["beta"] > 0
    assert diagnostics["baseline_progress"] > 0
