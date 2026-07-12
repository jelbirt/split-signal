# Horizon decay: signal strength vs. prediction horizon

Same features and model as Split Likelihood v1; only the label window
changes. Train always ends one full label-window before the 2019+
holdout; labels require fully-elapsed windows (no partial credit).

| horizon | holdout AUC | top-decile lift | capture | base rate | train rows | holdout rows (quarters) |
|---|---|---|---|---|---|---|
| 12m | 0.740 | 3.7x | 37% | 1.58% | 48,775 | 50,006 (26) |
| 18m | 0.726 | 3.5x | 35% | 2.40% | 45,974 | 45,420 (24) |
| 24m | 0.718 | 3.2x | 32% | 3.19% | 43,216 | 41,109 (22) |
| 36m | 0.706 | 2.8x | 28% | 4.72% | 38,039 | 32,896 (18) |
| 48m | 0.699 | 2.8x | 28% | 6.13% | 33,038 | 24,908 (14) |
| 60m | 0.689 | 2.7x | 27% | 7.62% | 28,369 | 16,919 (10) |

Reading: AUC measures ranking quality at each horizon; lift is how much
denser splitters are in the top decile than in the population. Longer
horizons mechanically raise the base rate (more time for a split to
happen), so lift compresses even where AUC holds — compare both.
Survivorship caveat applies equally at every horizon (DATA_QUALITY.md).
