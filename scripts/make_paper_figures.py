"""Figures of the article, generated from the result files.

Writes figures/paper/fig1.pdf to fig5.pdf; with --png DIR also writes PNG copies for visual
checks.

Usage: python scripts/make_paper_figures.py [--png DIR]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("pdf")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

from scripts.make_paper_outputs import CONDITIONS, load_rows, per_trace  # noqa: E402

OUT = ROOT / "figures" / "paper"
SUMMARY = ROOT / "results" / "summary"
MM = 1.0 / 25.4
WIDTH = 119.0 * MM
AVAILABLE = {f.name for f in fm.fontManager.ttflist}
FONT = next((n for n in ("Arial", "Liberation Sans", "DejaVu Sans") if n in AVAILABLE), "sans-serif")
plt.rcParams.update({
    "font.family": FONT, "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8, "axes.linewidth": 0.5,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5, "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "lines.linewidth": 0.9, "lines.markersize": 4, "pdf.fonttype": 42, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "savefig.pad_inches": 0.02})
PDF_META = {"CreationDate": None}
GRID = {"color": "#E3E3E3", "lw": 0.4}
BLUE, ORANGE, GREEN, GREY, PURPLE = "#0072B2", "#D55E00", "#009E73", "#4D4D4D", "#CC79A7"
PALETTE = {"process": ("#DAE8FC", "#7EA6E0", "#6C8EBF"), "terminal": ("#F8CECC", "#EA6B66", "#B85450"),
           "decision": ("#D5E8D4", "#97D077", "#82B366"), "highlight": ("#FFF2CC", "#FFD966", "#D6B656")}
P1_LABELS = {"in_domain_4g": "Same\ntype 4G", "in_domain_5g": "Same\ntype 5G",
             "cross_mobility_4g": "Mobility\n4G", "cross_mobility_5g": "Mobility\n5G",
             "cross_tech_4to5": "4G to\n5G", "cross_tech_5to4": "5G to\n4G", "cross_app_5g": "Application\n5G"}


def save(fig, name: str, png: Path | None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", metadata=PDF_META, bbox_inches="tight")
    if png is not None:
        png.mkdir(parents=True, exist_ok=True)
        fig.savefig(png / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def gradient_box(ax, x, y, w, h, kind: str, text: str, rounded: float = 1.0) -> None:
    top, bottom, edge = PALETTE[kind]
    cmap = LinearSegmentedColormap.from_list(kind, [bottom, top])
    box = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rounded}",
                         fc="none", ec=edge, lw=0.7, zorder=3)
    ax.add_patch(box)
    im = ax.imshow(np.linspace(0, 1, 64)[:, None], extent=(x, x + w, y, y + h), origin="lower",
                   cmap=cmap, aspect="auto", zorder=1)
    im.set_clip_path(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="black", fontsize=7, zorder=4)


def diamond(ax, cx, cy, w, h, text: str) -> None:
    top, bottom, edge = PALETTE["decision"]
    cmap = LinearSegmentedColormap.from_list("d", [bottom, top])
    pts = [(cx - w / 2, cy), (cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2)]
    poly = Polygon(pts, closed=True, fc="none", ec=edge, lw=0.7, zorder=3)
    ax.add_patch(poly)
    im = ax.imshow(np.linspace(0, 1, 64)[:, None], extent=(cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2),
                   origin="lower", cmap=cmap, aspect="auto", zorder=1)
    im.set_clip_path(poly)
    ax.text(cx, cy, text, ha="center", va="center", color="black", fontsize=7, zorder=4)


def arrow(ax, a, b, style="arc3,rad=0") -> None:
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=7, lw=0.7, color="#222222",
                                 shrinkA=0, shrinkB=0, connectionstyle=style, zorder=2))


def figure_method(png) -> None:
    fig, ax = plt.subplots(figsize=(WIDTH, 100.0 * MM))
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set_xlim(0, 119)
    ax.set_ylim(0, 100)
    ax.set_axis_off()
    x, w = 1.0, 68.0
    cx = x + w / 2
    rx, rw = 79.0, 39.0
    rc = rx + rw / 2
    gradient_box(ax, x, 89, w, 9, "terminal", "Request for the next video segment", rounded=3.0)
    gradient_box(ax, x, 73, w, 12, "process", "Model predicts the throughput\nof the next segment")
    gradient_box(ax, x, 59, w, 9, "process", "Estimate = prediction × exp(−margin)")
    gradient_box(ax, x, 43, w, 11, "process", "Model predictive control\nchooses the bitrate")
    gradient_box(ax, x, 29, w, 9, "process", "Download segment, measure throughput")
    diamond(ax, cx, 13, 66, 20, "Was the estimate above\nthe measured throughput?")
    gradient_box(ax, rx, 77, rw, 12, "highlight", "Service sets\nthe level")
    gradient_box(ax, rx, 44, rw, 24, "decision", "Yes: margin up by\nstep × (1 − level)\n\nNo: margin down by\nstep × level")
    for y0, y1 in ((89, 85), (73, 68), (59, 54), (43, 38), (29, 23)):
        arrow(ax, (cx, y0), (cx, y1))
    arrow(ax, (rc, 77), (rc, 68))
    arrow(ax, (cx + 33, 13), (rc, 44), style="angle,angleA=0,angleB=90,rad=0")
    arrow(ax, (rx, 63.5), (x + w, 63.5))
    save(fig, "fig1", png)


def figure_coverage(png) -> None:
    df = pd.read_csv(SUMMARY / "main_methods.csv").set_index(["regime", "method"])
    regimes = list(P1_LABELS)
    fig, ax = plt.subplots(figsize=(WIDTH, 58.0 * MM))
    x = np.arange(len(regimes))
    for j, (k, label, color, hatch) in enumerate((("split", "Split CP", BLUE, ""), ("cqr", "CQR", ORANGE, "////"),
                                                  ("aci", "ACI", GREEN, "...."))):
        v = np.array([df.loc[(r, k), "marginal_coverage"] for r in regimes])
        lo = np.array([df.loc[(r, k), "marginal_coverage_ci_lo"] for r in regimes])
        hi = np.array([df.loc[(r, k), "marginal_coverage_ci_hi"] for r in regimes])
        ax.bar(x + (j - 1) * 0.26, v, width=0.25, color=color, hatch=hatch, edgecolor="white", linewidth=0.2,
               label=label, yerr=[v - lo, hi - v], error_kw=dict(elinewidth=0.5, capsize=1.0, capthick=0.5, ecolor="black"))
    ax.axhline(0.90, color="black", ls=(0, (4, 2)), lw=0.7, label="Nominal 0.90")
    ax.set_xticks(x, [P1_LABELS[r] for r in regimes])
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Share of outcomes covered")
    ax.yaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.13), columnspacing=1.2, handlelength=1.8)
    save(fig, "fig2", png)


def figure_delay(png) -> None:
    d = pd.read_csv(SUMMARY / "delay_grid.csv")
    d = d[(d["tag"] == "main") & (d["method"] == "aci")]
    styles = {"cross_tech_4to5": (BLUE, "o"), "cross_mobility_4g": (ORANGE, "s"), "cross_tech_5to4": (GREEN, "^"),
              "in_domain_4g": (PURPLE, "D"), "cross_mobility_5g": (GREY, "v"), "in_domain_5g": ("#56B4E9", "P"),
              "cross_app_5g": ("#E69F00", "X")}
    fig, ax = plt.subplots(figsize=(WIDTH, 58.0 * MM))
    for r, (c, mk) in styles.items():
        g = d[d["regime"] == r].sort_values("delay_s")
        ax.plot(g["delay_s"], 100.0 * g["frac_inf_instance"], color=c, marker=mk, markersize=3.5,
                label=P1_LABELS[r].replace("\n", " "))
    ax.set_xlabel("Reporting delay of throughput feedback (s)")
    ax.set_ylabel("Infinite intervals (%)")
    ax.set_xticks([0, 1, 2, 5, 10])
    ax.yaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1.8)
    save(fig, "fig3", png)


def test_means() -> pd.DataFrame:
    df = load_rows()
    return per_trace(df[df["role"] == "playback"]).groupby(["regime", "variant"], sort=False).mean(numeric_only=True)


def figure_levels(mu: pd.DataFrame, png) -> None:
    conds = list(CONDITIONS)
    markers = ["o", "s", "^", "v", "D", "P", "X"]
    colors = [BLUE, "#56B4E9", ORANGE, "#E69F00", GREEN, PURPLE, GREY]
    fig, ax = plt.subplots(figsize=(WIDTH, 66.0 * MM))
    levels = {"online_0.05": 5.0, "online_0.1": 10.0, "online_0.2": 20.0}
    robust = [100.0 * mu.loc[(r, "robust"), "overestimate_fraction"] for r in conds]
    ax.axhspan(min(robust), max(robust), color="#DDDDDD", zorder=0, lw=0)
    ax.text(-0.42, (min(robust) + max(robust)) / 2, "RobustMPC range", va="center", fontsize=8)
    for i, lv in enumerate(levels.values()):
        ax.plot([i - 0.36, i + 0.36], [lv, lv], color="black", lw=0.9, zorder=2, label="Requested level" if i == 0 else None)
    for j, r in enumerate(conds):
        xs, ys = [], []
        for i, v in enumerate(levels):
            xs.append(i + (j - 3) * 0.1)
            ys.append(100.0 * mu.loc[(r, v), "overestimate_fraction"])
        ax.plot(xs, ys, ls="none", marker=markers[j], color=colors[j], markersize=3.5, label=CONDITIONS[r][1], zorder=3)
    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(0, 24)
    ax.set_xticks([0, 1, 2], ["5", "10", "20"])
    ax.set_xlabel("Requested level (%)")
    ax.set_ylabel("Mean share of segments\nwith an overestimate (%)")
    ax.yaxis.grid(True, **GRID)
    ax.set_axisbelow(True)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), handlelength=1.0)
    save(fig, "fig4", png)


def figure_tradeoff(mu: pd.DataFrame, png) -> None:
    global CURVES, TRACES
    CURVES = pd.read_csv(ROOT / "results" / "stall_control" / "curves" / "curves_rows.csv.gz")
    df = load_rows()
    df = df[(df["role"] == "playback") & (df["variant"] == "robust")]
    TRACES = {r: set(df[df["regime"] == r]["trace_id"]) for r in CONDITIONS}
    conds = list(CONDITIONS)
    fig, axes = plt.subplots(3, 3, figsize=(WIDTH, 118.0 * MM))
    axes = axes.ravel()
    for i, r in enumerate(conds):
        ax = axes[i]
        lv = ["online_0.05", "online_0.1", "online_0.2"]
        ax.plot([mu.loc[(r, v), "avg_bitrate_mbps"] for v in lv], [mu.loc[(r, v), "stalls"] for v in lv],
                color=BLUE, marker="o", markersize=3.5, label="Proposed (levels 5, 10, 20%)")
        ids = sorted(TRACES[r])
        c = CURVES[CURVES["trace_id"].isin(ids) & (CURVES["kind"] == "robust_scaled") & (CURVES["value"] >= 0.5)]
        g = c.groupby("value")[["avg_bitrate_mbps", "stalls"]].mean()
        ax.plot(g["avg_bitrate_mbps"], g["stalls"], color=GREY, lw=0.8, marker=".", markersize=3, label="RobustMPC, scaled discount")
        ax.plot(mu.loc[(r, "online_0.05"), "avg_bitrate_mbps"], mu.loc[(r, "online_0.05"), "stalls"], ls="none",
                marker="o", markersize=5.5, mfc="white", mec=BLUE, mew=0.9, label="Proposed, level 5%", zorder=4)
        for v, col, mk, name, face in (("robust", "black", "s", "RobustMPC", "black"), ("bola", ORANGE, "D", "BOLA", "white")):
            ax.plot(mu.loc[(r, v), "avg_bitrate_mbps"], mu.loc[(r, v), "stalls"], ls="none", marker=mk, color=col,
                    mfc=face, mec=col, mew=0.9, markersize=4, label=name, zorder=2)
        ax.set_title(CONDITIONS[r][1], pad=2.5)
        ax.yaxis.grid(True, **GRID)
        ax.set_axisbelow(True)
        ax.margins(0.12)
        ax.tick_params(pad=1.5)
        if i in (0, 3, 6):
            ax.set_ylabel("Stalls per trace", labelpad=1.5)
        if i >= 4:
            ax.set_xlabel("Average bitrate (Mbit/s)", labelpad=1.5)
    handles, labels = axes[0].get_legend_handles_labels()
    for ax in axes[7:]:
        ax.set_axis_off()
    axes[7].legend(handles, labels, loc="center left", bbox_to_anchor=(-0.05, 0.5), handlelength=1.6, labelspacing=0.7)
    fig.subplots_adjust(hspace=0.42, wspace=0.34)
    save(fig, "fig5", png)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", type=Path, default=None)
    args = ap.parse_args()
    figure_method(args.png)
    figure_coverage(args.png)
    figure_delay(args.png)
    mu = test_means()
    figure_levels(mu, args.png)
    figure_tradeoff(mu, args.png)
    print(f"figures written to {OUT} using font {FONT}")


if __name__ == "__main__":
    main()
