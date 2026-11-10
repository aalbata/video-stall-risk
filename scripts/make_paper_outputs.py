"""Numbers and tables of the article, generated from the result files.

Reads results/summary/ (interval-method study) and results/stall_control/test/ (final test
of the online margin) and writes results/paper/macros.tex and results/paper/tab_*.tex.
Every placeholder of a table template must be filled exactly once.

Usage: python scripts/make_paper_outputs.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loading import read_cell_rows  # noqa: E402
from src.stats import bh_correct, bootstrap_ci_mean, paired_wilcoxon  # noqa: E402

SUMMARY = ROOT / "results" / "summary"
TEST = ROOT / "results" / "stall_control" / "test"
PILOT = ROOT / "results" / "stall_control" / "pilot"
CURVES = ROOT / "results" / "stall_control" / "curves" / "curves_rows.csv.gz"
OUT = ROOT / "results" / "paper"

P1_REGIMES = ["in_domain_4g", "in_domain_5g", "cross_mobility_4g", "cross_mobility_5g",
              "cross_tech_4to5", "cross_tech_5to4", "cross_app_5g"]
P1_LABELS = ["Same 4G", "Same 5G", "Mobility 4G", "Mobility 5G", "4G to 5G", "5G to 4G",
             "App. 5G"]
P1_METHODS = {"gaussian": "Gaussian", "quantile_raw": "Quantile regression", "split": "Split CP",
              "cqr": "CQR", "mondrian": "Mondrian", "aci": "ACI", "mondrian_aci": "Mondrian-ACI"}
CONDITIONS = {"in_domain_4g": ("Idfour", "4G same"),
              "in_domain_5g": ("Idfive", "5G same"),
              "cross_mobility_4g": ("Mobfour", "4G vehicles"),
              "cross_mobility_5g": ("Mobfive", "5G driving"),
              "cross_tech_4to5": ("Techfive", "4G to 5G"),
              "cross_tech_5to4": ("Techfour", "5G to 4G"),
              "external_lumos5g": ("Lumos", "mmWave")}
SHORT = {r: v[1] for r, v in CONDITIONS.items()}
IRISH = [r for r in CONDITIONS if r != "external_lumos5g"]
PRIMARY = "online_0.05"
VARIANT_LABELS = {"robust": "RobustMPC", "hm": "MPC, harmonic mean", "rate_hm": "Rate-based",
                  "bba": "BBA", "bola": "BOLA", "old_aci": "Two-sided ACI bound",
                  "model": "Model, no margin", "model_robust": "Model, RobustMPC discount",
                  "fixed_tuned": "Model, fixed margin", "online_0.05": "Proposed, level 5\\%",
                  "online_0.1": "Proposed, level 10\\%", "online_0.2": "Proposed, level 20\\%"}
COMPARATORS = ["model_robust", "bola", "bba", "old_aci", "fixed_tuned", "hm", "model"]
MEASURES = ["qoe_per_segment", "rebuffer_ratio", "avg_bitrate_mbps", "stalls", "switches_per_min",
            "overestimate_fraction", "margin_mean", "top_fraction", "n_decisions"]


def load_rows() -> pd.DataFrame:
    """Rows of the final test from the combined file or the cell files."""
    combined = TEST / "test_rows.csv.gz"
    if combined.exists():
        return pd.read_csv(combined)
    files = sorted((TEST / "cells").glob("*.csv"))
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def fill(template: str, values: dict) -> str:
    """Replace every @@key@@ exactly once; no placeholder may remain or go unused."""
    for key, value in values.items():
        token = f"@@{key}@@"
        if template.count(token) != 1:
            raise ValueError(f"{token} occurs {template.count(token)} times")
        template = template.replace(token, str(value))
    if re.search(r"@@\w+@@", template):
        raise ValueError(f"unfilled placeholder: {re.search(r'@@\w+@@', template).group(0)}")
    return template


def p_text(p: float) -> str:
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def signed(x: float, d: int = 2) -> str:
    text = f"{abs(x):.{d}f}"
    return f"$-${text}" if x < 0 and float(text) != 0 else text


def part_one(m: dict) -> str:
    """Macros of the interval-method study; returns the table of coverage and width."""
    df = pd.read_csv(SUMMARY / "main_methods.csv").set_index(["regime", "method"])
    groups = pd.read_csv(SUMMARY / "main_groups.csv").set_index(["regime", "method", "group"])
    delay = pd.read_csv(SUMMARY / "delay_grid.csv")
    delay = delay[delay["tag"] == "main"]
    audit = json.loads((SUMMARY / "audit.json").read_text(encoding="utf-8"))["data_audit"]
    cov = lambda r, k: float(df.loc[(r, k), "marginal_coverage"])
    inf = lambda r, k: 100.0 * float(df.loc[(r, k), "frac_inf_instance"])

    m["nTracesAll"] = audit["n_traces"]
    m["nTracesFourG"] = audit["n_traces_4g"]
    m["nTracesFiveG"] = audit["n_traces_5g"]
    m["nInstances"] = f"{audit['n_instances']:,}".replace(",", "{,}")
    m["covSplitTechFive"] = f"{cov('cross_tech_4to5', 'split'):.3f}"
    m["covSplitTechFivePct"] = f"{100 * cov('cross_tech_4to5', 'split'):.1f}"
    m["covCqrTechFive"] = f"{cov('cross_tech_4to5', 'cqr'):.3f}"
    m["covSplitTechFour"] = f"{cov('cross_tech_5to4', 'split'):.3f}"
    m["covSplitMobFour"] = f"{cov('cross_mobility_4g', 'split'):.3f}"
    m["covSplitApp"] = f"{cov('cross_app_5g', 'split'):.3f}"
    m["covSplitMobFive"] = f"{cov('cross_mobility_5g', 'split'):.3f}"
    m["covSplitIdFour"] = f"{cov('in_domain_4g', 'split'):.3f}"
    m["covSplitIdFive"] = f"{cov('in_domain_5g', 'split'):.3f}"
    m["widthSplitApp"] = f"{float(df.loc[('cross_app_5g', 'split'), 'width_finite_median']):.1f}"
    m["widthAciApp"] = f"{float(df.loc[('cross_app_5g', 'aci'), 'width_finite_median']):.1f}"
    m["covGroupStillTechFive"] = f"{float(groups.loc[('cross_tech_4to5', 'split', 'speed_0'), 'coverage']):.3f}"
    m["covGroupStillTechFivePct"] = f"{100 * float(groups.loc[('cross_tech_4to5', 'split', 'speed_0'), 'coverage']):.1f}"
    locked = read_cell_rows(ROOT / "results" / "locked" / "locked_rows.csv.gz")
    locked = locked[(locked["tag"] == "main") & (locked["base_model"] == "gbm") & (locked["alpha"] == 0.1)]
    sid = locked["trace_id"].str.lower()
    locked = locked.assign(download=sid.str.contains("download"), five=sid.str.startswith("5g"))

    def by_app(regime: str, method: str, column: str, download: bool) -> float:
        """Instance-weighted value over the 5G test traces of one kind, pooled per seed, then averaged."""
        x = locked[(locked["regime"] == regime) & (locked["method"] == method) & locked["five"]
                   & (locked["download"] == download)]
        g = x.assign(w=x[column] * x["n"]).groupby("seed")[["w", "n"]].sum()
        return float((g["w"] / g["n"]).mean())

    m["covSplitIdFiveDl"] = f"{by_app('in_domain_5g', 'split', 'coverage', True):.3f}"
    m["covSplitIdFiveSt"] = f"{by_app('in_domain_5g', 'split', 'coverage', False):.3f}"
    m["covSplitMobFiveDl"] = f"{by_app('cross_mobility_5g', 'split', 'coverage', True):.3f}"
    m["covSplitTechFiveDl"] = f"{by_app('cross_tech_4to5', 'split', 'coverage', True):.3f}"
    m["infAciTechFiveDl"] = f"{100.0 * by_app('cross_tech_4to5', 'aci', 'frac_inf', True):.1f}"
    same5 = locked[(locked["regime"] == "in_domain_5g") & locked["five"]]
    m["nFiveGStreaming"] = int(same5.loc[~same5["download"], "trace_id"].nunique())
    tests = pd.read_csv(SUMMARY / "locked_tests.csv")
    closer = (tests["p_bh"] < 0.05) & (tests["median_diff"] < 0)
    conf = tests["family"] == "confirmatory"
    m["nConfirmCloser"] = int((conf & closer).sum())
    m["nConfirmTotal"] = int(conf.sum())
    m["nMaciCloserAci"] = int(((tests["family"] == "secondary") & (tests["method_b"] == "aci") & closer).sum())
    aci_cov = [cov(r, "aci") for r in P1_REGIMES]
    m["covAciMin"], m["covAciMax"] = f"{min(aci_cov):.3f}", f"{max(aci_cov):.3f}"
    m["infAciTechFive"] = f"{inf('cross_tech_4to5', 'aci'):.1f}"
    m["infAciMobFour"] = f"{inf('cross_mobility_4g', 'aci'):.1f}"
    m["infMaciMobFour"] = f"{inf('cross_mobility_4g', 'mondrian_aci'):.1f}"
    fin = [float(df.loc[(r, "aci"), "finite_coverage"]) for r in P1_REGIMES]
    m["finCovAciMin"] = f"{min(fin):.3f}"
    more_inf = sum(inf(r, "mondrian_aci") > inf(r, "aci") for r in P1_REGIMES)
    m["nRegimesMoreInf"] = more_inf
    m["maxCovDiffAciMaci"] = f"{max(abs(cov(r, 'aci') - cov(r, 'mondrian_aci')) for r in P1_REGIMES):.4f}"
    d = delay[(delay["method"] == "aci")]
    frac = lambda r, s: 100.0 * float(d[(d["regime"] == r) & (d["delay_s"] == s)]["frac_inf_instance"].iloc[0])
    m["infAciTechFiveDten"] = f"{frac('cross_tech_4to5', 10.0):.1f}"
    m["infAciMobFourDten"] = f"{frac('cross_mobility_4g', 10.0):.1f}"
    dd = d[d["delay_s"] == 10.0]
    m["finCovAciDtenMin"] = f"{dd['finite_coverage'].min():.3f}"
    m["covAciDelayMin"] = f"{d['marginal_coverage'].min():.3f}"
    m["covAciDelayMax"] = f"{d['marginal_coverage'].max():.3f}"

    rows = []
    for k, label in P1_METHODS.items():
        cells = [f"{cov(r, k):.3f}" for r in P1_REGIMES]
        rows.append(label + " & " + " & ".join(cells) + r" \\")
    top = ["", "Same type", "Same type", "Mobility", "Mobility", "4G to", "5G to", "Application"]
    bottom = ["Method", "4G", "5G", "4G", "5G", "5G", "4G", "5G"]
    head = " & ".join(top) + r" \\" + "\n" + " & ".join(bottom) + r" \\"
    return ("\\begin{tabular}{@{}l" + "c" * 7 + "@{}}\n\\toprule\n" + head + "\n\\midrule\n"
            + "\n".join(rows) + "\n\\botrule\n\\end{tabular}\n")


def per_trace(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(["regime", "variant", "trace_id"], sort=False)[MEASURES].mean().reset_index()


def means(tr: pd.DataFrame) -> pd.DataFrame:
    return tr.groupby(["regime", "variant"], sort=False)[MEASURES].mean()


def diff_ci(tr: pd.DataFrame, regime: str, a: str, b: str, metric: str) -> tuple:
    x = tr[(tr["regime"] == regime) & (tr["variant"] == a)].set_index("trace_id")[metric]
    y = tr[(tr["regime"] == regime) & (tr["variant"] == b)].set_index("trace_id")[metric]
    return bootstrap_ci_mean((x - y.loc[x.index]).to_numpy())


def exploratory(tr: pd.DataFrame, df: pd.DataFrame, get) -> dict:
    """Exploratory analyses of amendment 4; returns macros and stores the matched table."""
    out: dict = {}
    cur = pd.read_csv(CURVES)
    ids = {r: sorted(tr[(tr["regime"] == r) & (tr["variant"] == "robust")]["trace_id"]) for r in CONDITIONS}
    rows, beta5, over_two, gap, stalls_low, qoe_high, hm_gap, hm_over = [], {}, [], [], 0, 0, [], []
    for r, (_, label) in CONDITIONS.items():
        c = cur[cur["trace_id"].isin(ids[r])]
        rob = c[c["kind"] == "robust_scaled"].groupby("value")[["avg_bitrate_mbps", "stalls", "qoe_per_segment", "overestimate_fraction"]].mean()
        x = rob["avg_bitrate_mbps"].to_numpy()
        order = np.argsort(x)
        br = get(r, PRIMARY, "avg_bitrate_mbps")
        st = float(np.interp(br, x[order], rob["stalls"].to_numpy()[order]))
        q = float(np.interp(br, x[order], rob["qoe_per_segment"].to_numpy()[order]))
        rate = 100.0 * rob["overestimate_fraction"].to_numpy()[::-1]
        beta5[r] = float(np.interp(5.0, rate, rob.index.to_numpy()[::-1]))
        over_two.append(100.0 * float(rob.loc[2.0, "overestimate_fraction"]))
        hm = c[(c["kind"] == "hm_margin") & (c["value"] == 0.05)][["avg_bitrate_mbps", "stalls", "qoe_per_segment", "overestimate_fraction"]].mean()
        hm_over.append(100.0 * float(hm["overestimate_fraction"]))
        stalls_low += st < get(r, PRIMARY, "stalls")
        qoe_high += q >= get(r, PRIMARY, "qoe_per_segment")
        hm_gap.append(get(r, PRIMARY, "qoe_per_segment") - float(hm["qoe_per_segment"]))
        rows.append(f"{label} & {br:.1f} & {get(r, PRIMARY, 'stalls'):.2f} & {signed(get(r, PRIMARY, 'qoe_per_segment'))} "
                    f"& {st:.2f} & {signed(q)} & {hm['avg_bitrate_mbps']:.1f} & {hm['stalls']:.2f} & {signed(float(hm['qoe_per_segment']))} \\\\")
    MATCHED["tab_matched"] = ("\\begin{tabular}{@{}lrrrrrrrr@{}}\n\\toprule\n"
                              "& \\multicolumn{3}{c}{Proposed, level 5\\%} & \\multicolumn{2}{c}{Scaled RobustMPC} & \\multicolumn{3}{c}{Harmonic mean with margin} \\\\\n"
                              "Condition & Bitrate & Stalls & QoE & Stalls & QoE & Bitrate & Stalls & QoE \\\\\n\\midrule\n"
                              + "\n".join(rows) + "\n\\botrule\n\\end{tabular}\n")
    irish = [beta5[r] for r in IRISH]
    out["betaFiveIrishMin"], out["betaFiveIrishMax"] = f"{min(irish):.1f}", f"{max(irish):.1f}"
    out["betaFiveLumos"] = f"{beta5['external_lumos5g']:.1f}"
    out["overBetaTwoMin"], out["overBetaTwoMax"] = f"{min(over_two):.1f}", f"{max(over_two):.1f}"
    out["overBetaTwoSpread"] = f"{round(max(over_two), 1) - round(min(over_two), 1):.1f}"
    two = dict(zip(CONDITIONS, over_two))
    irish_two = [two[r] for r in IRISH]
    out["overBetaTwoIrishMin"], out["overBetaTwoIrishMax"] = f"{min(irish_two):.1f}", f"{max(irish_two):.1f}"
    out["overBetaTwoLumos"] = f"{two['external_lumos5g']:.1f}"
    five = [100.0 * get(r, PRIMARY, "overestimate_fraction") for r in CONDITIONS]
    out["overFiveSpread"] = f"{round(max(five), 1) - round(min(five), 1):.1f}"
    out["nMatchedStallsLower"] = int(stalls_low)
    out["nMatchedQoeHigher"] = int(qoe_high)
    out["hmGapMax"] = f"{max(hm_gap):.1f}"
    out["nHmHigher"] = sum(g < 0 for g in hm_gap)
    out["overHmFiveMin"], out["overHmFiveMax"] = f"{min(hm_over):.1f}", f"{max(hm_over):.1f}"

    pairs = tr[tr["variant"] == PRIMARY].set_index(["regime", "trace_id"])
    rates = pairs["overestimate_fraction"] * 100.0
    out["nDistinctTraces"] = int(tr[tr["variant"] == PRIMARY]["trace_id"].nunique())
    out["nTracePairs"] = len(rates)
    out["overFiveTraceMedian"] = f"{rates.median():.1f}"
    out["overFiveTraceNinety"] = f"{rates.quantile(0.9):.1f}"
    out["overFiveTraceMax"] = f"{rates.max():.1f}"
    out["overFiveTraceMaxK"] = f"{pairs['n_decisions'].loc[rates.idxmax()]:.0f}"
    out["overFiveShareTen"] = f"{100.0 * float((rates <= 10.0).mean()):.1f}"

    main = df[df["role"] == "playback"]
    counts = {}
    for mult in (2, 4, 8):
        recs = []
        for r in CONDITIONS:
            a = main[(main["regime"] == r) & (main["variant"] == PRIMARY)]
            b = main[(main["regime"] == r) & (main["variant"] == "robust")]
            qa = (a["qoe_per_segment"] - (mult - 1) * 39.537 * a["rebuffer_s"] / a["n_segments"]).groupby(a["trace_id"]).mean()
            qb = (b["qoe_per_segment"] - (mult - 1) * 39.537 * b["rebuffer_s"] / b["n_segments"]).groupby(b["trace_id"]).mean()
            res = paired_wilcoxon(qa.to_numpy(), qb.loc[qa.index].to_numpy())
            recs.append({"r": r, "p": res["p"], "d": res["median_diff"]})
        _, adj = bh_correct([x["p"] for x in recs])
        counts[mult] = {"higher": sum(p < 0.05 and x["d"] > 0 for x, p in zip(recs, adj) if x["r"] in IRISH),
                        "lower": sum(p < 0.05 and x["d"] < 0 for x, p in zip(recs, adj) if x["r"] in IRISH)}
    out["nRescoreTwoLower"] = counts[2]["lower"]
    out["nRescoreFourHigher"] = counts[4]["higher"]
    out["nRescoreEightHigher"] = counts[8]["higher"]
    return out


MATCHED: dict = {}


def part_two(m: dict) -> dict:
    """Macros of the final test; returns the table bodies."""
    s = json.loads((TEST / "test_summary.json").read_text(encoding="utf-8"))
    df = load_rows()
    main = df[df["role"] == "playback"]
    tr = per_trace(main)
    mu = means(tr)
    get = lambda r, v, c: float(mu.loc[(r, v), c])
    prim = {x["regime"]: x for x in s["primary_qoe_vs_robust"]}
    sec = {k: {x["regime"]: x for x in v} for k, v in s["secondary_vs_robust"].items()}
    cmp_ = {k: {x["regime"]: x for x in v} for k, v in s["qoe_vs_comparators"].items()}
    stall_mr = {x["regime"]: x for x in s["stalls_vs_model_robust"]}

    n_test = {r: int(prim[r]["n"]) for r in CONDITIONS}
    m["nTestFourG"] = n_test["in_domain_4g"]
    m["nTestFiveG"] = n_test["in_domain_5g"]
    m["nTestLumos"] = n_test["external_lumos5g"]
    m["nTestAll"] = n_test["in_domain_4g"] + n_test["in_domain_5g"] + n_test["external_lumos5g"]
    for r, (key, _) in CONDITIONS.items():
        m[f"nTest{key}"] = n_test[r]

    counts = s["verdict_counts"]
    m["nQoeHigher"], m["nQoeLower"], m["nQoeSame"] = counts["higher"], counts["lower"], counts["no difference"]

    sig = [r for r in CONDITIONS if sec["stalls"][r]["p_bh"] < 0.05 and sec["stalls"][r]["median_diff"] < 0]
    red = [100.0 * (1.0 - get(r, PRIMARY, "stalls") / get(r, "robust", "stalls")) for r in sig]
    m["nStallsFewer"] = len(sig)
    m["stallCutMin"], m["stallCutMax"] = f"{min(red):.0f}", f"{max(red):.0f}"
    loss = [100.0 * (1.0 - get(r, PRIMARY, "avg_bitrate_mbps") / get(r, "robust", "avg_bitrate_mbps")) for r in IRISH]
    m["bitrateLossMin"], m["bitrateLossMax"] = f"{min(loss):.0f}", f"{max(loss):.0f}"
    r = "external_lumos5g"
    m["bitrateGainLumos"] = f"{100.0 * (get(r, PRIMARY, 'avg_bitrate_mbps') / get(r, 'robust', 'avg_bitrate_mbps') - 1.0):.0f}"
    sig_reb = [r for r in CONDITIONS if sec["rebuffer_ratio"][r]["p_bh"] < 0.05 and sec["rebuffer_ratio"][r]["median_diff"] < 0]
    m["nRebufferLower"] = len(sig_reb)

    for name, v in (("Five", "online_0.05"), ("Ten", "online_0.1"), ("Twenty", "online_0.2")):
        values = [100.0 * get(r, v, "overestimate_fraction") for r in CONDITIONS]
        m[f"over{name}Min"], m[f"over{name}Max"] = f"{min(values):.1f}", f"{max(values):.1f}"
    excess = [100.0 * get(r, v, "overestimate_fraction") - lv for r in CONDITIONS
              for v, lv in (("online_0.05", 5.0), ("online_0.1", 10.0), ("online_0.2", 20.0))]
    m["overExcessMax"] = f"{max(excess):.1f}"
    values = [100.0 * get(r, "robust", "overestimate_fraction") for r in CONDITIONS]
    m["overRobustMin"], m["overRobustMax"] = f"{min(values):.1f}", f"{max(values):.1f}"
    bound = s["per_trace_bound"]
    m["boundRows"] = f"{bound['n_rows']:,}".replace(",", "{,}")
    m["boundViolations"] = bound["n_violations"]
    d = df[df["variant"].isin(["online_0.05", "online_0.1", "online_0.2"]) & (df["role"] == "playback")]
    right = d["margin_final"] / (0.5 * d["n_decisions"])
    m["boundRightMedianPct"] = f"{100.0 * right.median():.1f}"
    m["boundRightMedianFivePct"] = f"{100.0 * right[d['variant'] == 'online_0.05'].median():.1f}"
    m["nDecisionsMedian"] = f"{tr[tr['variant'] == PRIMARY]['n_decisions'].median():.0f}"

    margin4 = [get(r, PRIMARY, "margin_mean") for r in ("in_domain_4g", "cross_mobility_4g", "cross_tech_5to4")]
    margin5 = [get(r, PRIMARY, "margin_mean") for r in ("in_domain_5g", "cross_mobility_5g", "cross_tech_4to5")]
    m["marginFourMin"], m["marginFourMax"] = f"{min(margin4):.2f}", f"{max(margin4):.2f}"
    m["marginFiveMin"], m["marginFiveMax"] = f"{min(margin5):.2f}", f"{max(margin5):.2f}"
    m["marginLumos"] = f"{get('external_lumos5g', PRIMARY, 'margin_mean'):.2f}"
    m["factorFiveMin"] = f"{100.0 * np.exp(-round(max(margin5), 2)):.0f}"
    m["factorFiveMax"] = f"{100.0 * np.exp(-round(min(margin5), 2)):.0f}"

    gap = [get(r, PRIMARY, "qoe_per_segment") - get(r, "old_aci", "qoe_per_segment") for r in CONDITIONS]
    m["gapOldMin"], m["gapOldMax"] = f"{min(gap):.1f}", f"{max(gap):.1f}"
    m["nOldBeaten"] = sum(cmp_["old_aci"][r]["p_bh"] < 0.05 and cmp_["old_aci"][r]["median_diff"] > 0 for r in CONDITIONS)
    m["qoeLumosHm"] = f"{get('external_lumos5g', 'hm', 'qoe_per_segment'):.1f}"
    m["qoeLumosNew"] = f"{get('external_lumos5g', PRIMARY, 'qoe_per_segment'):.1f}"
    m["qoeLumosRobust"] = f"{get('external_lumos5g', 'robust', 'qoe_per_segment'):.1f}"
    m["topLumosRobust"] = f"{100.0 * get('external_lumos5g', 'robust', 'top_fraction'):.0f}"
    m["topLumosHm"] = f"{100.0 * get('external_lumos5g', 'hm', 'top_fraction'):.0f}"
    m["nStallsFewerMr"] = sum(stall_mr[r]["p_bh"] < 0.05 and stall_mr[r]["median_diff"] < 0 for r in CONDITIONS)
    mr = cmp_["model_robust"]
    m["nMrLower"] = sum(mr[r]["p_bh"] < 0.05 and mr[r]["median_diff"] < 0 for r in CONDITIONS)
    m["nMrHigher"] = sum(mr[r]["p_bh"] < 0.05 and mr[r]["median_diff"] > 0 for r in CONDITIONS)
    m["nMrSame"] = len(CONDITIONS) - int(m["nMrLower"]) - int(m["nMrHigher"])
    bo = cmp_["bola"]
    m["nBolaHigher"] = sum(bo[r]["p_bh"] < 0.05 and bo[r]["median_diff"] > 0 for r in CONDITIONS)
    m["nBolaSame"] = len(CONDITIONS) - int(m["nBolaHigher"]) - sum(bo[r]["p_bh"] < 0.05 and bo[r]["median_diff"] < 0 for r in CONDITIONS)
    ba = cmp_["bba"]
    m["nBbaHigher"] = sum(ba[r]["p_bh"] < 0.05 and ba[r]["median_diff"] > 0 for r in CONDITIONS)
    m["nBbaLower"] = sum(ba[r]["p_bh"] < 0.05 and ba[r]["median_diff"] < 0 for r in CONDITIONS)
    fx = cmp_["fixed_tuned"]
    m["nFixedHigher"] = sum(fx[r]["p_bh"] < 0.05 and fx[r]["median_diff"] > 0 for r in CONDITIONS)
    m["nFixedLower"] = sum(fx[r]["p_bh"] < 0.05 and fx[r]["median_diff"] < 0 for r in CONDITIONS)
    m["nFixedSame"] = len(CONDITIONS) - int(m["nFixedHigher"]) - int(m["nFixedLower"])
    m["qoeFiveGTwentyId"] = f"{get('in_domain_5g', 'online_0.2', 'qoe_per_segment'):.2f}"
    m["qoeFiveGRobustId"] = f"{get('in_domain_5g', 'robust', 'qoe_per_segment'):.2f}"
    m["qoeFourGFiveId"] = f"{get('in_domain_4g', 'online_0.05', 'qoe_per_segment'):.2f}"
    m["qoeFiveGFiveId"] = f"{get('in_domain_5g', 'online_0.05', 'qoe_per_segment'):.2f}"
    m["qoeFourGTwentyId"] = f"{get('in_domain_4g', 'online_0.2', 'qoe_per_segment'):.2f}"

    idle = {x["regime"]: x for x in s["idle_as_zero"]}
    m["nIdleSameVerdict"] = sum(idle[r]["verdict"] == prim[r]["verdict"] for r in IRISH)
    m["nIdleRegimes"] = len(IRISH)

    pilot = json.loads((PILOT / "pilot_summary.json").read_text(encoding="utf-8"))
    a = pilot["a_limit"]["mean_fraction_by_limit_dev_mob"]
    m["pilotStallObserved"] = f"{100.0 * a['0.002']:.2f}"
    m["pilotStallAllowed"] = f"{100.0 * (0.002 + pilot['a_limit']['tolerance']):.2f}"
    m["pilotStallLimit"] = "0.2"

    # Table of the main comparison, one row per condition.
    row_tpl = ("@@label@@ & @@n@@ & @@sn@@ / @@sr@@ & @@sp@@ & @@bn@@ / @@br@@ & @@bp@@ & @@rn@@ / @@rr@@ & @@rp@@ "
               "& @@qn@@ / @@qr@@ & @@qm@@ & @@qd@@ @@qci@@ & @@qp@@ & @@rb@@ & @@res@@ \\\\")
    rows = []
    for r, (_, label) in CONDITIONS.items():
        mean_d, lo, hi = diff_ci(tr, r, PRIMARY, "robust", "qoe_per_segment")
        rows.append(fill(row_tpl, {
            "label": label, "n": n_test[r],
            "sn": f"{get(r, PRIMARY, 'stalls'):.2f}", "sr": f"{get(r, 'robust', 'stalls'):.2f}",
            "sp": p_text(sec["stalls"][r]["p_bh"]),
            "bn": f"{get(r, PRIMARY, 'avg_bitrate_mbps'):.1f}", "br": f"{get(r, 'robust', 'avg_bitrate_mbps'):.1f}",
            "bp": p_text(sec["avg_bitrate_mbps"][r]["p_bh"]),
            "rn": f"{100.0 * get(r, PRIMARY, 'rebuffer_ratio'):.2f}", "rr": f"{100.0 * get(r, 'robust', 'rebuffer_ratio'):.2f}",
            "rp": p_text(sec["rebuffer_ratio"][r]["p_bh"]),
            "qn": signed(get(r, PRIMARY, "qoe_per_segment")), "qr": signed(get(r, "robust", "qoe_per_segment")),
            "qm": signed(prim[r]["median_diff"]), "qd": signed(mean_d), "qci": f"[{signed(lo)}, {signed(hi)}]",
            "qp": p_text(prim[r]["p_bh"]), "rb": signed(prim[r]["rank_biserial"]),
            "res": prim[r]["verdict"].replace("no difference", "n.s.")}))
    main_table = ("\\begin{tabular}{@{}lrcrcrcrcrcrrl@{}}\n\\toprule\n"
                  "Condition & $n$ & Stalls & $p$ & Bitrate & $p$ & Rebuffering (\\%) & $p$ & QoE & Median diff. & Mean diff. [95\\% CI] & $p$ & $r_{\\mathrm{rb}}$ & Result \\\\\n"
                  "\\midrule\n" + "\n".join(rows) + "\n\\botrule\n\\end{tabular}\n")

    # Mean QoE of every variant in every condition.
    order = list(VARIANT_LABELS)
    body = []
    for v in order:
        body.append(VARIANT_LABELS[v] + " & " + " & ".join(signed(get(r, v, "qoe_per_segment")) for r in CONDITIONS) + r" \\")
    qoe_table = ("\\begin{tabular}{@{}l" + "r" * 7 + "@{}}\n\\toprule\n"
                 + "Estimator or rule & " + " & ".join(SHORT[r] for r in CONDITIONS) + " \\\\\n\\midrule\n"
                 + "\n".join(body) + "\n\\botrule\n\\end{tabular}\n")

    # Result of the proposed rule at level 5% against each comparator.
    mark = lambda x: "higher" if x["p_bh"] < 0.05 and x["median_diff"] > 0 else ("lower" if x["p_bh"] < 0.05 and x["median_diff"] < 0 else "n.s.")
    body = ["RobustMPC & " + " & ".join(mark(prim[r]) for r in CONDITIONS) + r" \\"]
    for c in COMPARATORS:
        body.append(VARIANT_LABELS[c] + " & " + " & ".join(mark(cmp_[c][r]) for r in CONDITIONS) + r" \\")
    tests_table = ("\\begin{tabular}{@{}l" + "c" * 7 + "@{}}\n\\toprule\n"
                   + "Comparator & " + " & ".join(SHORT[r] for r in CONDITIONS) + " \\\\\n\\midrule\n"
                   + "\n".join(body) + "\n\\botrule\n\\end{tabular}\n")

    # Test conditions.
    m.update(exploratory(tr, df, get))
    src = {"in_domain_4g": "53 development 4G traces", "in_domain_5g": "Other folds of 5G download traces",
           "cross_mobility_4g": "All static and pedestrian 4G traces", "cross_mobility_5g": "5 static 5G download traces",
           "cross_tech_4to5": "All 135 4G traces", "cross_tech_5to4": "21 5G download traces",
           "external_lumos5g": "156 Irish capacity traces"}
    tgt = {"in_domain_4g": "Held-out 4G traces", "in_domain_5g": "Held-out fold, 5G download",
           "cross_mobility_4g": "Held-out car, bus and train 4G traces", "cross_mobility_5g": "Driving 5G download traces",
           "cross_tech_4to5": "5G download traces", "cross_tech_5to4": "Held-out 4G traces",
           "external_lumos5g": "Lumos5G runs"}
    body = [f"{CONDITIONS[r][1]} & {src[r]} & {tgt[r]} & {n_test[r]} \\\\" for r in CONDITIONS]
    cond_table = ("\\begin{tabular}{@{}lllr@{}}\n\\toprule\nCondition & Training and calibration & Test & $n$ \\\\\n\\midrule\n"
                  + "\n".join(body) + "\n\\botrule\n\\end{tabular}\n")
    return {"tab_main": main_table, "tab_qoe": qoe_table, "tab_tests": tests_table, "tab_conditions": cond_table, **MATCHED}


WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
         8: "eight", 9: "nine", 10: "ten"}


def extras(m: dict) -> None:
    """Measured costs, run times and small counts written as words."""
    cost = json.loads((OUT / "cost.json").read_text(encoding="utf-8"))
    m["costTrainS"] = f"{cost['train_seconds']:.1f}"
    m["costTrainRows"] = f"{cost['n_training_rows']:,}".replace(",", "{,}")
    m["costPredictMs"] = f"{cost['predict_ms']:.1f}"
    m["costUpdateUs"] = f"{cost['update_us']:.1f}"
    m["costModelKib"] = f"{cost['model_kib']:,.0f}".replace(",", "{,}")
    for folder, key in ((PILOT, "runPilotMin"), (TEST, "runTestMin")):
        text = (folder / "run_log.txt").read_text(encoding="utf-8")
        m[key] = re.search(r"finished in ([0-9.]+) min", text).group(1)
    dev = json.loads((ROOT / "protocol" / "stall_development_traces.json").read_text(encoding="utf-8"))
    m["nDevTraces"] = dev["n_development_traces"]
    audit = json.loads((SUMMARY / "audit.json").read_text(encoding="utf-8"))["data_audit"]
    m["nCapacityIrish"] = audit["n_traces_streaming_eligible"]
    m["nFiveGDownload"] = audit["n_traces_5g_download"]
    for key in ("nStallsFewer", "nQoeHigher", "nQoeLower", "nQoeSame", "nRebufferLower", "nMrHigher",
                "nMrLower", "nMrSame", "nBolaHigher", "nBolaSame", "nBbaHigher", "nBbaLower", "nOldBeaten",
                "nRegimesMoreInf", "nIdleSameVerdict", "nIdleRegimes", "nStallsFewerMr", "nMatchedStallsLower",
                "nMatchedQoeHigher", "nHmHigher", "nRescoreTwoLower", "nRescoreFourHigher", "nRescoreEightHigher",
                "nFixedHigher", "nFixedLower", "nFixedSame", "nConfirmCloser", "nConfirmTotal", "nMaciCloserAci"):
        m[key + "W"] = WORDS[int(m[key])]
    same, total = int(m["nIdleSameVerdict"]), int(m["nIdleRegimes"])
    m["idleAgreeText"] = f"all {WORDS[total]}" if same == total else f"{WORDS[same]} of the {WORDS[total]}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    m: dict = {}
    tables = {"tab_intervals": part_one(m)}
    tables.update(part_two(m))
    extras(m)
    if any(not re.fullmatch(r"[A-Za-z]+", k) for k in m):
        raise ValueError("macro names must be letters only")
    lines = [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items())]
    (OUT / "macros.tex").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for name, text in tables.items():
        (OUT / f"{name}.tex").write_text(text, encoding="utf-8", newline="\n")
    (OUT / "values.json").write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(f"{len(m)} macros and {len(tables)} tables written to {OUT}")


if __name__ == "__main__":
    main()
