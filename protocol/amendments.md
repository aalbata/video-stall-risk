# Protocol amendments

The original protocol (`preregistered_protocol.md`, `protocol.json`, hashes in
`protocol_hashes.json`) is unchanged. Terminology: a "trace" in this amendment is one
drive-test recording, called a "session" in the original protocol.

## Amendment 1 (2026-10-21)

### 1.1 Outcomes examined before this amendment

The following quantities were computed from the existing outputs in `results/locked/`
and examined before this amendment was written. They are reported as post hoc
descriptive analyses:
finite-interval coverage derived from stored coverage and infinite-interval fractions;
finite-interval mean width; instance-level and per-trace infinite-interval fractions;
speed-group coverage in every regime; the spread of per-trace coverage; mean width with
infinite widths replaced by a cap; the stored per-trace median interval scores; and the
share of zero-throughput targets by regime.

No outcome of the analyses specified in 1.4 to 1.8 (feedback delay, corrected 5-s
horizon, timestamp sensitivity, positive-throughput sensitivity, adaptive-streaming
simulation, mean Winkler score, finite-interval median width) had been computed when
this amendment was written.

### 1.2 Deviations from the original protocol

1. The step-size sensitivity of Section 8c was run with gamma in {0.01, 0.02}, not the
   specified {0.01, 0.05}; gamma = 0.05 is the primary value. The grid as run is reported.
2. The width-ratio confidence intervals of H4 and the group-coverage confidence intervals
   of H5 were not produced in the original analysis. The 500-instance group filter of H5
   excludes no group (the smallest speed group has 788 test instances in every seed).
3. The Winkler interval score was not part of the original protocol. It is added in 1.5.
4. Targets and the trailing window are defined on the row index of each trace (nominal
   1 Hz). For h = 1, 85.8% of targets lie exactly 1 s after the prediction time. The
   confirmatory analysis is unchanged; 1.7 adds a timestamp-based sensitivity analysis.
5. Seeds determine the trace-level splits only. The gradient-boosting models are
   deterministic for a given training set because early stopping is disabled.

### 1.3 Instance-level re-execution of the main and 5-s cells

The 140 main cells (7 regimes, seeds 0-19, gradient boosting, alpha = 0.10,
gamma = 0.05, h = 1) and the 10 cells of the 5-s horizon ablation (in_domain_5g and
cross_tech_4to5, seeds 0-4) are re-executed with code that also records the quantities
specified below. Acceptance criterion: for every (cell, method, trace) the trace length
n equals the locked value and coverage and infinite-interval fraction agree with the
locked values to within 1e-12. If the criterion fails, execution stops and no new
outcome is examined until the cause is identified and recorded here.

### 1.4 Feedback delay

Label-arrival model. For the instance issued at row t of a trace, with timestamp tau(t)
and horizon h, the label is the throughput at row t + h. It becomes available at time
tau(t + h) + D, where D >= 0 is an additional reporting delay in seconds. Before issuing
the interval at time tau(j), ACI and Mondrian-ACI apply the update
alpha <- alpha + gamma (alpha_nominal - err_i), in order of arrival (ties in issue
order), for every earlier instance i of the same trace whose label has arrived
(tau(t_i + h) + D <= tau(j)) and has not yet been applied. Labels that arrive after the
last instance of a trace are not applied. With h = 1 and D = 0 this reproduces the
sequencing of the locked runs, which 1.3 verifies.

Grid. D in {0, 1, 2, 5, 10} s at h = 1, all 7 regimes, seeds 0-19, alpha = 0.10,
gamma = 0.05, for ACI and Mondrian-ACI (the other methods do not use feedback).
Corrected 5-s horizon: the 10 cells of 1.3 at h = 5 with D = 0 under this model, so
labels arrive 5 rows after issue; reported beside the immediate-feedback results.

Recorded per trace: coverage, infinite-interval fraction, the quantities of 1.5, the
absolute coverage deviation, the maximum number of issued predictions whose labels were
outstanding at any issue time, and the numbers of issue times with alpha_t <= 0 and with
alpha_t >= 1, and the number of intervals issued with alpha_t >= 1 that covered their
target. The deterministic long-run bound evaluated at the recorded maximum is reported
per trace. Analysis is descriptive: means with 95% percentile bootstrap confidence
intervals over traces (10,000 resamples, bootstrap seed 0).

### 1.5 Finite intervals and the Winkler score

