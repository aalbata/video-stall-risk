"""Tests of the online stall controller and of its player loop."""
import math

import numpy as np
import pandas as pd
import pytest

from src.has import METRIC_KEYS, simulate
from src.stall_control import (External, HarmonicMean, MarginController, ModelEstimator,
                               RobustDiscount, bba_choice, bola_choice, capacity_trace,
                               development_traces, load_lumos, replay_rows, segment_features,
                               simulate_controlled, split_folds, training_rows)

LADDER = np.array([237.0, 752.0, 1815.0, 4282.0, 14817.0, 39537.0])


def synthetic_video(rng, n_segments=30):
    base = LADDER * 1000.0 * 4.0
    return np.array([base * rng.uniform(0.7, 1.3) for _ in range(n_segments)])


def synthetic_trace(rng, n=400):
    level = np.exp(rng.normal(1.5, 1.0, size=n // 20 + 1))
    cap = np.repeat(level, 20)[:n] * rng.uniform(0.3, 1.7, size=n)
    cap[rng.uniform(size=n) < 0.05] = 0.0
    return cap


def assert_same_result(a, b, logkeys=("request_s", "rep", "mbit", "finish_s", "buffer_s",
                                      "rebuffer_s", "wait_s")):
    ma, la = a
    mb, lb = b
    for key in METRIC_KEYS:
        va, vb = ma[key], mb[key]
        if isinstance(va, float) and math.isnan(va):
            assert isinstance(vb, float) and math.isnan(vb), key
        else:
            assert va == vb, key
    for key in logkeys:
        assert np.array_equal(la[key], lb[key]), key


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("rule", ["mpc", "rate"])
@pytest.mark.parametrize("name", ["hm", "robust", "point"])
def test_zero_margin_reproduces_reference_player(seed, rule, name):
    rng = np.random.default_rng(seed)
    cap = synthetic_trace(rng)
    video = synthetic_video(rng)
    start = int(rng.integers(0, 12))
    point = cap * rng.uniform(0.5, 1.5, size=len(cap))
    point[rng.uniform(size=len(cap)) < 0.1] = np.nan
    reference = simulate(cap, start, {"point": point}, LADDER, video, rule, name)
    estimator = {"hm": HarmonicMean(), "robust": RobustDiscount(HarmonicMean()),
                 "point": External(point)}[name]
    result = simulate_controlled(cap, start, LADDER, video, estimator, rule=rule)
    assert_same_result(result, reference)


def test_controller_update_and_floor():
    c = MarginController(limit=0.1, step=0.5, floor=-0.02)
    c.update(1.0)
    assert c.margin == pytest.approx(0.45)
    c.margin = 0.0
    c.update(0.0)
    assert c.margin == pytest.approx(-0.02)
    with pytest.raises(ValueError):
        MarginController(limit=0.0, step=0.5)
    with pytest.raises(ValueError):
        MarginController(limit=0.1, step=0.0)
    with pytest.raises(ValueError):
        MarginController(limit=0.1, step=0.1, signal="other")


def test_avoidable_stall_by_hand():
    # Lowest representation 1 Mbit per segment, next 8 Mbit; capacity 1 Mbit/s.
    video = np.array([[1e6, 8e6]] * 3)
    ladder = np.array([250.0, 2000.0])
    cap = np.ones(40)

    class High:
        def estimate(self, second, tputs):
            return 1000.0

    m, log = simulate_controlled(cap, 0, ladder, video, High(), rule="rate", latency_s=0.0,
                                 buffer_s=30.0, mu=1.0)
    # Segment 0: 1 s, buffer 4 s. Segment 1 takes 8 s and stalls 4 s; the lowest
    # representation would take 1 s and not stall.
    assert log["rebuffer_s"][1] == pytest.approx(4.0)
    assert log["avoidable_s"][1] == pytest.approx(4.0)
    assert m["n_decisions"] >= 1
    assert m["stall_event_fraction"] > 0.0


def test_unavoidable_outage_is_not_counted():
    video = np.array([[1e6, 2e6], [1.5e6, 3e6]])
    ladder = np.array([250.0, 500.0])
    # Only 1 Mbit can arrive before a 20-s outage, too little for either representation
    # of the second segment, so both stall until the outage ends.
    cap = np.concatenate(([2.0], np.zeros(20), np.full(30, 1e6)))

    class High:
        def estimate(self, second, tputs):
            return 1e5

    m, log = simulate_controlled(cap, 0, ladder, video, High(), rule="rate", latency_s=0.0,
                                 mu=1.0)
    assert log["rebuffer_s"][1] > 10.0
    assert log["avoidable_s"][1] == pytest.approx(0.0, abs=1e-5)


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("signal", ["stall_time", "stall_event"])
def test_long_run_bound_holds_on_every_trace(seed, signal):
    rng = np.random.default_rng(seed + 100)
    cap = synthetic_trace(rng, n=rng.integers(150, 800))
    video = synthetic_video(rng)
    limit = float(rng.choice([0.005, 0.02, 0.1]))
    step = float(rng.choice([0.1, 0.5, 1.0]))
    floor = float(rng.choice([-0.5, 0.0, -math.inf]))
    wild = np.exp(rng.normal(2.0, 2.0, size=len(cap)))
    ctl = MarginController(limit=limit, step=step, floor=floor, signal=signal)
    m, _ = simulate_controlled(cap, 0, LADDER, video, External(wild), controller=ctl)
    k = m["n_decisions"]
    gap = m["control_loss_mean"] - limit
    assert gap <= (m["margin_final"] - 0.0) / (step * k) + 1e-12
    p_max = float(wild.max())
    margin_safe = max(0.0, math.log(p_max / 0.01))
    assert m["margin_max"] <= margin_safe + step + 1e-9
    assert gap <= (margin_safe + step) / (step * k) + 1e-12


def test_large_margin_selects_lowest_representation():
    rng = np.random.default_rng(3)
    cap = synthetic_trace(rng)
    video = synthetic_video(rng)
    high = np.full(len(cap), 500.0)
    m, log = simulate_controlled(cap, 0, LADDER, video, External(high),
                                 fixed_margin=math.log(500.0 / 0.01))
    assert np.all(log["rep"] == 0)
    assert m["avoidable_s"] == 0.0


def test_training_rows_use_only_earlier_segments():
    radio = np.arange(70.0).reshape(10, 7)
    log = {"request_s": np.array([0.0, 2.5, 5.2, 7.0]),
           "throughput_mbps": np.array([1.0, 2.0, 4.0, np.nan])}
    X, y = training_rows(log, radio)
    assert X.shape == (2, 12)
    assert y.tolist() == pytest.approx([math.log(2.0), math.log(4.0)])
    assert X[0, 0] == 1.0
    assert X[1, 0] == 2.0
    assert X[1, 1] == pytest.approx(2.0 / (1.0 + 0.5))
    assert X[1, 5:].tolist() == radio[5].tolist()


def test_segment_features_window():
    f = segment_features([9.0, 1.0, 1.0, 1.0, 1.0, 2.0], list(range(7)))
    assert f[0] == 2.0
    assert f[3] == 1.0
    assert f[4] == 2.0
    assert f[2] == pytest.approx(6.0 / 5.0)


def test_model_estimator_is_exponential_of_model():
    class Fixed:
        def predict(self, x):
            assert x.shape == (1, 12)
            return np.array([math.log(3.0)])

    est = ModelEstimator(Fixed(), np.zeros((5, 7)))
    assert est.estimate(2, [1.0]) == pytest.approx(3.0)


def test_capacity_trace_removes_rows_outside_download():
    rows = pd.DataFrame({
        "state": ["D", "I", "D", "D", "I", "D"],
        "dl_mbps": [1.0, 0.0, 2.0, np.nan, 0.0, 4.0],
        "RSRP": [-90.0, -91.0, -92.0, -93.0, -94.0, -95.0], "RSRQ": 0.0, "SNR": 0.0,
        "CQI": 0.0, "RSSI": 0.0, "Speed": 0.0, "is_5g_mode": 0.0})
    cap, radio = capacity_trace(rows)
    assert cap.tolist() == [2.0, 0.0, 4.0]
    assert radio[:, 0].tolist() == [-90.0, -92.0, -93.0]


def test_development_draw_is_stratified_and_repeatable():
    table = {"a": [f"a{i}" for i in range(15)], "b": [f"b{i}" for i in range(31)]}
    first = development_traces(table, 0.4, seed=5)
    assert first == development_traces(table, 0.4, seed=5)
    assert sum(x.startswith("a") for x in first) == 6
    assert sum(x.startswith("b") for x in first) == 12


@pytest.mark.parametrize("seed", range(6))
def test_scaled_discount_at_one_is_robustmpc(seed):
    from src.stall_curves import ScaledDiscount
    rng = np.random.default_rng(seed)
    cap, video = synthetic_trace(rng), synthetic_video(rng)
    a = simulate_controlled(cap, 0, LADDER, video, ScaledDiscount(1.0))
    b = simulate_controlled(cap, 0, LADDER, video, RobustDiscount(HarmonicMean()))
    assert_same_result(a, b)
    c = simulate_controlled(cap, 0, LADDER, video, ScaledDiscount(0.0))
    d = simulate_controlled(cap, 0, LADDER, video, HarmonicMean())
    assert_same_result(c, d)


def test_bba_matches_the_published_rule():
    assert bba_choice(4.9, 6) == 0
    assert bba_choice(5.0, 6) == 0
    assert bba_choice(15.0, 6) == 5
    assert bba_choice(30.0, 6) == 5
    assert bba_choice(7.0, 6) == 1
    assert bba_choice(14.99, 6) == 4


def test_bola_prefers_high_quality_only_with_a_full_buffer():
    rates = (LADDER / 1000.0).tolist()
    assert bola_choice(0.0, rates, 30.0, 4.0) == 0
    assert bola_choice(26.0, rates, 30.0, 4.0) == 5
    chosen = [bola_choice(b, rates, 30.0, 4.0) for b in np.linspace(0.0, 26.0, 53)]
    assert chosen == sorted(chosen)


def test_bola_equals_direct_evaluation_of_the_score():
    rates = [0.3, 0.75, 1.2, 1.85, 2.85, 4.3]
    u = [math.log(r / 0.3) for r in rates]
    v = 21.0 / (u[-1] + 5.0)
    for level in (0.0, 3.0, 9.0, 15.0, 20.0):
        scores = [(v * (x + 5.0) - level) / r for x, r in zip(u, rates)]
        assert bola_choice(level, rates, 25.0, 4.0) == int(np.argmax(scores))


@pytest.mark.parametrize("rule", ["bba", "bola"])
def test_buffer_rules_run_without_an_estimator(rule):
    rng = np.random.default_rng(1)
    m, log = simulate_controlled(synthetic_trace(rng), 0, LADDER, synthetic_video(rng), None,
                                 rule=rule)
    assert m["n_segments"] > 0
    assert m["n_decisions"] == 0
    assert np.all(np.isnan(log["estimate_mbps"]))


def test_replay_rows_keeps_every_row():
    rows = pd.DataFrame({
        "state": ["D", "I", "D"], "dl_mbps": [1.0, 0.0, np.nan], "RSRP": [-90.0, -91.0, -92.0],
        "RSRQ": 0.0, "SNR": 0.0, "CQI": 0.0, "RSSI": 0.0, "Speed": 0.0, "is_5g_mode": 0.0})
    cap, radio = replay_rows(rows)
    assert cap.tolist() == [0.0, 0.0]
    assert radio[:, 0].tolist() == [-90.0, -91.0]


def test_lumos_mapping(tmp_path):
    import zipfile
    csv = ("run_num,seq_num,movingSpeed,nrStatus,lte_rssi,lte_rsrp,lte_rsrq,lte_rssnr,"
           "nr_ssRsrp,nr_ssRsrq,nr_ssSinr,Throughput,mobility_mode\n"
           "2,2.0,1.0,CONNECTED,-61,-94,-14,2147483647,-80,-10,20,300,walking\n"
           "2,1.0,2.0,NOT_RESTRICTED,-62,-95,-15,5,,,,100,walking\n"
           "1,1.0,0.5,CONNECTED,-63,-96,-16,6,,,,0,driving\n")
    path = tmp_path / "x.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("d/Lumos5G-v1.0.csv", csv)
    df = load_lumos(path)
    assert df["trace_id"].tolist() == ["Lumos5G/driving/run_001", "Lumos5G/walking/run_002",
                                       "Lumos5G/walking/run_002"]
    first, second = df.iloc[1], df.iloc[2]
    assert first["dl_mbps"] == 100.0 and first["RSRP"] == -95.0 and first["is_5g_mode"] == 0.0
    assert first["Speed"] == pytest.approx(7.2)
    assert second["RSRP"] == -80.0 and second["SNR"] == 20.0 and second["is_5g_mode"] == 1.0
    assert df.iloc[0]["RSRP"] == -96.0
    assert df["CQI"].isna().all()
    sentinel = load_lumos(path)
    assert sentinel.iloc[1]["SNR"] == 5.0


def test_folds_partition_the_identifiers():
    ids = [f"t{i}" for i in range(53)]
    folds = split_folds(ids, 5, seed=1)
    joined = sorted(x for v in folds.values() for x in v)
    assert joined == sorted(ids)
    assert max(len(v) for v in folds.values()) - min(len(v) for v in folds.values()) <= 1
