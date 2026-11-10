"""One-command smoke reproduction (~1 minute): runs one in-domain and one shifted
cell on a locked seed and checks that headline directions reproduce qualitatively.
Does not touch results/locked/.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(v, "4")

import pandas as pd  # noqa: E402

from src.data_loading import read_feature_table  # noqa: E402
from src.experiments import run_cell  # noqa: E402

feat = read_feature_table(ROOT / "data" / "processed" / "features_h1.csv.gz")
t0 = time.time()
rows = []
for regime in ("in_domain_4g", "cross_tech_4to5"):
    rows.append(run_cell(feat, regime, seed=0, alpha=0.1, base_model="gbm", gamma=0.05))
r = pd.concat(rows)
agg = r.groupby(["regime", "method"])["marginal_coverage"].first().unstack()
print(agg.round(3).to_string())
split_shift = agg.loc["cross_tech_4to5", "split"]
maci_shift = agg.loc["cross_tech_4to5", "mondrian_aci"]
split_id = agg.loc["in_domain_4g", "split"]

# single-seed tolerances: the 20-seed locked means are much tighter; one seed
# fluctuates (e.g. split in-domain 0.843..0.95 across seeds)
ok = (abs(split_id - 0.9) < 0.08) and (split_shift < 0.85) and (abs(maci_shift - 0.9) < 0.03)
print(f"\nsmoke checks: in-domain split~0.9 (+/-0.08): {abs(split_id-0.9)<0.08}; "
      f"shifted split<0.85: {split_shift<0.85}; shifted mondrian_aci~0.9: {abs(maci_shift-0.9)<0.03}")
print(f"SMOKE {'PASS' if ok else 'FAIL'} in {time.time()-t0:.0f}s")
sys.exit(0 if ok else 1)
