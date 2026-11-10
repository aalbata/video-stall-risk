"""Measure the cost of the online margin on a laptop CPU, on development traces only.

Writes results/paper/cost.json with the time to train the segment model once, the time of
one prediction, the time of one margin update and the size of the fitted model.

Usage: python scripts/measure_decision_cost.py
"""
import json
import pickle
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src.stall_control import MarginController, RobustDiscount, HarmonicMean, simulate_controlled, training_rows  # noqa: E402
from src.stall_test import N_RADIO, data  # noqa: E402
from src.models import GBMPoint  # noqa: E402

OUT = ROOT / "results" / "paper" / "cost.json"


def main() -> None:
    d = data()
    table, ladder = d["table"], d["ladder"]
    train = sorted(d["dev"])[:40]
    Xs, ys = [], []
    for sid in train:
        tr = table[sid]
        _, log = simulate_controlled(tr["cap"], 0, ladder.bitrates_kbps, ladder.segment_bits,
                                     RobustDiscount(HarmonicMean()), seg_s=ladder.segment_s)
        X, y = training_rows(log, tr["radio"])
        Xs.append(X)
        ys.append(y)
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    med = np.array([np.nanmedian(c) if np.any(~np.isnan(c)) else 0.0 for c in X[:, -N_RADIO:].T])
    miss = np.isnan(X[:, -N_RADIO:])
    X[:, -N_RADIO:] = np.where(miss, np.broadcast_to(med, miss.shape), X[:, -N_RADIO:])
    t0 = time.perf_counter()
    model = GBMPoint(0).fit(X, y)
    train_s = time.perf_counter() - t0
    n = min(5000, len(X))
    t0 = time.perf_counter()
    for i in range(n):
        model.predict(X[i:i + 1])
    predict_ms = (time.perf_counter() - t0) / n * 1000.0
    ctl = MarginController(limit=0.05, step=0.5, floor=0.0, signal="overestimate")
    n_up = 1_000_000
    t0 = time.perf_counter()
    for i in range(n_up):
        ctl.update(float(i % 20 == 0))
    update_us = (time.perf_counter() - t0) / n_up * 1e6
    out = {"n_training_rows": int(len(y)), "train_seconds": round(train_s, 2),
           "predict_ms": round(predict_ms, 2), "update_us": round(update_us, 3),
           "model_kib": round(len(pickle.dumps(model)) / 1024.0, 0),
           "python": platform.python_version()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(out)


if __name__ == "__main__":
    main()
