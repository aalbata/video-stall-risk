"""Final test of the online margin on the test-pool traces (protocol amendment 3).

The per-trace metrics of each (regime, seed, fold) cell are written to
results/stall_control/test/cells/<regime>__s<seed>__f<fold>.csv; cells already written are
skipped. With --smoke, small cells built from development traces check the code path,
including the worker processes, and write to the folder given by --out.

Run through scripts/run_stall_test.py [--n-jobs 6] [--smoke --out DIR].
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import time
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[v] = "1"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.conformal import ACITrace  # noqa: E402
from src.data_loading import load_all, read_feature_table  # noqa: E402
from src.features import apply_impute, build_features, train_median_impute  # noqa: E402
from src.has import METRIC_KEYS, load_ladder  # noqa: E402
from src.models import GBMPoint  # noqa: E402
from src.stall_control import (CONTROL_KEYS, External, HarmonicMean,  # noqa: E402
                               MarginController, ModelEstimator, RobustDiscount, capacity_trace,
                               load_lumos, replay_rows, simulate_controlled, split_folds,
                               training_rows)

SEEDS = (0, 1, 2, 3, 4)
LEVELS = (0.05, 0.10, 0.20)
STEP = 0.5
FLOOR = 0.0
SIGNAL = "overestimate"
FIXED_GRID = (0.2, 0.4, 0.6, 0.8, 1.0)
TRAIN_SHARE = 0.75
OLD_ALPHA = 0.10
OLD_GAMMA = 0.05
N_RADIO = 7
FOLDS_5G = 5
REGIMES = ("in_domain_4g", "in_domain_5g", "cross_mobility_4g", "cross_mobility_5g",
           "cross_tech_4to5", "cross_tech_5to4", "external_lumos5g")

OUT = ROOT / "results" / "stall_control" / "test"
PARTITION = ROOT / "protocol" / "stall_development_traces.json"
AMENDMENTS = ROOT / "protocol" / "amendments.md"
LADDER_CSV = ROOT / "data" / "ladder" / "segmentByteCostinColumns-bbb-x264-4sec-main.csv"
FEATURES = ROOT / "data" / "processed" / "features_h1.csv.gz"
LUMOS_ZIP = ROOT / "data" / "external" / "lumos5g" / "Lumos5G-v1.0.zip"
ID_COLUMNS = ["regime", "seed", "fold", "role", "trace_id", "tech", "mobility", "variant",
              "fixed_margin"]
EXTRA = ["top_fraction"]


@lru_cache(maxsize=1)
def data() -> dict:
    """Replay inputs, per-second features and identifier lists (read once per process)."""
    raw = load_all(ROOT / "data" / "raw")
    raw = raw[(raw["tech"] == "4G") | (raw["app"] == "Download")]
    lumos = load_lumos(LUMOS_ZIP)
    table = {}
    for frame in (raw, lumos):
        for sid, g in frame.groupby("trace_id", sort=False):
            g = g.reset_index(drop=True)
            cap, radio = capacity_trace(g)
            cap_all, radio_all = replay_rows(g)
            table[sid] = {"cap": cap, "radio": radio, "cap_all": cap_all, "radio_all": radio_all,
                          "kept": np.flatnonzero(g["state"].to_numpy() == "D"),
                          "tech": g["tech"].iloc[0], "mobility": g["mobility"].iloc[0],
                          "dataset": "lumos" if sid.startswith("Lumos5G/") else "irish"}
    feat = read_feature_table(FEATURES)
    feat = feat[feat["trace_id"].isin(set(table))]
    feat_lumos = build_features(lumos, horizon=1)
    feat = pd.concat([feat, feat_lumos], ignore_index=True)
    dev = json.loads(PARTITION.read_text(encoding="utf-8"))["development_traces"]
    return {"table": table, "feat": feat, "dev": dev, "ladder": load_ladder(LADDER_CSV)}


def identifier_sets(table: dict, dev: list) -> dict:
    irish = [s for s, t in table.items() if t["dataset"] == "irish"]
    g4 = sorted(s for s in irish if table[s]["tech"] == "4G")
    g5 = sorted(s for s in irish if table[s]["tech"] == "5G")
    pool = sorted(set(g4) - set(dev))
    if len(g4) != 135 or len(g5) != 21 or len(pool) != 82 or not set(dev) <= set(g4):
        raise SystemExit("unexpected numbers of capacity traces")
    return {"g4": g4, "g5": g5, "pool": pool, "dev": sorted(dev), "irish": sorted(irish),
            "lumos": sorted(s for s, t in table.items() if t["dataset"] == "lumos")}


def source_target(regime: str, seed: int, fold: int, table: dict, ids: dict) -> tuple:
    """Training, calibration and test traces of one cell."""
    if regime == "in_domain_4g":
        source, target = ids["dev"], ids["pool"]
    elif regime == "in_domain_5g":
        folds = split_folds(ids["g5"], FOLDS_5G, seed)
        target = folds[fold]
        source = sorted(set(ids["g5"]) - set(target))
    elif regime == "cross_mobility_4g":
        source = [s for s in ids["g4"] if table[s]["mobility"] in ("static", "pedestrian")]
        target = [s for s in ids["pool"] if table[s]["mobility"] in ("car", "bus", "train")]
    elif regime == "cross_mobility_5g":
        source = [s for s in ids["g5"] if table[s]["mobility"] == "static"]
        target = [s for s in ids["g5"] if table[s]["mobility"] == "driving"]
    elif regime == "cross_tech_4to5":
        source, target = ids["g4"], ids["g5"]
    elif regime == "cross_tech_5to4":
        source, target = ids["g5"], ids["pool"]
    elif regime == "external_lumos5g":
        source, target = ids["irish"], ids["lumos"]
    elif regime == "smoke":
        source, target = ids["dev"][:12], ids["dev"][12:15]
    else:
        raise ValueError(regime)
    if regime != "smoke" and set(target) & set(ids["dev"]):
        raise SystemExit(f"{regime}: development traces in the test set")
    order = sorted(source)
    np.random.default_rng(seed).shuffle(order)
    n_train = round(TRAIN_SHARE * len(order))
    return sorted(order[:n_train]), sorted(order[n_train:]), sorted(target)


def fit_segment_model(train: list, table: dict, ladder, seed: int):
    """Segment model trained on logs of RobustMPC replayed on the training traces."""
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
    med = np.array([np.median(c[~np.isnan(c)]) if np.any(~np.isnan(c)) else 0.0
                    for c in X[:, -N_RADIO:].T])
    miss = np.isnan(X[:, -N_RADIO:])
    X[:, -N_RADIO:] = np.where(miss, np.broadcast_to(med, miss.shape), X[:, -N_RADIO:])
    return GBMPoint(seed).fit(X, y), med


def old_bounds(feat: pd.DataFrame, train: list, cal: list, test: list, seed: int) -> dict:
    """Lower bound of two-sided ACI on the one-step model, per test trace.

    Same predictor, calibration and update as the earlier streaming analysis: {trace:
    (row indices, lower bounds)}.
    """
    tr = feat[feat["trace_id"].isin(set(train))]
    ca = feat[feat["trace_id"].isin(set(cal))]
    te = feat[feat["trace_id"].isin(set(test))]
    med = train_median_impute(tr)
    point = GBMPoint(seed).fit(apply_impute(tr, med), tr["y"].to_numpy())
    aci = ACITrace(OLD_ALPHA, gamma=OLD_GAMMA).calibrate(ca["y"].to_numpy(),
                                                         point.predict(apply_impute(ca, med)))
    out = {}
    for sid, g in te.groupby("trace_id", sort=False):
        g = g.sort_values("t_index")
        lo, _, _ = aci.run_trace(g["y"].to_numpy(), point.predict(apply_impute(g, med)))
        out[sid] = (g["t_index"].to_numpy(dtype=np.int64), lo)
    return out


def play(cap, radio, med, model, ladder, base: str, rule: str = "mpc", controller=None,
         fixed_margin: float = 0.0, external=None) -> tuple:
    imputed = np.where(np.isnan(radio), np.broadcast_to(med, radio.shape), radio)
    if base == "hm":
        est = HarmonicMean()
    elif base == "robust":
        est = RobustDiscount(HarmonicMean())
    elif base == "model":
        est = ModelEstimator(model, imputed)
    elif base == "model_robust":
        est = RobustDiscount(ModelEstimator(model, imputed))
    elif base == "external":
        est = External(external)
    else:
        est = None
    m, log = simulate_controlled(cap, 0, ladder.bitrates_kbps, ladder.segment_bits, est,
                                 controller=controller, rule=rule, seg_s=ladder.segment_s,
                                 fixed_margin=fixed_margin)
    done = np.isfinite(log["finish_s"])
    top = float(np.mean(log["rep"][done] == ladder.segment_bits.shape[1] - 1)) if done.any() else np.nan
    return m, top


def margin_controller(level: float) -> MarginController:
    return MarginController(limit=level, step=STEP, floor=FLOOR, signal=SIGNAL)


def row(regime, seed, fold, role, sid, tr, variant, m, top, margin=np.nan) -> dict:
    return {"regime": regime, "seed": seed, "fold": fold, "role": role, "trace_id": sid,
            "tech": tr["tech"], "mobility": tr["mobility"], "variant": variant,
            "fixed_margin": margin, **{k: m[k] for k in METRIC_KEYS},
            **{k: m[k] for k in CONTROL_KEYS}, "top_fraction": top}


def run_cell(regime: str, seed: int, fold: int) -> tuple:
    """Fit one cell and replay its calibration and test traces."""
    t0 = time.time()
    d = data()
    table, ladder = d["table"], d["ladder"]
    ids = identifier_sets(table, d["dev"])
    train, cal, test = source_target(regime, seed, fold, table, ids)
    model, med = fit_segment_model(train, table, ladder, seed)
    bounds = old_bounds(d["feat"], train, cal, test, seed)
    rows = []

    cal_qoe = {m: [] for m in FIXED_GRID}
    for sid in cal:
        tr = table[sid]
        for margin in FIXED_GRID:
            m, top = play(tr["cap"], tr["radio"], med, model, ladder, "model", fixed_margin=margin)
            cal_qoe[margin].append(m["qoe_per_segment"])
            rows.append(row(regime, seed, fold, "calibration", sid, tr, f"fixed_{margin:g}", m, top,
                            margin))
    means = {k: float(np.nanmean(v)) for k, v in cal_qoe.items()}
    tuned = max(FIXED_GRID, key=lambda k: (means[k], -k))

    for sid in test:
        tr = table[sid]
        idx, lo = bounds[sid]
        est = np.full(len(tr["cap"]), np.nan)
        pos = np.searchsorted(tr["kept"], idx)
        keep = pos < len(est)
        est[pos[keep]] = lo[keep]
        specs = [("robust", dict(base="robust")), ("hm", dict(base="hm")),
                 ("rate_hm", dict(base="hm", rule="rate")), ("bba", dict(base="", rule="bba")),
                 ("bola", dict(base="", rule="bola")), ("old_aci", dict(base="external", external=est)),
                 ("model", dict(base="model")), ("model_robust", dict(base="model_robust")),
                 ("fixed_tuned", dict(base="model", fixed_margin=tuned))]
        specs += [(f"online_{lv:g}", dict(base="model", controller=margin_controller(lv)))
                  for lv in LEVELS]
        for name, spec in specs:
            m, top = play(tr["cap"], tr["radio"], med, model, ladder, **spec)
            rows.append(row(regime, seed, fold, "playback", sid, tr, name, m, top,
                            tuned if name == "fixed_tuned" else np.nan))
        if tr["dataset"] == "irish":
            est_all = np.full(len(tr["cap_all"]), np.nan)
            keep = idx < len(est_all)
            est_all[idx[keep]] = lo[keep]
            for name, spec in (("online_0.05", dict(base="model", controller=margin_controller(0.05))),
                               ("robust", dict(base="robust")),
                               ("model_robust", dict(base="model_robust")),
                               ("old_aci", dict(base="external", external=est_all))):
                m, top = play(tr["cap_all"], tr["radio_all"], med, model, ladder, **spec)
                rows.append(row(regime, seed, fold, "idle_as_zero", sid, tr, name, m, top))
    return rows, len(train), len(cal), len(test), tuned, time.time() - t0


def write_cell(out_dir: Path, regime: str, seed: int, fold: int) -> tuple:
    res = run_cell(regime, seed, fold)
    columns = [*ID_COLUMNS, *METRIC_KEYS, *CONTROL_KEYS, *EXTRA]
    path = out_dir / "cells" / f"{regime}__s{seed}__f{fold}.csv"
    tmp = path.with_name(path.name + ".tmp")
    pd.DataFrame(res[0], columns=columns).to_csv(tmp, index=False)
    os.replace(tmp, path)
    return (regime, seed, fold, *res[1:])


def all_cells() -> list:
    out = []
    for seed in SEEDS:
        for regime in REGIMES:
            folds = range(FOLDS_5G) if regime == "in_domain_5g" else [0]
            out += [(regime, seed, f) for f in folds]
    return out


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-jobs", type=int, default=6)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    out_dir = args.out
    (out_dir / "cells").mkdir(parents=True, exist_ok=True)

    if args.smoke:
        from joblib import Parallel, delayed
        for r in Parallel(n_jobs=2)(delayed(write_cell)(out_dir, "smoke", s, 0) for s in (0, 1)):
            print("smoke cell (development traces only):", r, flush=True)
        return

    import sklearn
    config = {"seeds": SEEDS, "levels": LEVELS, "step": STEP, "floor": FLOOR, "signal": SIGNAL,
              "fixed_grid": FIXED_GRID, "train_share": TRAIN_SHARE, "regimes": REGIMES,
              "folds_5g": FOLDS_5G, "old_alpha": OLD_ALPHA, "old_gamma": OLD_GAMMA,
              "provenance": {"amendments_sha256": sha256_file(AMENDMENTS),
                             "partition_sha256": sha256_file(PARTITION),
                             "lumos_zip_sha256": sha256_file(LUMOS_ZIP),
                             "stall_control_py_sha256": sha256_file(ROOT / "src" / "stall_control.py"),
                             "has_py_sha256": sha256_file(ROOT / "src" / "has.py"),
                             "stall_test_py_sha256": sha256_file(Path(__file__).resolve())},
              "environment": {"host": platform.node(), "python": platform.python_version(),
                              "numpy": np.__version__, "pandas": pd.__version__,
                              "scikit_learn": sklearn.__version__, "n_jobs": args.n_jobs}}
    path = out_dir / "run_config.json"
    if path.exists():
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored["provenance"] != config["provenance"]:
            raise SystemExit(f"{path}: provenance differs from this launch")
    else:
        config["first_launch_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        path.write_text(json.dumps(config, indent=1), encoding="utf-8")

    pending = [c for c in all_cells()
               if not (out_dir / "cells" / f"{c[0]}__s{c[1]}__f{c[2]}.csv").exists()]
    print(f"{len(all_cells())} cells, {len(pending)} to run", flush=True)
    t0 = time.time()
    from joblib import Parallel, delayed
    stream = Parallel(n_jobs=args.n_jobs, return_as="generator_unordered")(
        delayed(write_cell)(out_dir, *c) for c in pending)
    for regime, seed, fold, n_train, n_cal, n_test, tuned, dt in stream:
        print(f"{regime}/s{seed}/f{fold}: train {n_train}, calibration {n_cal}, test {n_test}, "
              f"tuned margin {tuned:g}, {dt:.0f}s", flush=True)
    print(f"finished in {(time.time() - t0) / 60:.1f} min", flush=True)

