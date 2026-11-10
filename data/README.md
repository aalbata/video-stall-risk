# Data sources

| Dataset | Used for | Source | Licence |
|---|---|---|---|
| 4G traces (Raca et al., MMSys 2018) | training, testing | https://doi.org/10.5281/zenodo.1219679 | CC BY 4.0 |
| 5G traces (Raca et al., MMSys 2020) | training, testing | https://github.com/uccmisl/5Gdataset | GPL-3.0 |
| Video segment sizes (Quinlan and Sreenan, MMSys 2018) | player | https://doi.org/10.5281/zenodo.1219788 | CC BY 4.0 |
| Lumos5G-v1.0 (Narayanan et al., IMC 2020) | external test | https://networking.umn.edu/lumos5g | CC BY 4.0, included in `external/lumos5g/` |

`scripts/download_data.py` and `scripts/fetch_ladder.py` download and verify the first three. The traces are not redistributed here. `row_order.json.gz` records the order of rows that share a timestamp. `ladder/` holds the segment sizes used by the player.
