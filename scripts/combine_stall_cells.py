"""Combine the per-cell result files of the online-margin runs into one gzip file each.

Cell files are joined in sorted file order with one header line, so that the combined text
equals the text of the cell files. The gzip header carries no time stamp.

Usage: python scripts/combine_stall_cells.py
"""
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {ROOT / "results" / "stall_control" / "pilot": "pilot_rows.csv.gz",
           ROOT / "results" / "stall_control" / "test": "test_rows.csv.gz"}


def main() -> None:
    for folder, name in TARGETS.items():
        files = sorted((folder / "cells").glob("*.csv"))
        if not files:
            print(f"{folder}: no cell files")
            continue
        out = bytearray()
        for i, f in enumerate(files):
            lines = f.read_bytes().splitlines(keepends=True)
            out += b"".join(lines if i == 0 else lines[1:])
        with open(folder / name, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
            gz.write(bytes(out))
        print(f"{folder / name}: {len(files)} cells")


if __name__ == "__main__":
    main()