For every method and regime of the main cells, and of the cells in 1.4:
- infinite-interval fraction, at instance level (pooled within a seed, then averaged over
  seeds) and as the mean of per-trace fractions;
- finite-interval coverage, marginal (pooled over finite intervals within a seed, then
  averaged over seeds) and as the mean of seed-averaged per-trace values;
- finite-interval width: the median across traces of the seed-averaged per-trace median
  finite width, and the same with the per-trace mean finite width;
- Winkler score, Eq. (7) of the manuscript, computed per instance for finite intervals;
  per-trace mean over finite intervals, averaged over seeds, reported as the median across
  traces (primary) and the mean across traces. No cap is applied to infinite intervals;
  their fraction is reported alongside;
- coverage in every speed group of every regime, with 95% percentile bootstrap
  confidence intervals over the 20 seed-level values, and the worst-group coverage.
For the ablation rows of the original Section 8, finite-interval coverage is computed
exactly from the stored per-trace coverage and infinite-interval fractions.

### 1.6 Zero-throughput targets

The share of targets equal to 0 Mbit/s is reported for every regime, and marginal
coverage restricted to instances with a positive target is reported for every method
and regime of the main cells.

### 1.7 Timestamp sensitivity

Features and targets are rebuilt on timestamps: the target of the instance at time
tau(t) is the throughput of the last row whose timestamp equals tau(t) + h (instances
without such a row are dropped); the trailing window contains the rows with timestamps
in (tau(t) - 10 s, tau(t)]; at least 10 s of history is required. All 7 methods,
7 regimes, seeds 0-4, h = 1, D = 0. Reported: marginal coverage and infinite-interval
fraction.

### 1.8 Adaptive-streaming simulation

Traces. Only traces recorded during bulk downloads represent available capacity: all 4G
traces and the 5G Download traces. The 5G Netflix and Amazon Prime traces reflect the
players' own on/off demand and are excluded; the application-shift regime therefore has
no streaming evaluation. Regimes: in_domain_4g, in_domain_5g, cross_mobility_4g,
cross_mobility_5g, cross_tech_4to5, cross_tech_5to4, with the models, calibration sets and
seeds 0-19 of the main cells; the simulated traces are the eligible test traces of each
cell.

Time base. One row of a trace is one second of capacity at that row's downlink
throughput, as for the predictor. Download time follows from integrating capacity over
seconds; each segment request adds 80 ms of latency.

Video. Big Buck Bunny, x264, 4-s segments, with the per-segment sizes of the UCC 4K DASH
dataset; six representations of 237, 752, 1815, 4282, 14817 and 39537 kbit/s (the
available representations nearest to a geometric sequence between the lowest and the
highest). Segment sizes repeat cyclically when a trace outlasts the video.

Player. Buffer capacity 30 s. The first segment is fetched at the lowest representation
and playback starts when it is downloaded. When the buffer is full the player waits until
one segment of space is free. Playback runs from the first instance of the trace to the
end of the trace; an incomplete final download is discarded.

Throughput estimates at a request issued during second s (the most recent instance at or
before s is used): point prediction; lower bound of split CP; lower bound of ACI; lower
bound of Mondrian-ACI (all from the main configuration, h = 1, D = 0); harmonic mean of
the last five segment throughputs; and the RobustMPC estimate, the harmonic mean divided
by one plus the maximum relative error of the last five harmonic-mean estimates. Before
any segment has completed, the lowest representation is used. Estimates below
0.01 Mbit/s, including the zero lower bound of an infinite interval, are set to
0.01 Mbit/s.

Rules. Rate-based: the highest representation whose bitrate does not exceed the
estimate (the lowest if none). MPC: exhaustive search over the next five segments that
maximises the QoE below with the estimate held constant, executing the first decision.
Variants: rate-based with harmonic mean, point prediction, split CP, ACI and
Mondrian-ACI bounds; MPC with harmonic mean, RobustMPC, point prediction, split CP, ACI
and Mondrian-ACI bounds.

QoE (linear form of Yin et al., SIGCOMM 2015): sum of segment bitrates in Mbit/s, minus
the sum of absolute bitrate changes between consecutive segments, minus mu times the
rebuffering time in seconds, minus mu_s times the startup delay, with mu = mu_s = 39.537
(the highest bitrate in Mbit/s), normalised per segment.

Metrics per trace: average bitrate (Mbit/s), rebuffering time (s), rebuffering ratio
(rebuffering time divided by playback plus rebuffering time), number of stalls after
startup, startup delay (s), quality switches per minute of playback, mean absolute
bitrate change per switch (Mbit/s), and QoE per segment.

