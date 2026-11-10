# Managing throughput overestimation risk for video streaming

Code and results for the article "Managing Throughput Overestimation Risk for Video Streaming on Changing Cellular Networks".

A video player that overestimates throughput stalls. This package gives a player one safety margin. The margin discounts a per-segment throughput prediction and is updated after every segment, so that the estimate is too high at a rate that the service sets. The method needs no retraining when the network changes, and each update is one line of arithmetic.

The package also reproduces every table and figure of the article.

## Quick start

Tested on Windows 11, Intel Core Ultra 7 155U, Python 3.12.10.

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python reproduce.py
```

`reproduce.py` regenerates the summaries, tables and figures from the shipped result files and checks each file against `SHA256SUMS`. It prints PASS or FAIL per file.

## Use it on your own traces

`examples/quickstart.py` runs the rule on a throughput trace. Replace the synthetic trace with one value per second in Mbit/s. To use your own model, write a class with an `estimate(second, throughputs)` method.

```python
from src.stall_control import HarmonicMean, MarginController, simulate_controlled

controller = MarginController(limit=0.05, step=0.5, floor=0.0, signal="overestimate")
metrics, log = simulate_controlled(capacity, 0, ladder.bitrates_kbps, ladder.segment_bits,
                                   HarmonicMean(), controller=controller, seg_s=ladder.segment_s)
```

`limit` is the risk level, the long-run share of segments whose estimate may be too high. A lower level gives fewer overestimates and lower bitrate. Data stay on your computer.

## Results of the final test

The rule at level 5% against RobustMPC, on traces held out from its development. "n.s." means not significantly different after Benjamini-Hochberg adjustment.

| Condition | Traces | Stalls per trace (rule / RobustMPC) | Bitrate, Mbit/s (rule / RobustMPC) | QoE (rule / RobustMPC) | QoE result |
|---|---|---|---|---|---|
| 4G same | 82 | 1.42 / 2.55 | 9.7 / 10.9 | 2.03 / 1.17 | n.s. |
| 5G same | 21 | 2.14 / 2.71 | 12.7 / 15.7 | 7.70 / 9.65 | lower |
| 4G vehicles | 54 | 1.53 / 3.00 | 9.5 / 11.1 | -0.28 / -1.75 | n.s. |
| 5G driving | 16 | 1.49 / 2.19 | 9.2 / 12.2 | 4.36 / 6.59 | lower |
| 4G to 5G | 21 | 1.44 / 2.71 | 12.3 / 15.7 | 7.52 / 9.65 | lower |
| 5G to 4G | 82 | 1.42 / 2.55 | 8.8 / 10.9 | 1.11 / 1.17 | lower |
| mmWave | 118 | 0.08 / 0.07 | 37.4 / 35.5 | 36.05 / 33.52 | higher |

Columns: Traces, the number of test traces. Stalls per trace, the mean number of playback stalls. Bitrate, the mean nominal bitrate of the played segments. QoE, the mean quality of experience per segment, the sum of bitrates minus bitrate changes minus the rebuffering and startup penalties, per segment; higher is better. QoE result, from a paired two-sided Wilcoxon signed-rank test per condition.

The full tables are in `results/stall_control/test/` and `results/paper/`. The rule does not improve the combined QoE in general, which was lower than that of RobustMPC in four of the seven conditions. In an exploratory comparison, RobustMPC with a scaled discount reaches a similar balance of stalls and bitrate, but its scale has to be retuned for the mmWave network to keep the same overestimation rate; see `results/stall_control/curves/`.

## Reproduce everything from the public datasets

```
python reproduce.py --full
```

This downloads the public datasets, rebuilds the features and reruns all studies. It takes several hours on a laptop CPU and resumes if interrupted. It was run step by step during the study; the combined command was not rerun from this package.

## Contents

- `src/`: methods, player simulation and statistics. `src/stall_control.py` holds the online margin.
- `scripts/`: run and analysis scripts.
- `protocol/`: the written protocol and its dated amendments.
- `results/`: per-trace results and summaries.
- `figures/paper/`: the figures of the article.
- `tests/`: unit tests. Run `python -m pytest`.

## Data

The 4G and 5G traces are downloaded by `scripts/download_data.py`. Sources and licences are listed in `data/README.md`. Lumos5G is included under its CC BY 4.0 licence.

## Licence and citation

MIT licence, see `LICENSE`. Citation details are in `CITATION.cff`.
