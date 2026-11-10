"""Selection and pass rule of the development pilot (protocol amendment 2.8).

Reads results/stall_control/pilot/cells/*.csv and writes pilot_summary.json and
pilot_tables.md to results/stall_control/pilot/.

Usage: python scripts/analyze_stall_pilot.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "stall_control" / "pilot"
EPS_TOLERANCE = 0.005
BOUND_TOL = 1e-9
MEASURES = ["qoe_per_segment", "rebuffer_ratio", "avg_bitrate_mbps", "stalls", "switches_per_min",
            "stall_time_fraction", "stall_event_fraction", "overestimate_fraction", "margin_mean"]


def load() -> pd.DataFrame:
    combined = OUT / "pilot_rows.csv.gz"
    if combined.exists():
        return pd.read_csv(combined, keep_default_na=True, na_values=[""]).assign(
            signal=lambda d: d["signal"].fillna(""))
    files = sorted((OUT / "cells").glob("*.csv"))
    if len(files) != 6:
        raise SystemExit(f"expected 6 cell files, found {len(files)}")
    return pd.concat([pd.read_csv(f, keep_default_na=True, na_values=[""]).assign(
        signal=lambda d: d["signal"].fillna("")) for f in files], ignore_index=True)


def means(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("variant", sort=False)[MEASURES].mean()


def select(cv: pd.DataFrame, family: str, signals: tuple) -> dict:
    """Best (signal, step, floor) by mean over limits of mean QoE on dev_cv playback."""
    d = cv[(cv["family"] == family) & cv["signal"].isin(signals)]
    by_limit = d.groupby(["signal", "step", "floor", "limit"])["qoe_per_segment"].mean()
    avg = by_limit.groupby(["signal", "step", "floor"]).mean().reset_index()
    avg = avg.sort_values(["qoe_per_segment", "step", "floor"], ascending=[False, True, False])
    top = avg.iloc[0]
    return {"signal": top["signal"], "step": float(top["step"]), "floor": float(top["floor"]),
            "mean_qoe_over_limits": float(top["qoe_per_segment"]),
            "ranking": avg.round(4).to_dict("records")}


def curve(df: pd.DataFrame, family: str, sel: dict) -> pd.DataFrame:
    d = df[(df["family"] == family) & (df["signal"] == sel["signal"]) &
           (df["step"] == sel["step"]) & (df["floor"] == sel["floor"])]
    return d.groupby("limit")[MEASURES].mean().sort_index()


def fixed_curve(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["family"] == "fixed"]
    return d.groupby("fixed_margin")[MEASURES].mean().sort_index()


def row(df: pd.DataFrame, variant: str) -> pd.Series:
    return df[df["variant"] == variant][MEASURES].mean()


def bound_check(df: pd.DataFrame) -> dict:
    """Per-trace inequality mean(loss) - limit <= final margin / (step * K)."""
    d = df[df["family"].isin(["online", "online_hm"]) & (df["n_decisions"] > 0)]
    lhs = d["control_loss_mean"] - d["limit"]
    rhs = d["margin_final"] / (d["step"] * d["n_decisions"])
    return {"n_rows": int(len(d)), "n_violations": int((lhs > rhs + BOUND_TOL).sum()),
            "largest_excess": float((lhs - rhs).max())}


def fmt(frame: pd.DataFrame) -> str:
    return "```\n" + frame.round(4).to_string() + "\n```"


def main() -> None:
    df = load()
    cv = df[df["setting"] == "dev_cv"]
    mob_all = df[df["setting"] == "dev_mob"]
    mob = mob_all[mob_all["role"] == "playback"]
    mob_cal = mob_all[mob_all["role"] == "calibration"]

    sel = select(cv, "online", ("stall_time", "stall_event"))
    sel_over = select(cv, "online_over", ("overestimate",))
    frac = f"{sel['signal']}_fraction"

    curves = {"dev_cv": curve(cv, "online", sel), "dev_mob": curve(mob, "online", sel)}
    curves_over = {"dev_cv": curve(cv, "online_over", sel_over),
                   "dev_mob": curve(mob, "online_over", sel_over)}
    robust = {"dev_cv": row(cv, "robust"), "dev_mob": row(mob, "robust")}

    # (a) the requested limit is met in the mean and the per-trace inequality holds
    a_means = {float(k): float(v) for k, v in curves["dev_mob"][frac].items()}
    a_mean_ok = all(v <= k + EPS_TOLERANCE for k, v in a_means.items())
    bound = bound_check(df)
    a_ok = a_mean_ok and bound["n_violations"] == 0

    # (b) one limit gives no more rebuffering and higher QoE than RobustMPC in both settings
    b_rows = []
    for limit in curves["dev_cv"].index:
        ok = True
        rec = {"limit": float(limit)}
        for s in ("dev_cv", "dev_mob"):
            c = curves[s].loc[limit]
            r = robust[s]
            cond = (c["rebuffer_ratio"] <= r["rebuffer_ratio"] and
                    c["qoe_per_segment"] > r["qoe_per_segment"])
            ok = ok and cond
            rec.update({f"{s}_rebuffer": float(c["rebuffer_ratio"]),
                        f"{s}_robust_rebuffer": float(r["rebuffer_ratio"]),
                        f"{s}_qoe": float(c["qoe_per_segment"]),
                        f"{s}_robust_qoe": float(r["qoe_per_segment"]),
                        f"{s}_bitrate": float(c["avg_bitrate_mbps"]),
                        f"{s}_robust_bitrate": float(r["avg_bitrate_mbps"]), f"{s}_met": bool(cond)})
        rec["met_in_both"] = bool(ok)
        b_rows.append(rec)
    b_ok = any(r["met_in_both"] for r in b_rows)

    # (c) online rule against a fixed margin, both tuned on source calibration traces only
    cal_online = curve(mob_cal, "online", sel)["qoe_per_segment"]
    limit_src = float(cal_online.idxmax())
    cal_fixed = fixed_curve(mob_cal)["qoe_per_segment"]
    margin_src = float(cal_fixed.idxmax())
    online_qoe = float(curves["dev_mob"].loc[limit_src, "qoe_per_segment"])
    fixed_tab = fixed_curve(mob)
    fixed_qoe = float(fixed_tab.loc[margin_src, "qoe_per_segment"])
    c_ok = online_qoe >= fixed_qoe

    # (d) reported only: freeze signal against overestimate signal, best point of each curve
    d_rows = {s: {"stall_signal_best_qoe": float(curves[s]["qoe_per_segment"].max()),
                  "overestimate_signal_best_qoe": float(curves_over[s]["qoe_per_segment"].max())}
              for s in curves}

    verdict = bool(a_ok and b_ok and c_ok)
    summary = {
        "selected": {k: v for k, v in sel.items() if k != "ranking"},
        "selected_overestimate": {k: v for k, v in sel_over.items() if k != "ranking"},
        "ranking": sel["ranking"], "ranking_overestimate": sel_over["ranking"],
        "a_limit": {"mean_fraction_by_limit_dev_mob": a_means, "tolerance": EPS_TOLERANCE,
                    "means_ok": a_mean_ok, "per_trace_bound": bound, "met": a_ok},
        "b_vs_robust": {"by_limit": b_rows, "met": b_ok},
        "c_vs_fixed": {"limit_from_source": limit_src, "margin_from_source": margin_src,
                       "online_qoe_dev_mob": online_qoe, "fixed_qoe_dev_mob": fixed_qoe, "met": c_ok},
        "d_signal_comparison": d_rows,
        "n_playback": {"dev_cv": int(cv["trace_id"].nunique()), "dev_mob": int(mob["trace_id"].nunique()),
                       "dev_mob_calibration": int(mob_cal["trace_id"].nunique())},
        "pass": verdict,
    }
    (OUT / "pilot_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    lines = ["# Development pilot tables", ""]
    for s, data in (("dev_cv", cv), ("dev_mob", mob)):
        lines += [f"## {s}", "", "Baselines", "",
                  fmt(means(data[data["family"] == "baseline"])), "",
                  f"Online margin, signal {sel['signal']}, step {sel['step']:g}, floor {sel['floor']:g}", "",
                  fmt(curves[s]), "",
                  f"Online margin, signal overestimate, step {sel_over['step']:g}, floor {sel_over['floor']:g}", "",
                  fmt(curves_over[s]), "", "Fixed margin", "", fmt(fixed_curve(data)), ""]
        hm = data[(data["family"] == "online_hm") & (data["step"] == sel["step"])]
        lines += ["Online margin on the harmonic mean", "",
                  fmt(hm.groupby("limit")[MEASURES].mean().sort_index()), ""]
    (OUT / "pilot_tables.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    print(json.dumps({k: summary[k] for k in ("selected", "selected_overestimate", "a_limit",
                                              "c_vs_fixed", "d_signal_comparison", "pass")}, indent=1))
    print(pd.DataFrame(b_rows).round(4).T.to_string())


if __name__ == "__main__":
    main()
