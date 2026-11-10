"""Online control of avoidable stalls in a trace-driven video player.

A throughput estimate is discounted by a safety margin, estimate * exp(-margin), and the
margin is updated after every downloaded segment by

    margin <- max(floor, margin + step * (loss - limit)),

where loss is a signal in [0, 1] observed by the player and limit is the long-run level
requested for that signal. The signal `stall_time` is the part of the stall of the
segment that the lowest representation would not have caused, as a fraction of the
segment duration. The player can compute it after a download because the lowest
representation is smaller than the one requested, so its download would have finished
inside the observed transfer.

The player loop follows src.has.simulate (same request, download, buffer and metric
rules); tests/test_stall_control.py checks that the two agree when the margin is zero.

Units: time in s, segment sizes in Mbit inside the simulator, rates in Mbit/s.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field

import numpy as np

from src.has import (BUFFER_S, FLOOR_MBPS, HORIZON, LATENCY_S, METRIC_KEYS, RULES, SEGMENT_S,
                     WINDOW, _empty_metrics, download_finish, harmonic_mean, mpc_choice)

SIGNALS = ("stall_time", "stall_event", "overestimate")
CONTROL_KEYS = ("n_decisions", "stall_time_fraction", "stall_event_fraction",
                "overestimate_fraction", "control_loss_mean", "margin_mean", "margin_final",
                "margin_max", "avoidable_s")
RADIO_COLUMNS = ("RSRP", "RSRQ", "SNR", "CQI", "RSSI", "Speed", "is_5g_mode")
N_HISTORY_FEATURES = 5
ALL_RULES = (*RULES, "bba", "bola")
BBA_RESERVOIR_S = 5.0
BBA_CUSHION_S = 10.0
BOLA_GAMMA_P = 5.0
LUMOS_UNAVAILABLE = 1e6


@dataclass
class MarginController:
    """Safety margin updated from a signal observed after each segment.

    limit is the requested long-run level of the signal, step the update size and floor
    the smallest margin allowed.
    """
    limit: float
    step: float
    floor: float = -math.inf
    signal: str = "stall_time"
    margin: float = 0.0
    start: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.signal not in SIGNALS:
            raise ValueError(f"unknown signal {self.signal}")
        if not 0.0 < self.limit < 1.0:
            raise ValueError("limit must lie in (0, 1)")
        if self.step <= 0.0:
            raise ValueError("step must be positive")
        self.start = self.margin

    def update(self, loss: float) -> None:
        """Apply one update with the observed signal value."""
        self.margin = max(self.floor, self.margin + self.step * (loss - self.limit))


class HarmonicMean:
    """Harmonic mean of the last WINDOW segment throughputs."""

    def estimate(self, second: int, tputs: list) -> float:
        return harmonic_mean(tputs[-WINDOW:])


class RobustDiscount:
    """base estimate / (1 + largest relative error of its last WINDOW estimates).

    With base = HarmonicMean() this is the RobustMPC estimate of Yin et al. (2015).
    """

    def __init__(self, base):
        self.base = base
        self.hist: list = []
        self.errs: list = []

    def estimate(self, second: int, tputs: list) -> float:
        value = self.base.estimate(second, tputs)
        if self.hist:
            self.errs.append(abs(self.hist[-1] - tputs[-1]) / tputs[-1])
        max_err = max(self.errs[-WINDOW:]) if self.errs else 0.0
        self.hist.append(value)
        return value / (1.0 + max_err)


class External:
    """Per-second external estimates; NaN seconds use the most recent earlier value."""

    def __init__(self, values):
        v = np.asarray(values, dtype=float)
        idx = np.maximum.accumulate(np.where(np.isnan(v), -1, np.arange(len(v))))
        self.values = np.where(idx >= 0, v[np.maximum(idx, 0)], np.nan).tolist()

    def estimate(self, second: int, tputs: list) -> float:
        return self.values[second]


def segment_features(tputs: list, radio_row) -> np.ndarray:
    """Features of a request: recent segment throughputs and the current radio readings.

    tputs are the throughputs of the segments already downloaded, and radio_row the
    readings of RADIO_COLUMNS at the request. Everything is known to the player when the
    request is issued.
    """
    recent = tputs[-WINDOW:]
    return np.array([recent[-1], harmonic_mean(recent), sum(recent) / len(recent),
                     min(recent), max(recent), *radio_row], dtype=float)


class ModelEstimator:
    """Segment throughput model trained on the logarithm of the realized throughput."""

    def __init__(self, model, radio: np.ndarray):
        self.model = model
        self.radio = radio

    def estimate(self, second: int, tputs: list) -> float:
        x = segment_features(tputs, self.radio[second])
        return float(math.exp(self.model.predict(x[None, :])[0]))


def bba_choice(buffer_level: float, n_reps: int, reservoir: float = BBA_RESERVOIR_S,
               cushion: float = BBA_CUSHION_S) -> int:
    """Buffer-based rule with the reservoir and cushion used by Mao et al. (2017).

    The lowest representation is chosen below the reservoir, the highest at or above
    reservoir + cushion, and the representation index grows linearly in between.
    """
    if buffer_level < reservoir:
        return 0
    if buffer_level >= reservoir + cushion:
        return n_reps - 1
    return int((n_reps - 1) * (buffer_level - reservoir) / cushion)


def bola_choice(buffer_level: float, bitrates, buffer_s: float = BUFFER_S,
                seg_s: float = SEGMENT_S, gamma_p: float = BOLA_GAMMA_P) -> int:
    """BOLA-BASIC of Spiteri et al. with logarithmic utilities.

    The representation maximises (V * (utility + gamma_p) - buffer) / bitrate, where
    V = (buffer_s - seg_s) / (highest utility + gamma_p) and the utility of the lowest
    representation is zero. The first maximiser is returned.
    """
    low = bitrates[0]
    utilities = [math.log(b / low) for b in bitrates]
    v = (buffer_s - seg_s) / (utilities[-1] + gamma_p)
    best, best_score = 0, -math.inf
    for q, (u, b) in enumerate(zip(utilities, bitrates)):
        score = (v * (u + gamma_p) - buffer_level) / b
        if score > best_score:
            best, best_score = q, score
    return best


def simulate_controlled(capacity_mbps, start_second: int, ladder_kbps, segment_bits, estimator,
                        controller: MarginController | None = None, rule: str = "mpc",
                        buffer_s: float = BUFFER_S, seg_s: float = SEGMENT_S,
                        latency_s: float = LATENCY_S, floor_mbps: float = FLOOR_MBPS,
                        mu: float | None = None, horizon: int = HORIZON,
                        fixed_margin: float = 0.0) -> tuple[dict, dict]:
    """Play one trace with an estimator and an optional online margin.

    The request, download, buffer and metric rules are those of src.has.simulate. The
    estimate of a request is estimator.estimate(second, throughputs) * exp(-margin),
    floored at floor_mbps, where margin is the controller's value or else fixed_margin.
    After each segment that had an estimate, the three signals are recorded and the
    controller, if any, is updated with its own signal. A segment cut by the end of the
    trace gives no update.

    Returns (metrics, log). metrics holds METRIC_KEYS of src.has.simulate and:
      n_decisions            segments that had an estimate and were completed
      stall_time_fraction    mean over those segments of min(avoidable stall / seg_s, 1)
      stall_event_fraction   share of those segments with an avoidable stall
      overestimate_fraction  share of those segments whose estimate exceeded their throughput
      control_loss_mean      mean of the controller's signal (NaN without controller)
      margin_mean, margin_final, margin_max   margin used at the requests and after the
                             last update
      avoidable_s            total avoidable stall time in seconds
    log additionally holds margin and avoidable_s per request.
    """
    cap = np.asarray(capacity_mbps, dtype=float)
    if cap.ndim != 1 or len(cap) == 0:
        raise ValueError("capacity must be a non-empty 1-D array")
    if not np.all(np.isfinite(cap)) or np.any(cap < 0):
        raise ValueError("capacity must be finite and non-negative")
    n = len(cap)
    start = int(start_second)
    if not 0 <= start < n:
        raise ValueError("start_second outside the capacity trace")
    ladder = np.asarray(ladder_kbps, dtype=float) / 1000.0
    sizes = np.asarray(segment_bits, dtype=float) / 1e6
    if sizes.ndim != 2 or sizes.shape[1] != len(ladder) or np.any(sizes <= 0):
        raise ValueError("segment_bits must have shape (n_segments, n_reps), positive")
    if rule not in ALL_RULES:
        raise ValueError(f"unknown rule {rule}")
    mu = float(ladder[-1]) if mu is None else float(mu)

    cum = np.concatenate(([0.0], np.cumsum(cap))).tolist()
    capl = cap.tolist()
    ladder_l = ladder.tolist()
    sizes_l = sizes.tolist()
    n_video = len(sizes_l)
    t_end = float(n)
    wait_cap = buffer_s - seg_s

    t = float(start)
    buf = 0.0
    playing = False
    k = 0
    last_rep = 0
    startup = np.nan
    t_play = np.nan
    rebuf_total = 0.0
    rebuf_final = 0.0
    stalls = 0
    wait_total = 0.0
    discarded = 0
    tputs: list[float] = []
    reps: list[int] = []
    n_dec = 0
    sum_time = sum_event = sum_over = sum_avoid = sum_loss = 0.0
    margins: list[float] = []
    log = {"request_s": [], "estimate_mbps": [], "rep": [], "mbit": [], "finish_s": [],
           "throughput_mbps": [], "buffer_s": [], "rebuffer_s": [], "wait_s": [],
           "margin": [], "avoidable_s": []}

    while t < t_end:
        margin = controller.margin if controller is not None else fixed_margin
        if k == 0:
            est = np.nan
            rep = 0
        elif rule == "bba":
            est = np.nan
            rep = bba_choice(buf, len(ladder_l))
        elif rule == "bola":
            est = np.nan
            rep = bola_choice(buf, ladder_l, buffer_s, seg_s)
        else:
            est = estimator.estimate(int(t), tputs)
            if est != est:
                rep = 0
            else:
                est = max(est * math.exp(-margin), floor_mbps)
                if rule == "rate":
                    rep = max(bisect_right(ladder_l, est) - 1, 0)
                else:
                    idx = [(k + j) % n_video for j in range(horizon)]
                    rep = mpc_choice(est, buf, last_rep, sizes[idx], ladder_l, mu,
                                     seg_s, latency_s, buffer_s)
        mbit = sizes_l[k % n_video][rep]
        finish = download_finish(cum, capl, t + latency_s, mbit)
        buf_before = buf
        if finish == np.inf:
            dt = t_end - t
            if playing:
                if dt > buf:
                    rebuf_final = dt - buf
                    rebuf_total += rebuf_final
                    stalls += 1
                    buf = 0.0
                else:
                    buf -= dt
            discarded = 1
            for key, v in (("request_s", t), ("estimate_mbps", est), ("rep", rep),
                           ("mbit", mbit), ("finish_s", np.inf), ("throughput_mbps", np.nan),
                           ("buffer_s", buf_before), ("rebuffer_s", rebuf_final),
                           ("wait_s", 0.0), ("margin", margin), ("avoidable_s", 0.0)):
                log[key].append(v)
            t = t_end
            break
        dt = finish - t
        reb = 0.0
        if playing:
            if dt > buf:
                reb = dt - buf
                rebuf_total += reb
                stalls += 1
                buf = 0.0
            else:
                buf -= dt
        else:
            startup = finish - start
            t_play = finish
            playing = True
        buf += seg_s
        tput = mbit / (finish - t - latency_s)
        avoid = 0.0
        if k >= 1 and est == est:
            if reb > 0.0 and rep > 0:
                finish_low = download_finish(cum, capl, t + latency_s, sizes_l[k % n_video][0])
                avoid = max(reb - max(finish_low - t - buf_before, 0.0), 0.0)
            loss_time = min(avoid / seg_s, 1.0)
            loss_event = 1.0 if avoid > 0.0 else 0.0
            loss_over = 1.0 if est > tput else 0.0
            n_dec += 1
            sum_time += loss_time
            sum_event += loss_event
            sum_over += loss_over
            sum_avoid += avoid
            margins.append(margin)
            if controller is not None:
                loss = {"stall_time": loss_time, "stall_event": loss_event,
                        "overestimate": loss_over}[controller.signal]
                sum_loss += loss
                controller.update(loss)
        tputs.append(tput)
        reps.append(rep)
        last_rep = rep
        req = t
        t = finish
        k += 1
        wait = buf - wait_cap
        if wait > 0.0:
            wait = min(wait, t_end - t)
            buf -= wait
            t += wait
            wait_total += wait
        else:
            wait = 0.0
        for key, v in (("request_s", req), ("estimate_mbps", est), ("rep", rep),
                       ("mbit", mbit), ("finish_s", finish), ("throughput_mbps", tput),
                       ("buffer_s", buf_before), ("rebuffer_s", reb), ("wait_s", wait),
                       ("margin", margin), ("avoidable_s", avoid)):
            log[key].append(v)

    log = {key: np.asarray(v, dtype=int if key == "rep" else float) for key, v in log.items()}
    duration = t_end - start
    n_seg = len(reps)
    final_margin = controller.margin if controller is not None else fixed_margin
    control = {"n_decisions": n_dec,
               "stall_time_fraction": sum_time / n_dec if n_dec else np.nan,
               "stall_event_fraction": sum_event / n_dec if n_dec else np.nan,
               "overestimate_fraction": sum_over / n_dec if n_dec else np.nan,
               "control_loss_mean": (sum_loss / n_dec if n_dec and controller is not None
                                     else np.nan),
               "margin_mean": float(np.mean(margins)) if margins else np.nan,
               "margin_final": final_margin,
               "margin_max": max(max(margins, default=final_margin), final_margin),
               "avoidable_s": sum_avoid}
    if n_seg == 0:
        return {**_empty_metrics(duration), **control}, log
    rates = ladder[np.asarray(reps)]
    changes = np.abs(np.diff(rates))
    switches = int(np.count_nonzero(changes))
    change_sum = float(changes.sum())
    window = t_end - t_play
    play = window - rebuf_total
    qoe = float(rates.sum()) - change_sum - mu * rebuf_total - mu * startup
    metrics = {
        "n_segments": n_seg,
        "avg_bitrate_mbps": float(rates.mean()),
        "rebuffer_s": rebuf_total,
        "rebuffer_final_s": rebuf_final,
        "rebuffer_ratio": rebuf_total / window if window > 0 else np.nan,
        "stalls": stalls,
        "startup_s": startup,
        "play_s": play,
        "switches": switches,
        "switches_per_min": switches / (play / 60.0) if play > 0 else np.nan,
        "mean_abs_switch_mbps": change_sum / switches if switches else np.nan,
        "qoe_total": qoe,
        "qoe_per_segment": qoe / n_seg,
        "wait_s": wait_total,
        "discarded": discarded,
        "duration_s": duration,
    }
    return {**metrics, **control}, log


def training_rows(log: dict, radio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Features and log-throughput targets from the request log of one played trace.

    Each row describes a completed request after the first; its features use only the
    throughputs of earlier segments and the radio readings of the request second.
    """
    tputs: list[float] = []
    X, y = [], []
    for i, (second, tput) in enumerate(zip(log["request_s"], log["throughput_mbps"])):
        if tput != tput:
            break
        if i >= 1:
            X.append(segment_features(tputs, radio[int(second)]))
            y.append(math.log(tput))
        tputs.append(float(tput))
    n_col = N_HISTORY_FEATURES + radio.shape[1]
    return (np.asarray(X, dtype=float).reshape(-1, n_col), np.asarray(y, dtype=float))


