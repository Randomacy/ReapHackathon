"""Experimental, individual-baseline EEG engagement heuristic."""

from collections import deque
from dataclasses import dataclass
import math
import statistics
import time

import numpy as np
from scipy.signal import welch


@dataclass(frozen=True)
class Estimate:
    state: str
    score: float | None
    quality: str
    sustained_for_ms: int
    connection: str


class FocusEstimator:
    """Consume four-channel, 256 Hz OSC EEG and optional accelerometer packets.

    beta/(alpha+theta) follows the reference classifier's feature. The
    baseline-relative score and decision thresholds are demo heuristics, not
    a validated measure of attention, fatigue, or medical state.
    """

    def __init__(self, baseline_seconds=30.0, dip_seconds=30.0,
                 dip_score=0.35, sample_rate=256):
        self.baseline_seconds = baseline_seconds
        self.dip_seconds = dip_seconds
        self.dip_score = dip_score
        self.sample_rate = sample_rate
        self.samples = deque(maxlen=sample_rate * 4)
        self.times = deque(maxlen=sample_rate * 4)
        self.last_eeg_at = None
        self.last_acc_at = None
        self.last_acc = None
        self.baseline_values = []
        self.baseline_started = None
        self.baseline = None
        self.dip_since = None
        self.recovery_since = None
        self.episode_fired = False
        self.last_state = "unknown"

    def ingest_eeg(self, values, now=None):
        now = time.monotonic() if now is None else now
        if len(values) != 4 or not all(math.isfinite(v) for v in values):
            self._clear_signal()
            return
        self.samples.append(tuple(float(v) for v in values))
        self.times.append(now)
        self.last_eeg_at = now

    def ingest_acc(self, values, now=None):
        now = time.monotonic() if now is None else now
        if len(values) == 3 and all(math.isfinite(v) for v in values):
            self.last_acc = tuple(float(v) for v in values)
            self.last_acc_at = now

    def _clear_signal(self):
        self.samples.clear()
        self.times.clear()
        self.last_eeg_at = None
        self.baseline_values.clear()
        self.baseline_started = None
        self.baseline = None
        self.dip_since = None
        self.recovery_since = None
        self.last_state = "unknown"

    def _unknown(self, quality, connection):
        self.dip_since = None
        self.recovery_since = None
        self.last_state = "unknown"
        return Estimate("unknown", None, quality, 0, connection)

    def evaluate(self, now=None):
        now = time.monotonic() if now is None else now
        if self.last_eeg_at is None or now - self.last_eeg_at > 2.0:
            self._clear_signal()
            return self._unknown("disconnected", "disconnected")
        if len(self.samples) < self.sample_rate * 4:
            return self._unknown("poor", "connected")

        data = np.asarray(self.samples, dtype=float)
        duration = self.times[-1] - self.times[0]
        if duration < 3.7 or duration > 4.3 or np.max(np.abs(data)) > 1000:
            return self._unknown("poor", "connected")
        if np.any(np.std(data, axis=0) < 0.5):
            return self._unknown("poor", "connected")
        if self.last_acc_at is not None and now - self.last_acc_at < 2:
            # Large acceleration is a likely motion artifact.
            if np.linalg.norm(self.last_acc) > 1.8:
                return self._unknown("poor", "connected")

        freqs, psd = welch(data.T, fs=self.sample_rate, nperseg=256,
                           noverlap=128, detrend="constant")
        def power(lo, hi):
            band = (freqs >= lo) & (freqs < hi)
            return float(np.mean(psd[:, band]))
        ratio = power(13, 30) / max(power(4, 8) + power(8, 13), 1e-12)
        if not math.isfinite(ratio):
            return self._unknown("poor", "connected")

        if self.baseline is None:
            if self.baseline_started is None:
                self.baseline_started = now
            self.baseline_values.append(ratio)
            if now - self.baseline_started < self.baseline_seconds:
                return self._unknown("poor", "connected")
            self.baseline = max(statistics.median(self.baseline_values), 1e-6)
            self.baseline_values.clear()

        score = round(min(1.0, max(0.0, ratio / (2 * self.baseline))), 4)
        if score < self.dip_score:
            self.recovery_since = None
            if self.dip_since is None:
                self.dip_since = now
            sustained = int((now - self.dip_since) * 1000)
            if sustained >= self.dip_seconds * 1000 and not self.episode_fired:
                self.episode_fired = True
                self.last_state = "focus_dip"
                return Estimate("focus_dip", score, "good", sustained, "connected")
            # Continue reporting the dip episode, but publish it once.
            if self.last_state == "focus_dip":
                return Estimate("focus_dip", score, "good", sustained, "connected")
            self.last_state = "unknown"
            return Estimate("unknown", score, "good", sustained, "connected")

        self.dip_since = None
        if score >= max(self.dip_score + 0.1, 0.45):
            if self.recovery_since is None:
                self.recovery_since = now
            if now - self.recovery_since >= 5:
                self.episode_fired = False
                self.last_state = "focused"
                return Estimate("focused", score, "good", 0, "connected")
        else:
            self.recovery_since = None
        self.last_state = "unknown"
        return Estimate("unknown", score, "good", 0, "connected")
