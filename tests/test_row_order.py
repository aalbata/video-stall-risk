"""Tests for the recorded row order of the trace loader (src/data_loading.py)."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loading import (ORDER_RECORDED, ORDER_STABLE_SORT, ROW_ORDER_FILE,  # noqa: E402
                              ROW_ORDER_SHA256, discover_traces, load_all, load_trace,
                              read_row_order)

# seconds after the first row; rows 1-3, 5-6 and 8-9 share a timestamp, row 7 is out of order
OFFSETS = [0, 1, 1, 1, 2, 4, 4, 3, 5, 5, 6, 7]


def _write_trace(root: Path, name: str = "A_t0", offsets=OFFSETS) -> str:
    """One 4G trace whose DL_bitrate is 1000 times the file position of the row."""
    d = root / "4G" / "Dataset" / "car"
    d.mkdir(parents=True, exist_ok=True)
    n = len(offsets)
    ts = pd.Timestamp("2020-01-01 10:00:00") + pd.to_timedelta(offsets, unit="s")
    pd.DataFrame({"Timestamp": ts.strftime("%Y.%m.%d_%H.%M.%S"),
                  "Speed": np.arange(n), "DL_bitrate": np.arange(n) * 1000,
                  "State": "D", "NetworkMode": "LTE"}).to_csv(d / f"{name}.csv", index=False)
    return f"4G/car/{name}"


def _positions(df: pd.DataFrame) -> list[int]:
    return [int(round(x)) for x in df["dl_mbps"]]


def _stable(offsets) -> list[int]:
    return list(np.argsort(np.asarray(offsets), kind="stable"))


def _ties_reversed(offsets) -> list[int]:
    """Timestamp order with the rows of each tied group in reverse file order."""
    pos = np.arange(len(offsets))
    return list(np.lexsort((-pos, np.asarray(offsets))))


def _write_order_file(path: Path, order: dict) -> str:
    text = "{\n" + ",\n".join(f"{json.dumps(k)}:{json.dumps([int(i) for i in v])}"
                              for k, v in sorted(order.items())) + "\n}\n"
    with open(path, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh,
                                               mtime=0) as gz:
        gz.write(text.encode("ascii"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_recorded_order_applied(tmp_path):
    tid = _write_trace(tmp_path / "raw")
    order = _ties_reversed(OFFSETS)
    assert order != _stable(OFFSETS)
    path = tmp_path / "row_order.json.gz"
    digest = _write_order_file(path, {tid: order})
    rec = read_row_order(path, sha256=digest)
    assert list(rec) == [tid] and rec[tid].tolist() == order

    (meta,) = discover_traces(tmp_path / "raw")
    df = load_trace(meta, rec)
    assert df.attrs["row_order"] == ORDER_RECORDED
    assert _positions(df) == order
    assert df["timestamp"].is_monotonic_increasing
    assert list(df.index) == list(range(len(OFFSETS)))
    assert df["Speed"].tolist() == [float(i) for i in order]

    raw = load_all(tmp_path / "raw", min_rows=1, row_order=rec)
    assert raw.attrs["row_order"] == {"traces_recorded_order": 1, "traces_stable_sort": []}
    assert _positions(raw) == order

    with pytest.raises(ValueError, match="SHA-256"):
        read_row_order(path, sha256="0" * 64)
    assert read_row_order(tmp_path / "absent.json.gz") == {}


def test_stable_sort_fallback(tmp_path):
    tid = _write_trace(tmp_path / "raw")
    other = _write_trace(tmp_path / "raw", name="A_t1", offsets=[0, 0, 1, 1, 2])
    (m0, m1) = discover_traces(tmp_path / "raw")
    assert (m0.trace_id, m1.trace_id) == (tid, other)

    df = load_trace(m0, {})
    assert df.attrs["row_order"] == ORDER_STABLE_SORT
    assert _positions(df) == _stable(OFFSETS)
    assert _positions(df) == [0, 1, 2, 3, 4, 7, 5, 6, 8, 9, 10, 11]

    raw = load_all(tmp_path / "raw", min_rows=1,
                   row_order={other: _ties_reversed([0, 0, 1, 1, 2])})
    assert raw.attrs["row_order"] == {"traces_recorded_order": 1, "traces_stable_sort": [tid]}
    assert _positions(raw[raw.trace_id == tid]) == _stable(OFFSETS)
    assert _positions(raw[raw.trace_id == other]) == [1, 0, 3, 2, 4]


def test_mismatched_order_rejected(tmp_path):
    tid = _write_trace(tmp_path / "raw")
    (meta,) = discover_traces(tmp_path / "raw")
    order = _ties_reversed(OFFSETS)
    for wrong in (order[:-1], order + [len(order)]):
        df = load_trace(meta, {tid: wrong})
        assert df.attrs["row_order"] == ORDER_STABLE_SORT
        assert _positions(df) == _stable(OFFSETS)
        raw = load_all(tmp_path / "raw", min_rows=1, row_order={tid: wrong})
        assert raw.attrs["row_order"]["traces_stable_sort"] == [tid]

    with pytest.raises(ValueError, match="timestamps decrease"):
        load_trace(meta, {tid: list(range(len(OFFSETS)))})
    with pytest.raises(ValueError, match="not a permutation"):
        load_trace(meta, {tid: [0] * len(OFFSETS)})
    bad = tmp_path / "bad.json.gz"
    bad.write_bytes(gzip.compress(json.dumps({tid: [0.5, 1]}).encode("ascii")))
    with pytest.raises(ValueError, match="list of integers"):
        read_row_order(bad, sha256=None)


def test_shipped_row_order_file():
    assert ROW_ORDER_FILE.parent.name == "data" and ROW_ORDER_FILE.is_file()
    assert hashlib.sha256(ROW_ORDER_FILE.read_bytes()).hexdigest() == ROW_ORDER_SHA256
    rec = read_row_order()
    assert len(rec) == 218
    assert sum(1 for t in rec if t.startswith("4G/")) == 135
    assert sum(1 for t in rec if t.startswith("5G/")) == 83
    assert sum(len(p) for p in rec.values()) == 363234
    for pos in rec.values():
        assert np.array_equal(np.sort(pos), np.arange(len(pos)))


def test_stable_sort_fallback_many_ties(tmp_path):
    """Fallback order of a trace with many tied timestamps in scattered file order: rows
    that share a timestamp keep their file order, which the default (unstable) sort of
    pandas does not guarantee for an input of this size."""
    offsets = [(7 * i) % 25 for i in range(200)]
    tid = _write_trace(tmp_path / "raw", name="A_t2", offsets=offsets)
    expected = sorted(range(len(offsets)), key=lambda i: (offsets[i], i))
    (meta,) = discover_traces(tmp_path / "raw")
    df = load_trace(meta, {})
    assert df.attrs["row_order"] == ORDER_STABLE_SORT
    assert _positions(df) == expected
    raw = load_all(tmp_path / "raw", min_rows=1, row_order={})
    assert raw.attrs["row_order"] == {"traces_recorded_order": 0, "traces_stable_sort": [tid]}
    assert _positions(raw) == expected
