"""Final test of the online margin (protocol amendment 3); see src/stall_test.py.

Usage: python scripts/run_stall_test.py [--n-jobs 6] [--smoke --out DIR]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.stall_test import main  # noqa: E402

if __name__ == "__main__":
    main()
