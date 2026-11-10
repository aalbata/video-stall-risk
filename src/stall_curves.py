"""Operating curves of the exploratory analysis in protocol amendment 4.

Replays every test trace with RobustMPC whose discount is scaled by a factor beta, and with
the harmonic mean discounted by the online margin. Neither uses a trained model, so each trace
is replayed once. Results go to results/stall_control/curves/curves_rows.csv.gz.

Run through scripts/run_stall_curves.py [--n-jobs 6].
"""
import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.has import METRIC_KEYS, WINDOW, harmonic_mean  # noqa: E402
from src.stall_control import (CONTROL_KEYS, HarmonicMean, MarginController,  # noqa: E402
                               simulate_controlled)
from src.stall_test import STEP, FLOOR, SIGNAL, data, identifier_sets  # noqa: E402

BETAS = (0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0)
LEVELS = (0.05, 0.10, 0.20)
OUT = ROOT / "results" / "stall_control" / "curves"


class ScaledDiscount:
    """Harmonic mean / (1 + beta * largest relative error of its last WINDOW estimates).

    beta = 1 is the RobustMPC estimate and beta = 0 the plain harmonic mean.
    """

    def __init__(self, beta: float):
        self.beta = beta
        self.hist: list = []
        self.errs: list = []

    def estimate(self, second: int, tputs: list) -> float:
        value = harmonic_mean(tputs[-WINDOW:])
        if self.hist:
            self.errs.append(abs(self.hist[-1] - tputs[-1]) / tputs[-1])
        max_err = max(self.errs[-WINDOW:]) if self.errs else 0.0
        self.hist.append(value)
        return value / (1.0 + self.beta * max_err)


def play_trace(sid: str) -> list:
    d = data()
    tr, ladder = d["table"][sid], d["ladder"]
    rows = []

    def add(name: str, kind: str, value: float, est, controller=None) -> None:
        m, log = simulate_controlled(tr["cap"], 0, ladder.bitrates_kbps, ladder.segment_bits, est,
                                     controller=controller, seg_s=ladder.segment_s)
        done = np.isfinite(log["finish_s"])
        top = float(np.mean(log["rep"][done] == ladder.segment_bits.shape[1] - 1)) if done.any() else np.nan
        rows.append({"trace_id": sid, "tech": tr["tech"], "mobility": tr["mobility"], "variant": name,
                     "kind": kind, "value": value, **{k: m[k] for k in METRIC_KEYS},
                     **{k: m[k] for k in CONTROL_KEYS}, "top_fraction": top})

    for beta in BETAS:
        add(f"robust_beta_{beta:g}", "robust_scaled", beta, ScaledDiscount(beta))
    for level in LEVELS:
        add(f"hm_margin_{level:g}", "hm_margin", level, HarmonicMean(),
            MarginController(limit=level, step=STEP, floor=FLOOR, signal=SIGNAL))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=6)
    args = ap.parse_args()
    d = data()
    ids = identifier_sets(d["table"], d["dev"])
    traces = sorted(set(ids["pool"]) | set(ids["g5"]) | set(ids["lumos"]))
    from joblib import Parallel, delayed
    t0 = time.time()
    parts = Parallel(n_jobs=args.n_jobs)(delayed(play_trace)(s) for s in traces)
    df = pd.DataFrame([r for p in parts for r in p])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "curves_rows.csv.gz"
    df.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
    minutes = (time.time() - t0) / 60.0
    (OUT / "run_config.json").write_text(json.dumps({"betas": BETAS, "levels": LEVELS, "step": STEP, "floor": FLOOR,
                                                     "signal": SIGNAL, "n_traces": len(traces)}, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")
    (OUT / "run_log.txt").write_text(f"{len(traces)} traces, {len(df)} rows\n", encoding="utf-8", newline="\n")
    print(f"{len(traces)} traces, {len(df)} rows, {minutes:.1f} min")
