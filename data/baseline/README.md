# Baseline (Immutable)

Anchors copied from Main paper Table 3, "Policy Credibility Index: Baseline
Scores at IRA Enactment (August 2022)," with scoring protocol in SI Appendix
S7.

`pci_baseline.csv` is the starting state for the weekly time series. The
`pci/builder.py` reads it and writes the first row of `pci_weekly.parquet`
for each provision at week `2022-W33` (week of August 16, 2022).

**Do not edit.** If a reviewer or coauthor disputes a baseline value, update
the paper, then update this file with a citation note in the commit
message.

The post-OBBBA target values are not stored here. They are computed from the
paper-defined deltas in SI Appendix S7.5 and used as stress-test anchors.
Expected post-OBBBA shocks per provision (from the paper):

| Provision | ΔPCI |
|---|---:|
| 45X | −1.00 |
| 45V | −1.00 |
| 45Q | 0.00 |
| 30D | −1.00 |
| 50144 | −1.33 |
| 50141 | −0.67 |