def capacity_trace(rows) -> tuple[np.ndarray, np.ndarray]:
    """Capacity and radio readings of a trace from its rows in the downloading state.

    rows is the table of one trace in time order. Rows outside the downloading state are
    removed. Second s of the replay carries the throughput of kept row s + 1, and a
    request issued during second s sees the radio readings of kept row s. Missing
    throughput values count as zero capacity.
    """
    d = rows[rows["state"] == "D"]
    dl = d["dl_mbps"].fillna(0.0).to_numpy(dtype=float)
    radio = d[list(RADIO_COLUMNS)].to_numpy(dtype=float)
    return dl[1:], radio[:-1]


def replay_rows(rows) -> tuple[np.ndarray, np.ndarray]:
    """Capacity and radio readings of a trace with every row kept.

    Rows outside the downloading state stay and are replayed with their measured
    throughput; this is the sensitivity treatment of protocol amendment 3.
    """
    dl = rows["dl_mbps"].fillna(0.0).to_numpy(dtype=float)
    radio = rows[list(RADIO_COLUMNS)].to_numpy(dtype=float)
    return dl[1:], radio[:-1]


def load_lumos(zip_path) -> "pd.DataFrame":
    """Lumos5G-v1.0 in the row format of src.data_loading.load_all, one trace per run.

    Throughput is the per-second iPerf TCP downlink in Mbit/s. When the device is on 5G
    (nrStatus CONNECTED) RSRP, RSRQ and SNR come from the NR columns if those are
    present and otherwise from the LTE columns; RSSI is the LTE value, speed is converted
    from m/s to km/h and CQI is not available. Values reported as unavailable are missing.
    """
    import zipfile

    import pandas as pd

    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and "__MACOSX" not in n)
        with z.open(name) as f:
            df = pd.read_csv(f)
    numeric = ["lte_rssi", "lte_rsrp", "lte_rsrq", "lte_rssnr", "nr_ssRsrp", "nr_ssRsrq",
               "nr_ssSinr"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
        df.loc[df[c].abs() > LUMOS_UNAVAILABLE, c] = np.nan
    on_nr = df["nrStatus"] == "CONNECTED"
    out = pd.DataFrame({
        "seq": df["seq_num"].astype(float),
        "run": df["run_num"].astype(int),
        "dl_mbps": df["Throughput"].astype(float),
        "RSRP": df["nr_ssRsrp"].where(on_nr & df["nr_ssRsrp"].notna(), df["lte_rsrp"]),
        "RSRQ": df["nr_ssRsrq"].where(on_nr & df["nr_ssRsrq"].notna(), df["lte_rsrq"]),
        "SNR": df["nr_ssSinr"].where(on_nr & df["nr_ssSinr"].notna(), df["lte_rssnr"]),
        "CQI": np.nan,
        "RSSI": df["lte_rssi"],
        "Speed": df["movingSpeed"].astype(float) * 3.6,
        "is_5g_mode": on_nr.astype(float),
        "state": "D",
        "tech": "5G",
        "mobility": df["mobility_mode"],
        "operator": "unknown",
        "app": "Download",
    })
    out["trace_id"] = ("Lumos5G/" + out["mobility"] + "/run_"
                       + out["run"].map(lambda r: f"{r:03d}"))
    out = out.sort_values(["run", "seq"], kind="stable").reset_index(drop=True)
    return out.drop(columns=["seq", "run"])


def development_traces(table: dict, fraction: float = 0.4, seed: int = 20261108) -> list:
    """Stratified draw of development traces.

    table maps a stratum name to its trace identifiers. Strata are visited in sorted
    order and one generator is used throughout; in each stratum the sorted identifiers
    are shuffled and the first round(fraction * n) are taken. Returns a sorted list.
    """
    rng = np.random.default_rng(seed)
    chosen: list[str] = []
    for stratum in sorted(table):
        ids = sorted(table[stratum])
        rng.shuffle(ids)
        chosen.extend(ids[:round(fraction * len(ids))])
    return sorted(chosen)


def split_folds(ids, n_folds: int = 5, seed: int = 20261108) -> dict:
    """Assign sorted, shuffled identifiers cyclically to folds; returns {fold: ids}."""
    order = sorted(ids)
    np.random.default_rng(seed).shuffle(order)
    return {f: sorted(order[f:: n_folds]) for f in range(n_folds)}


__all__ = ["CONTROL_KEYS", "External", "HarmonicMean", "MarginController", "METRIC_KEYS",
           "ModelEstimator", "RADIO_COLUMNS", "RobustDiscount", "SIGNALS", "capacity_trace",
           "development_traces", "segment_features", "simulate_controlled", "split_folds",
           "training_rows"]