Statistics. Per-trace metrics are averaged over the seeds in which the trace was tested.
All variants are reported with means and 95% percentile bootstrap confidence intervals
over traces. Pre-specified paired two-sided Wilcoxon signed-rank tests on per-trace QoE,
Benjamini-Hochberg corrected as one family of 12 tests, with matched-pairs rank-biserial
effect sizes: within the MPC family, Mondrian-ACI bound versus ACI bound, versus split CP
bound, and versus RobustMPC, in cross_mobility_4g, cross_mobility_5g, cross_tech_4to5 and
cross_tech_5to4. Results are reported whatever their direction.

Verification. The simulator is checked against hand-computed outcomes on synthetic
traces, and its rate-based rule is compared with an independent reference implementation
(Sabre) on identical synthetic inputs.

### 1.9 Unchanged

No other method, regime, seed, base model, tuning parameter or hypothesis is added or
changed. The original confirmatory family, its tests and its results are unchanged and
reported.

## Amendment 2 (2026-11-08)

### 2.1 What was known when this amendment was written

The outcomes of amendment 1 are known for all 156 capacity traces, including the finding
that the lower bounds of the interval methods attain lower QoE than RobustMPC in the four
shifted regimes. That finding motivated the method below, which is a new proposal and is
not part of the earlier analyses. Those analyses stand unchanged.

Before this amendment, three descriptive quantities were examined for the new design: the
share and run lengths of rows outside the downloading state, the ordering of segment sizes
across representations, and the time of one model prediction. No outcome of the method
below had been computed when this amendment was written.

### 2.2 Development and test traces

The development traces are 40% of the 4G traces in each mobility class, drawn by
scripts/make_stall_partition.py with seed 20261108 and stored in
protocol/stall_development_traces.json (53 traces). The other 82 4G traces, all 21 5G
Download traces and any external dataset form the test pool. The pilot uses development
traces only, for training, tuning and playback. Outcomes of the new method on test-pool
traces are computed only after the method, its settings and the test plan have been fixed
in a later amendment.

### 2.3 Replay

Rows outside the downloading state are removed before replay. They are concentrated in the
train traces (34% of their rows), occur in repeated runs of one to two minutes with radio
readings present and carry almost no throughput, so they describe a client that is not
transferring data rather than the capacity of the link. Rows in the downloading state with
zero throughput stay and are replayed as zero capacity. A test-pool sensitivity analysis in
which the removed rows are replayed as zero capacity is planned.

With the kept rows indexed 0 to n-1, second s of the replay has the throughput of row s+1 as
capacity, and a request issued during second s sees the radio readings of row s. Playback
starts at second 0. The ladder, segment duration, buffer, latency, estimate floor, MPC
horizon and QoE weights are those of 1.8.

### 2.4 Predictor

The player predicts the throughput of the next segment from quantities it can observe when
it issues the request: the throughput of the last segment; the harmonic mean, mean, minimum
and maximum of the throughputs of the last five segments; and the current RSRP, RSRQ, SNR,
CQI, RSSI, speed and 5G-mode indicator. Missing radio values are replaced by the medians of
the training rows. The target is the logarithm of the realized segment throughput, and the
prediction is its exponential. The model is the histogram gradient-boosting regressor of
the main analysis (squared error, 300 iterations, learning rate 0.1, no early stopping). It
is trained on one row per completed request after the first, from RobustMPC replayed on the
training traces.

### 2.5 Method

The estimate used by MPC is prediction * exp(-margin), floored at 0.01 Mbit/s. The margin
starts at 0. After each completed segment that had an estimate,

    margin <- max(floor, margin + step * (loss - limit)).

The avoidable stall a of a segment is max(s - s_low, 0), where s is its stall and s_low the
stall that the lowest representation would have caused if requested at the same time with
the same buffer; a is 0 when the lowest representation was requested. Signals:
stall_time, loss = min(a / 4 s, 1); stall_event, loss = 1 if a > 0 and 0 otherwise;
overestimate, loss = 1 if the estimate exceeds the realized segment throughput and 0
otherwise. The overestimate signal is the comparator that calibrates on a statistical event
rather than on stalls.

For every trace, the mean loss over the K updates minus limit is at most
margin_final / (step * K). When the prediction is at most p_max, the margin cannot exceed
max(0, ln(p_max / 0.01)) + step, because at that margin the estimate equals the floor and
MPC requests the lowest representation, for which a = 0.

