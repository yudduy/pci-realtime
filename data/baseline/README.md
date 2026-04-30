# Baseline (Immutable)

Anchors copied verbatim from the PNAS paper's Table 1 in
`Draft/PNAS.../Mechanism/Credibility.tex` (Aug 2022 PCI scores at IRA enactment).

`pci_baseline.csv` is the starting state for the weekly time series. The
`pci/builder.py` reads it and writes the first row of `pci_weekly.parquet`
for each provision at week `2022-W33` (week of August 16, 2022).

**Do not edit.** If a reviewer or coauthor disputes a baseline value, update
the paper, then update this file with a citation note in the commit
message.

The post-OBBBA target values (used by `pci/validation.py::test_obbba_match`)
are not stored here — they're computed from the cumulative deltas the
scorer produces and validated against `Mechanism/Credibility.tex` directly.
Expected post-OBBBA shocks per provision (from the paper):

| Provision | ΔPCI |
|---|---:|
| 45X | −1.00 |
| 45V | −1.00 |
| 45Q | 0.00 |
| 30D | −1.00 |
| 50144 | −1.33 |
| 50141 | −0.67 |
