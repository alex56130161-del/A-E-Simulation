# SEEM3410 Team Project — Data and Code

Discrete-event simulation of a Hong Kong public hospital A&E (triage levels 2–5) comparing
queue-discipline policies — pooled priority, flexible fast-track and ageing — under one fixed
staffing schedule. Event-driven model with common random numbers: the same patients are replayed
under every policy, so policy differences are paired within each replication.

## Software requirements

- Python 3.10+ (tested on 3.13)
- Python packages: `numpy`, `pandas`, `scipy`, `matplotlib` — install with

      pip install numpy pandas scipy matplotlib

## Run instructions

Run from this folder:

    python Run_Experiments_Code.py    # main results: 30 replications x 6 policies
                                      #   -> results/main_replications.csv
    python Run_Sensitivity_Code.py    # sensitivity: 13 scenarios x 6 policies x 30 replications
                                      #   -> results/sensitivity_replications.csv
                                      #   -> results/sensitivity_summary.csv

Both scripts create `results/` automatically.

## Seeds and configuration

- Replication r uses seed `20261 + r` (r = 0..29). Each triage class has its own random stream
  `[seed, class]`. `REPS` is set to 30 in both scripts; results for any prefix of the seed
  sequence are reproducible regardless of `REPS`.
- **Common random numbers**: patients (arrival time, class, doctor time) are generated once per
  replication and replayed under every policy; 95% t-intervals over the 30 replications.
- Warm-up 14 days, measurement 100 days, plus 2 extra generated days so the horizon drains;
  empty initial state; every patient arriving in the measurement window is followed until
  consultation starts.
- **Fixed staffing schedule** (`STAFF` in `Main_Result_Code.py`, shared by all policies — an
  input, not an experimental factor): 3 doctors 00:00–08:00, 7 doctors 08:00–16:00, 6 doctors
  16:00–24:00 = 128 doctor-hours per day.
- **Policies** (`POLICIES` in `Run_Experiments_Code.py`): `B` pooled priority (baseline),
  `F1` flexible fast-track ×1 with q=3, `F2` flexible fast-track ×2 with q=5,
  `A60`/`A120`/`A180` ageing with threshold θ = 60/120/180 min.
- **Sensitivity scenarios** (`SCEN` in `Run_Sensitivity_Code.py`): arrival multipliers ×0.80,
  ×0.85, ×0.90, ×0.95, ×1.05, ×1.10; service-time multipliers ×0.95, ×1.05; T4/5 arrivals ×1.15
  only; T3 service ×1.15 only; joint ×1.05/×1.05; service CV 1.2 (base 0.8).

## Input data (`Main_Result_Code.py`)

All inputs are hard-coded constants; the simulation reads no external files.

- HA 2024 average daily attendance by triage category, per representative hospital (HA total ÷ 18):
  T2 154, T3 2,194, T4 2,909, T5 124. Source: HA press release of 15 Jan 2025, Annex 1
  (`P2025011500467_483364_1_1736931757837.pdf`, included in this folder), which also supplies
  the average waiting times used to calibrate the non-doctor delays (4 min level 2, 18 min level 3).
- Assumed hourly arrival multipliers (diurnal shape, mean 1); mean doctor-minutes
  44.73 / 29.82 / 19.88 / 14.91 (assumed 45/30/20/15 × 0.994 calibration); lognormal service
  times with CV 0.8.
- `Data-Specification-for-A&E-Waiting-Time-en.pdf` (included) documents the HA real-time A&E
  waiting-time dataset on data.gov.hk, cited in the report as background; the calibration uses
  the annual press-release figures above.

## Outputs

- `results/main_replications.csv` — per-replication metrics (mean / p90 wait, level 3 ≤ 30-min
  and level 2 ≤ 15-min compliance, utilisation) for the 6 policies under the base configuration.
- `results/sensitivity_replications.csv` — the same metrics across the 13 sensitivity scenarios.
- `results/sensitivity_summary.csv` — scenario × policy means plus paired differences vs baseline
  B with 95% t-interval half-widths.