### 2.6 Compared variants (MPC throughout)

Baselines: RobustMPC; harmonic mean; the segment model with the RobustMPC discount.
Fixed margin on the segment model: -0.25, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.25,
1.5. Online margin on the segment model: signals stall_time and stall_event with limit in
{0.002, 0.005, 0.01, 0.02, 0.04}, step in {0.1, 0.25, 0.5} and floor in {-0.5, 0}; signal
overestimate with level in {0.05, 0.1, 0.2, 0.3, 0.4} and the same steps and floors. Online
margin on the harmonic mean: signal stall_time, the same limits and steps, floor -0.5.

### 2.7 Pilot settings

dev_cv: the development traces are split into five folds; for each fold the model is
trained on the other four and every trace of the fold is played. dev_mob: the static and
pedestrian development traces are the source and the car, bus and train development traces
the target. Of the source traces, 75% train the model and 25% are calibration traces used
only for tuning in 2.8(c). Fold and split seed 20261108. The model is deterministic for a
given training set, so one run is made for each cell.

### 2.8 Selection and pass rule

Selection. The proposed configuration is the combination of signal (stall_time or
stall_event), step and floor with the highest mean over limits of the mean QoE per segment
across dev_cv playback traces. The overestimate comparator receives its own step and floor
in the same way.

The pilot passes if all of the following hold for the selected configuration.
(a) Limit: on dev_mob playback traces, the mean of the controlled signal is at most limit +
0.005 at every limit, and the per-trace inequality of 2.5 holds for every played trace.
(b) Against RobustMPC: at one limit, used in both settings, the mean rebuffering ratio is
at most that of RobustMPC and the mean QoE per segment is higher than that of RobustMPC, in
both dev_cv and dev_mob.
(c) Against a fixed margin under change: on dev_mob, the limit and the fixed margin are each
chosen by highest mean QoE per segment on the calibration traces, and the online method then
has mean QoE per segment on the playback traces at least equal to that of the fixed margin.
The comparison of the stall signals with the overestimate signal is reported but does not
decide the pilot.

If the pilot fails, the method is not carried to the test pool and no test-pool outcome of
it is computed. Means are taken across played traces. This is a development analysis; its
numbers are not confirmatory.

## Amendment 3 (2026-11-08)

### 3.1 Pilot outcome and change of method

The pilot of amendment 2 failed its pass rule. On dev_mob the mean stall_event fraction at
limit 0.002 was 0.0084 against the 0.007 allowed by 2.8(a), and 2.8(b) was met only at that
limit. The stall-signal method is therefore not carried to the test pool, as 2.8 requires.

The overestimate signal, a pre-specified comparator of 2.6, had the higher best QoE in both
development settings. It is adopted here as the proposed method, with the step (0.5) and
floor (0) selected for it by the rule of 2.8. Level 0.05 is the primary level because it had
the highest mean QoE per segment of the five levels in both development settings; levels
0.10 and 0.20 are reported as secondary points of the operating curve. This change was made
after development results were seen. No test-pool outcome of any method of amendments 2 or 3
had been computed when this amendment was written.

### 3.2 Test data

Test-pool traces: the 82 4G traces outside the development set, the 21 5G Download traces and
the 118 runs of Lumos5G-v1.0 (Narayanan et al., IMC 2020; 1 Hz iPerf TCP downlink on
commercial mmWave 5G in Minneapolis; CC BY 4.0; archive SHA-256
1ea8770b3090735f987d4ef7b248188de7c667bf6be5716e4891daf9e8d331e8). Before this amendment only
the format of Lumos5G was examined: its files, columns, missing-value shares, run lengths and
the distribution of throughput. Each run is one trace. When the device is on 5G (nrStatus
CONNECTED), RSRP, RSRQ and SNR come from the NR columns if present and otherwise from the LTE
columns; RSSI is the LTE value; speed is converted from m/s to km/h; CQI is not available and
takes the training median; 5G mode is nrStatus CONNECTED; values reported as unavailable are
missing. Throughput is taken in Mbit/s.

### 3.3 Regimes

Each cell has training, calibration and test traces. Calibration traces are used only to tune
the fixed-margin baseline and to calibrate the one-step baseline of 3.5.
in_domain_4g: source the 53 development traces, test the 82 pool traces.
in_domain_5g: the 21 5G Download traces in five folds; each fold is tested with the other four
as source.
cross_mobility_4g: source all static and pedestrian 4G traces; test the car, bus and train
pool traces (54).
cross_mobility_5g: source the static 5G Download traces (5); test the driving ones (16).
cross_tech_4to5: source all 135 4G traces; test the 21 5G Download traces.
cross_tech_5to4: source the 21 5G Download traces; test the 82 pool traces.
external_lumos5g: source the 156 Irish capacity traces; test the 118 Lumos5G runs.
No development trace appears in any test set.

