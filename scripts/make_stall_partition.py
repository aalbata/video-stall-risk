"""Write the development traces of the online stall controller (protocol amendment 2).

Draws 40% of the 4G traces per mobility class with a fixed seed and stores the list in
protocol/stall_development_traces.json. An existing file must match the draw.

Usage: python scripts/make_stall_partition.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loading import discover_traces  # noqa: E402
from src.stall_control import development_traces  # noqa: E402

SEED = 20261108
FRACTION = 0.4
OUT = ROOT / "protocol" / "stall_development_traces.json"


def main() -> None:
    table: dict = {}
    for meta in discover_traces(ROOT / "data" / "raw"):
        if meta.tech == "4G":
            table.setdefault(meta.mobility, []).append(meta.trace_id)
    chosen = development_traces(table, FRACTION, SEED)
    record = {"seed": SEED, "fraction": FRACTION,
              "n_4g_traces_by_mobility": {k: len(v) for k, v in sorted(table.items())},
              "n_development_traces": len(chosen), "development_traces": chosen}
    text = json.dumps(record, indent=1) + "\n"
    if OUT.exists():
        if OUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"{OUT} differs from the draw")
        print(f"{OUT} matches the draw: {len(chosen)} traces")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT}: {len(chosen)} traces")


if __name__ == "__main__":
    main()
