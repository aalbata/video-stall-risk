"""Development pilot of the online stall controller (protocol amendment 2).

Only the development traces of protocol/stall_development_traces.json are used. The
per-trace metrics of each (setting, fold) are written to
results/stall_control/pilot/cells/<setting>__f<fold>.csv; cells already written are
skipped.

Usage: python scripts/run_stall_pilot.py [--n-jobs 6]
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.has import METRIC_KEYS, Ladder, load_ladder  # noqa: E402
from src.models import GBMPoint  # noqa: E402
from src.stall_control import (CONTROL_KEYS, HarmonicMean, MarginController,  # noqa: E402
                               ModelEstimator, RobustDiscount, capacity_trace,
                               simulate_controlled, split_folds, training_rows)

SEED = 20261108
LIMITS = (0.002, 0.005, 0.01, 0.02, 0.04)
LEVELS = (0.05, 0.1, 0.2, 0.3, 0.4)
STEPS = (0.1, 0.25, 0.5)
FLOORS = (-0.5, 0.0)
FIXED_MARGINS = (-0.25, 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25, 1.5)
N_FOLDS = 5
TRAIN_SHARE = 0.75
N_RADIO = 7

OUT = ROOT / "results" / "stall_control" / "pilot"
PARTITION = ROOT / "protocol" / "stall_development_traces.json"
AMENDMENTS = ROOT / "protocol" / "amendments.md"
LADDER_CSV = ROOT / "data" / "ladder" / "segmentByteCostinColumns-bbb-x264-4sec-main.csv"
ID_COLUMNS = ["setting", "fold", "role", "trace_id", "mobility", "variant", "family", "base",
              "signal", "limit", "step", "floor", "fixed_margin"]


def variants() -> list:
    """All compared estimators; each is a dict of the ID_COLUMNS that describe it."""
    blank = {"signal": "", "limit": np.nan, "step": np.nan, "floor": np.nan,
             "fixed_margin": np.nan}
    out = [{**blank, "variant": b, "family": "baseline", "base": b}
           for b in ("robust", "hm", "model_robust")]
    for m in FIXED_MARGINS:
        out.append({**blank, "variant": f"fixed_{m:g}", "family": "fixed", "base": "model",
                    "fixed_margin": m})

    def online(family, base, signal, levels, floors):
        for limit in levels:
            for step in STEPS:
                for floor in floors:
                    out.append({**blank, "variant": f"{family}_{signal}_{limit:g}_{step:g}_{floor:g}",
                                "family": family, "base": base, "signal": signal, "limit": limit,
                                "step": step, "floor": floor})

    online("online", "model", "stall_time", LIMITS, FLOORS)
    online("online", "model", "stall_event", LIMITS, FLOORS)
    online("online_over", "model", "overestimate", LEVELS, FLOORS)
    online("online_hm", "hm", "stall_time", LIMITS, (-0.5,))
    return out


def load_traces(dev_ids: list) -> dict:
    """Capacity and radio readings of the development traces only."""
    from src.data_loading import load_all
    raw = load_all(ROOT / "data" / "raw")
    raw = raw[raw["trace_id"].isin(set(dev_ids))]
    traces = {}
    for sid, g in raw.groupby("trace_id", sort=False):
        if g["tech"].iloc[0] != "4G":
            raise SystemExit(f"{sid} is not a 4G trace")
        cap, radio = capacity_trace(g)
        traces[sid] = {"cap": cap, "radio": radio, "mobility": g["mobility"].iloc[0]}
    if set(traces) != set(dev_ids):
        raise SystemExit("development traces missing from the raw data")
    return traces


def fit_model(train_ids: list, traces: dict, ladder: Ladder, seed: int):
    """Train the segment model on logs of RobustMPC replayed on the training traces.

    Returns the fitted model, the training medians of the radio columns and the number of
    training rows.
    """
    Xs, ys = [], []
    for sid in train_ids:
        tr = traces[sid]
        _, log = simulate_controlled(tr["cap"], 0, ladder.bitrates_kbps, ladder.segment_bits,
                                     RobustDiscount(HarmonicMean()), seg_s=ladder.segment_s)
        X, y = training_rows(log, tr["radio"])
        Xs.append(X)
        ys.append(y)
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    med = np.array([np.median(c[~np.isnan(c)]) if np.any(~np.isnan(c)) else 0.0
                    for c in X[:, -N_RADIO:].T])
    miss = np.isnan(X[:, -N_RADIO:])
    X[:, -N_RADIO:] = np.where(miss, np.broadcast_to(med, miss.shape), X[:, -N_RADIO:])
    return GBMPoint(seed).fit(X, y), med, len(y)


def make_estimator(base: str, radio: np.ndarray, model):
    if base == "robust":
        return RobustDiscount(HarmonicMean())
    if base == "hm":
        return HarmonicMean()
    est = ModelEstimator(model, radio)
    return RobustDiscount(est) if base == "model_robust" else est


def play_trace(setting, fold, role, sid, tr, model, med, ladder, var_list) -> list:
    """Replay one trace with every variant; returns one row per variant."""
    radio = np.where(np.isnan(tr["radio"]), np.broadcast_to(med, tr["radio"].shape), tr["radio"])
    rows = []
    for v in var_list:
        ctl = None
        if v["family"].startswith("online"):
            ctl = MarginController(limit=v["limit"], step=v["step"], floor=v["floor"],
                                   signal=v["signal"])
        fixed = 0.0 if np.isnan(v["fixed_margin"]) else v["fixed_margin"]
        m, _ = simulate_controlled(tr["cap"], 0, ladder.bitrates_kbps, ladder.segment_bits,
                                   make_estimator(v["base"], radio, model), controller=ctl,
                                   seg_s=ladder.segment_s, fixed_margin=fixed)
        rows.append({"setting": setting, "fold": fold, "role": role, "trace_id": sid,
                     "mobility": tr["mobility"], **v, **{k: m[k] for k in METRIC_KEYS},
                     **{k: m[k] for k in CONTROL_KEYS}})
    return rows


def run_cell(setting, fold, train_ids, playback, calibration, traces, ladder, var_list,
             n_jobs) -> tuple:
    """Fit the model of one cell and replay its traces; returns (rows, n_train, seconds)."""
    t0 = time.time()
    model, med, n_train = fit_model(train_ids, traces, ladder, SEED)
    jobs = [("playback", s) for s in playback] + [("calibration", s) for s in calibration]
    if n_jobs > 1:
        from joblib import Parallel, delayed
        parts = Parallel(n_jobs=n_jobs)(
            delayed(play_trace)(setting, fold, role, s, traces[s], model, med, ladder, var_list)
            for role, s in jobs)
    else:
        parts = [play_trace(setting, fold, role, s, traces[s], model, med, ladder, var_list)
                 for role, s in jobs]
    return [r for p in parts for r in p], n_train, time.time() - t0


def cells(dev_ids: list, traces: dict) -> list:
    """(setting, fold, train, playback, calibration) of the two development settings."""
    folds = split_folds(dev_ids, N_FOLDS, SEED)
    out = []
    for f, test in folds.items():
        train = sorted(s for s in dev_ids if s not in set(test))
        out.append(("dev_cv", f, train, test, []))
    source = sorted(s for s in dev_ids if traces[s]["mobility"] in ("static", "pedestrian"))
    target = sorted(s for s in dev_ids if traces[s]["mobility"] in ("car", "bus", "train"))
    order = list(source)
    np.random.default_rng(SEED).shuffle(order)
    n_train = round(TRAIN_SHARE * len(order))
    out.append(("dev_mob", 0, sorted(order[:n_train]), target, sorted(order[n_train:])))
    return out


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=6)
    args = ap.parse_args()

    dev_ids = json.loads(PARTITION.read_text(encoding="utf-8"))["development_traces"]
    ladder = load_ladder(LADDER_CSV)
    var_list = variants()
    (OUT / "cells").mkdir(parents=True, exist_ok=True)
    import sklearn
    config = {"seed": SEED, "limits": LIMITS, "levels": LEVELS, "steps": STEPS, "floors": FLOORS,
              "fixed_margins": FIXED_MARGINS, "n_folds": N_FOLDS, "train_share": TRAIN_SHARE,
              "n_variants": len(var_list),
              "provenance": {"amendments_sha256": sha256_file(AMENDMENTS),
                             "partition_sha256": sha256_file(PARTITION),
                             "stall_control_py_sha256": sha256_file(ROOT / "src" / "stall_control.py"),
                             "has_py_sha256": sha256_file(ROOT / "src" / "has.py"),
                             "run_stall_pilot_py_sha256": sha256_file(Path(__file__).resolve())},
              "environment": {"host": platform.node(), "python": platform.python_version(),
                              "numpy": np.__version__, "pandas": pd.__version__,
                              "scikit_learn": sklearn.__version__, "n_jobs": args.n_jobs}}
    path = OUT / "run_config.json"
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored["provenance"] != config["provenance"]:
            raise SystemExit(f"{path}: provenance differs from this launch")
    else:
        config["first_launch_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path.write_text(json.dumps(config, indent=1), encoding="utf-8")

    t0 = time.time()
    traces = load_traces(dev_ids)
    print(f"{len(traces)} development traces loaded in {time.time() - t0:.0f}s; "
          f"{len(var_list)} variants", flush=True)
    columns = [*ID_COLUMNS, *METRIC_KEYS, *CONTROL_KEYS]
    for setting, fold, train, playback, calibration in cells(dev_ids, traces):
        cell = OUT / "cells" / f"{setting}__f{fold}.csv"
        if cell.exists():
            print(f"{setting}/f{fold}: already written", flush=True)
            continue
        rows, n_train, dt = run_cell(setting, fold, train, playback, calibration, traces, ladder,
                                     var_list, args.n_jobs)
        tmp = cell.with_name(cell.name + ".tmp")
        pd.DataFrame(rows, columns=columns).to_csv(tmp, index=False)
        os.replace(tmp, cell)
        print(f"{setting}/f{fold}: train traces {len(train)}, training rows {n_train}, "
              f"playback {len(playback)}, calibration {len(calibration)}, {dt:.0f}s", flush=True)
    print(f"finished in {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
