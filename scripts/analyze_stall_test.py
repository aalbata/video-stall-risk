"""Analysis of the final test of the online margin (protocol amendment 3).

Reads results/stall_control/test/cells/*.csv and writes test_summary.json and test_tables.md
to the same parent folder.

Usage: python scripts/analyze_stall_test.py [--dir DIR]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.stats import bh_correct, bootstrap_ci_mean, paired_wilcoxon  # noqa: E402

PRIMARY = "online_0.05"
REGIMES = ["in_domain_4g", "in_domain_5g", "cross_mobility_4g", "cross_mobility_5g",
           "cross_tech_4to5", "cross_tech_5to4", "external_lumos5g"]
MEASURES = ["qoe_per_segment", "rebuffer_ratio", "avg_bitrate_mbps", "stalls", "switches_per_min",
            "overestimate_fraction", "margin_mean", "top_fraction"]
SECONDARY_METRICS = ["rebuffer_ratio", "stalls", "avg_bitrate_mbps"]
QOE_COMPARATORS = ["model_robust", "bola", "bba", "old_aci", "fixed_tuned", "hm", "model"]
LEVEL_VARIANTS = {"online_0.05": 0.05, "online_0.1": 0.10, "online_0.2": 0.20}


def load(directory: Path) -> pd.DataFrame:
    combined = directory / "test_rows.csv.gz"
    if combined.exists():
        return pd.read_csv(combined)
    files = sorted((directory / "cells").glob("*.csv"))
    if len(files) != 55:
        raise SystemExit(f"expected 55 cell files, found {len(files)}")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def per_trace(df: pd.DataFrame) -> pd.DataFrame:
    """Seed averages of every measure per regime, variant and trace."""
    return df.groupby(["regime", "variant", "trace_id"], sort=False)[MEASURES].mean().reset_index()


def paired(tr: pd.DataFrame, regime: str, a: str, b: str, metric: str) -> dict:
    x = tr[(tr["regime"] == regime) & (tr["variant"] == a)].set_index("trace_id")[metric]
    y = tr[(tr["regime"] == regime) & (tr["variant"] == b)].set_index("trace_id")[metric]
    idx = x.index.intersection(y.index)
    res = paired_wilcoxon(x.loc[idx].to_numpy(), y.loc[idx].to_numpy())
    return {**res, "mean_a": float(x.loc[idx].mean()), "mean_b": float(y.loc[idx].mean())}


def family(tr: pd.DataFrame, a: str, b: str, metric: str) -> list:
    """One paired test per regime, Benjamini-Hochberg adjusted over the regimes."""
    rows = [{"regime": r, "a": a, "b": b, "metric": metric, **paired(tr, r, a, b, metric)}
            for r in REGIMES]
    _, adj = bh_correct([r["p"] for r in rows])
    for r, p in zip(rows, adj):
        r["p_bh"] = p
    return rows


def verdict(rec: dict) -> str:
    """Claim rule of amendment 3.7 for QoE."""
    if rec["p_bh"] < 0.05 and rec["median_diff"] > 0:
        return "higher"
    if rec["p_bh"] < 0.05 and rec["median_diff"] < 0:
        return "lower"
    return "no difference"


def means_with_ci(tr: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (regime, variant), g in tr.groupby(["regime", "variant"], sort=False):
        rec = {"regime": regime, "variant": variant, "n": len(g)}
        for m in MEASURES:
            rec[m] = float(g[m].mean())
        mean, lo, hi = bootstrap_ci_mean(g["qoe_per_segment"].to_numpy())
        rec.update(qoe_lo=lo, qoe_hi=hi)
        out.append(rec)
    return pd.DataFrame(out)


def bound_check(df: pd.DataFrame) -> dict:
    """Per-trace inequality mean(signal) - level <= final margin / (step * K)."""
    d = df[(df["variant"].isin(LEVEL_VARIANTS)) & (df["role"] != "calibration") &
           (df["n_decisions"] > 0)]
    lhs = d["control_loss_mean"] - d["variant"].map(LEVEL_VARIANTS)
    rhs = d["margin_final"] / (0.5 * d["n_decisions"])
    return {"n_rows": int(len(d)), "n_violations": int((lhs > rhs + 1e-9).sum()),
            "largest_excess": float((lhs - rhs).max())}


def fmt(frame: pd.DataFrame) -> str:
    return "```\n" + frame.round(4).to_string() + "\n```"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=ROOT / "results" / "stall_control" / "test")
    args = ap.parse_args()
    df = load(args.dir)
    main_df = df[df["role"] == "playback"]
    tr = per_trace(main_df)
    means = means_with_ci(tr)

    primary = family(tr, PRIMARY, "robust", "qoe_per_segment")
    for r in primary:
        r["verdict"] = verdict(r)
    secondary = {m: family(tr, PRIMARY, "robust", m) for m in SECONDARY_METRICS}
    comparators = {c: family(tr, PRIMARY, c, "qoe_per_segment") for c in QOE_COMPARATORS}
    stalls_vs_model_robust = family(tr, PRIMARY, "model_robust", "stalls")

    idle = df[df["role"] == "idle_as_zero"]
    idle_tr = idle.groupby(["regime", "variant", "trace_id"], sort=False)[MEASURES].mean().reset_index()
    idle_tests = [{"regime": r, **paired(idle_tr, r, PRIMARY, "robust", "qoe_per_segment")}
                  for r in REGIMES[:-1]]
    _, adj = bh_correct([r["p"] for r in idle_tests])
    for r, p in zip(idle_tests, adj):
        r["p_bh"] = p
        r["verdict"] = verdict(r)
    idle_means = idle_tr.groupby(["regime", "variant"], sort=False)[MEASURES].mean().reset_index()

    fidelity = {}
    for v, level in LEVEL_VARIANTS.items():
        g = tr[tr["variant"] == v].groupby("regime", sort=False)["overestimate_fraction"].mean()
        fidelity[v] = {"level": level, "mean_by_regime": {k: float(x) for k, x in g.items()}}

    summary = {"primary_qoe_vs_robust": primary, "secondary_vs_robust": secondary,
               "qoe_vs_comparators": comparators, "stalls_vs_model_robust": stalls_vs_model_robust,
               "idle_as_zero": idle_tests, "level_fidelity": fidelity,
               "per_trace_bound": bound_check(df),
               "verdict_counts": {k: sum(r["verdict"] == k for r in primary)
                                  for k in ("higher", "lower", "no difference")},
               "tuned_margins": {r: sorted(float(x) for x in
                                           main_df[(main_df["regime"] == r) &
                                                   (main_df["variant"] == "fixed_tuned")]["fixed_margin"].unique())
                                 for r in REGIMES}}
    (args.dir / "test_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    lines = ["# Final test tables", ""]
    order = ["robust", "hm", "rate_hm", "bba", "bola", "old_aci", "model", "model_robust",
             "fixed_tuned", "online_0.05", "online_0.1", "online_0.2"]
    for r in REGIMES:
        g = means[means["regime"] == r].set_index("variant").reindex(order).drop(columns="regime")
        lines += [f"## {r}", "", fmt(g), ""]
    lines += ["## Sensitivity, rows outside the downloading state replayed as measured", "",
              fmt(idle_means.set_index(["regime", "variant"])), ""]
    (args.dir / "test_tables.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    view = pd.DataFrame(primary)[["regime", "n", "mean_a", "mean_b", "median_diff", "rank_biserial",
                                  "p_bh", "verdict"]]
    print(view.round(4).to_string())
    print(json.dumps({k: summary[k] for k in ("verdict_counts", "per_trace_bound", "level_fidelity")},
                     indent=1))


if __name__ == "__main__":
    main()
