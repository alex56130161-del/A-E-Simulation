"""Main experiments. Usage: python Run_Experiments_Code.py   (writes results/*.csv)
Common random numbers: replication r uses seed BASE_SEED+r for every scenario.
All policies share the same fixed staffing schedule (STAFF in Main_Result_Code.py)."""
import numpy as np, pandas as pd, os, sys
from scipy import stats
from Main_Result_Code import *

BASE_SEED, REPS, WARM, MEAS = 20261, 30, 14, 100
os.makedirs("results", exist_ok=True)

POLICIES = {   # name -> Policy
 "B  pooled priority (baseline)": Policy("B"),
 "F1 flex fast-track x1, q=3":    Policy("F1", "flex", 1, q=3),
 "F2 flex fast-track x2, q=5":    Policy("F2", "flex", 2, q=5),
 "A60  aging, theta=60":          Policy("A60", "aging", theta=60),
 "A120 aging, theta=120":         Policy("A120", "aging", theta=120),
 "A180 aging, theta=180":         Policy("A180", "aging", theta=180),
}

def one(seed, pol, **gen_kw):
    p = gen_replication(seed, WARM + MEAS + 2, **gen_kw)
    cls, w = run(p, pol, STAFF, WARM, MEAS)
    s = summarize(cls, w)
    m = (p[:,0] >= WARM*1440) & (p[:,0] < (WARM+MEAS)*1440)
    util = p[m,2].sum() / (sum(STAFF) * 60 * MEAS)
    return dict(T45_mean=s['45']['mean'], T45_p90=s['45']['p90'], T4_mean=s[4]['mean'], T5_mean=s[5]['mean'],
                T3_mean=s[3]['mean'], T3_le30=s[3]['le30'], T2_mean=s[2]['mean'], T2_le15=s[2]['le15'],
                T3_p90=s[3]['p90'], util=util)

def experiment(policies, reps=REPS, **gen_kw):
    rows = []
    for name, pol in policies.items():
        for r in range(reps):
            d = one(BASE_SEED + r, pol, **gen_kw); d.update(policy=name, rep=r); rows.append(d)
    return pd.DataFrame(rows)

def paired(df, base, metric):
    b = df[df.policy == base].sort_values("rep")[metric].values
    out = {}
    for name, g in df.groupby("policy"):
        x = g.sort_values("rep")[metric].values; d = x - b
        h = stats.t.ppf(0.975, len(d)-1) * d.std(ddof=1) / np.sqrt(len(d))
        out[name] = (x.mean(), x.std(ddof=1)/np.sqrt(len(x))*stats.t.ppf(0.975,len(x)-1), d.mean(), h)
    return out

if __name__ == "__main__":
    df = experiment(POLICIES); df.to_csv("results/main_replications.csv", index=False)
    base = "B  pooled priority (baseline)"
    summ = df.groupby("policy", sort=False).mean(numeric_only=True).drop(columns="rep")
    print(summ.round(3).to_string())
    for m in ("T45_mean","T45_p90","T3_le30","T3_mean","T2_le15"):
        print("\n", m)
        for k, v in paired(df, base, m).items(): print(f"  {k:34s} mean {v[0]:8.3f} +-{v[1]:6.3f}   diff {v[2]:8.3f} +-{v[3]:6.3f}")
