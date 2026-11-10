"""Operating curves of the exploratory analysis (protocol amendment 4); see src/stall_curves.py.

Usage: python scripts/run_stall_curves.py [--n-jobs 6]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.stall_curves import main  # noqa: E402

if __name__ == "__main__":
    main()