Replay, player and predictor are those of 2.3 and 2.4.

### 3.4 Splits and repetition

What is random is the assignment of source traces to training and calibration, and the fold
assignment; the models are deterministic for a given training set. Split seeds 0 to 4 are used.
For each seed the sorted source identifiers are shuffled with numpy.random.default_rng(seed)
and the first round(0.75 n) train the models. Folds of in_domain_5g use the same seed.
Per-trace metrics are averaged over the seeds. The full design has 55 cells.

### 3.5 Compared variants (MPC unless stated)

Proposed: segment model with the online margin (signal overestimate, step 0.5, floor 0, start
0) at levels 0.05 (primary), 0.10 and 0.20.
Baselines: RobustMPC; harmonic mean in MPC; rate-based rule with the harmonic mean; BBA with
reservoir 5 s and cushion 10 s and a representation index linear in the buffer (Mao et al.,
2017); BOLA-BASIC with logarithmic utilities and gamma p = 5 (Spiteri et al.); the segment model
without a margin; the segment model with the RobustMPC discount; the segment model with a fixed
margin chosen from {0.2, 0.4, 0.6, 0.8, 1.0} by highest mean QoE on the calibration traces, ties
to the smaller margin; and the earlier approach, the lower bound of two-sided ACI (level 0.10,
step 0.05, immediate feedback) on the one-step per-second model, floored at 0.01 Mbit/s.

### 3.6 Outcomes and statistics

The replication unit is the trace. Primary family: per-trace QoE per segment, proposed method
at level 0.05 against RobustMPC, paired two-sided Wilcoxon signed-rank test in each of the seven
regimes, Benjamini-Hochberg over the seven tests. Secondary families, each adjusted over the
seven regimes: rebuffering ratio, stalls and average bitrate against RobustMPC; QoE against each
of the segment model with the RobustMPC discount, BOLA, BBA, the earlier approach, the fixed
margin, the harmonic mean in MPC and the segment model without a margin; stalls against the
segment model with the RobustMPC discount. Effect sizes are matched-pairs rank-biserial
correlations. Means across traces carry 95% percentile bootstrap intervals over traces (10,000
resamples, seed 0). Also reported: the realized share of overestimates at each level and the
per-trace inequality of 2.5 for every played trace.

### 3.7 Claim rule

In a regime, the proposed method is said to have higher QoE than RobustMPC if the adjusted
p-value is below 0.05 and the median paired difference is positive, lower if the adjusted p-value
is below 0.05 and the median difference is negative, and no different otherwise. Results are
reported for every regime whichever way they fall.

### 3.8 Sensitivity

For the Irish test traces, the proposed method at level 0.05, RobustMPC, the segment model with
the RobustMPC discount and the earlier approach are also replayed with every row kept, rows
outside the downloading state at their measured throughput. The models of the main analysis are
used. The same comparison of QoE against RobustMPC is reported.

## Amendment 4 (2026-11-08)

The outcomes of amendment 3 had been seen when this amendment was written. The analyses below
are exploratory. They do not change the primary or secondary analyses of amendment 3, the
method or its settings.

4.1 Operating curves of baselines. On the test traces of amendment 3, RobustMPC is replayed with
its discount scaled by beta in {0, 0.25, 0.5, 1, 1.5, 2, 3, 5}, the estimate being the harmonic
mean divided by (1 + beta * largest relative error of the last five estimates). beta = 1 is
RobustMPC and beta = 0 the harmonic mean. The stalls and QoE of the scaled curve are read by
linear interpolation at the mean bitrate of the proposed method at level 0.05 in each condition.

4.2 Value of the trained model. The harmonic mean is discounted by the online margin of
amendment 3 (signal overestimate, step 0.5, floor 0) at levels 0.05, 0.10 and 0.20.

4.3 Stall weight. The stored QoE of the main analysis is rescored with the rebuffering weight
multiplied by 2, 4 and 8, without replanning, and the per-trace comparison of the proposed method
at level 0.05 with RobustMPC is repeated in each condition, with Benjamini-Hochberg adjustment over
the conditions at each weight.
