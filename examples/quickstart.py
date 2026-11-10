"""Run the online margin on a throughput trace of your own.

The example uses a short synthetic capacity trace. Replace `capacity` with one value per
second in Mbit/s. The harmonic mean of recent segments stands in for a throughput model; to use
your own model, write a class with an estimate(second, throughputs) method.

Usage: python examples/quickstart.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from src.has import load_ladder  # noqa: E402
from src.stall_control import HarmonicMean, MarginController, simulate_controlled  # noqa: E402

LADDER = ROOT / "data" / "ladder" / "segmentByteCostinColumns-bbb-x264-4sec-main.csv"


def main() -> None:
    rng = np.random.default_rng(1)
    capacity = np.clip(rng.lognormal(mean=2.0, sigma=0.9, size=900), 0.0, None)
    ladder = load_ladder(LADDER)
    for level in (0.05, 0.20):
        controller = MarginController(limit=level, step=0.5, floor=0.0, signal="overestimate")
        metrics, _ = simulate_controlled(capacity, 0, ladder.bitrates_kbps, ladder.segment_bits,
                                         HarmonicMean(), controller=controller, seg_s=ladder.segment_s)
        print(f"level {level:.0%}: overestimates {metrics['overestimate_fraction']:.1%}, "
              f"stalls {metrics['stalls']}, average bitrate {metrics['avg_bitrate_mbps']:.1f} Mbit/s, "
              f"mean margin {metrics['margin_mean']:.2f}")


if __name__ == "__main__":
    main()
