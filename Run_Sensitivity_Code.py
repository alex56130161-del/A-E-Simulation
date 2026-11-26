"""Sensitivity analysis. Usage: python Run_Sensitivity_Code.py
Writes results/sensitivity_replications.csv (per replication) and results/sensitivity_summary.csv
(mean per scenario/policy and paired difference vs baseline B, 95% t-interval).
Staffing is fixed (STAFF in Main_Result_Code.py) in every scenario."""
import numpy as np, pandas as pd
from scipy import stats
import Main_Result_Code as ae_sim
from Main_Result_Code import *
import Run_Experiments_Code as ex

REPS = 30
POL = dict(ex.POLICIES)   # all six policies of the main experiment (pooled / flex / aging, fixed staffing)
BASE = "B  pooled priority (baseline)"
SCEN = {
 "Base":                        dict(),
 "Arrivals x0.80":              dict(rate_mult=0.80),   # threshold runs: where a policy becomes feasible
 "Arrivals x0.85":              dict(rate_mult=0.85),
 "Arrivals x0.90":              dict(rate_mult=0.90),
 "Arrivals x0.95":              dict(rate_mult=0.95),
 "Arrivals x1.05":              dict(rate_mult=1.05),
 "Arrivals x1.10":              dict(rate_mult=1.10),
 "Service x0.95":               dict(svc_mult=0.95),
 "Service x1.05":               dict(svc_mult=1.05),
 "T4/5 arrivals x1.15 only":    dict(cls_mult={4: 1.15, 5: 1.15}),
 "T3 service x1.15 only":       dict(svc_cls_mult={3: 1.15}),
 "Joint: arrivals x1.05, service x1.05": dict(rate_mult=1.05, svc_mult=1.05),
 "Service CV 1.2 (base 0.8)":   dict(cv=1.2),
}

def summarize_all(df):
    rows = []
    for sc, g in df.groupby("scenario", sort=False):
        b = g[g.policy == BASE].sort_values("rep")
        for pol, x in g.groupby("policy", sort=False):
            x = x.sort_values("rep"); row = dict(scenario=sc, policy=pol, util=x.util.mean())
            for m in ("T45_mean", "T3_le30", "T2_le15", "T3_mean"):
                d = x[m].values - b[m].values
                h = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
                row[m] = x[m].mean(); row[m + "_diff"] = d.mean(); row[m + "_diff_hw"] = h
            rows.append(row)
    return pd.DataFrame(rows)

if __name__ == "__main__":
    out = []
    for sname, kw in SCEN.items():
        kw = dict(kw); cv = kw.pop("cv", 0.8); ae_sim.CV_SVC = cv
        d = ex.experiment(POL, reps=REPS, **kw); d["scenario"] = sname; out.append(d)
        print(sname, flush=True)
    ae_sim.CV_SVC = 0.8
    df = pd.concat(out); df.to_csv("results/sensitivity_replications.csv", index=False)
    summarize_all(df).to_csv("results/sensitivity_summary.csv", index=False)
