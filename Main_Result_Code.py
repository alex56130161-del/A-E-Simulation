"""
SEEM3410 - Hong Kong public hospital A&E discrete-event simulation.
Event-driven (arrival / completion / shift-change) model with triage classes 2-5,
common random numbers (per-replication arrival & service-time streams shared by all policies).
"""
import heapq, math
from collections import deque
import numpy as np

CLASSES = [2, 3, 4, 5]
# --- Inputs (see report Table 1) ---------------------------------------------------------
# HA 2024 average daily attendance (all 18 A&Es): T2 154, T3 2194, T4 2909, T5 124.
HA_DAILY = {2: 154, 3: 2194, 4: 2909, 5: 124}
N_HOSP = 18                         # representative hospital = 1/18 of HA volume
DAILY = {c: HA_DAILY[c] / N_HOSP for c in CLASSES}
RAW = np.array([0.75,0.60,0.50,0.45,0.40,0.40,0.50,0.70,1.00,1.35,1.55,1.60,
                1.50,1.40,1.30,1.25,1.25,1.30,1.30,1.25,1.10,1.00,0.90,0.80])
HOUR_MULT = RAW / RAW.mean()        # assumed diurnal shape, mean 1
MEAN_SVC = {2: 44.73, 3: 29.82, 4: 19.88, 5: 14.91}  # mean doctor-minutes per patient (assumed 45/30/20/15, x0.994 calibration)
CV_SVC = 0.8
# Non-doctor delay (nurse triage-to-cubicle, bed, registration) added to modelled T2/T3 waits; calibrated
EXTRA_DELAY = {2: 4.0, 3: 18.0, 4: 0.0, 5: 0.0}
# Fixed staffing schedule: doctors on duty per hour of day (3 at night, 7 daytime, 6 evening; 128 doctor-hours/day).
# This is held fixed for every policy; it is an input, not a policy.
STAFF = [3]*8 + [7]*8 + [6]*8

def staff_at(hour, staff):
    return staff[hour % 24]

def gen_replication(seed, days, rate_mult=1.0, svc_mult=1.0, cls_mult=None, svc_cls_mult=None):
    """Pre-generate all patients (arrival time, class, service time). Same seed -> same patients."""
    rng = np.random.default_rng(seed)
    cls_mult = cls_mult or {}
    svc_cls_mult = svc_cls_mult or {}
    rows = []
    sig2 = math.log(1 + CV_SVC ** 2); sig = math.sqrt(sig2)
    for c in CLASSES:                       # one independent stream per class
        r = np.random.default_rng([seed, c])
        lam_h = DAILY[c] / 24.0 * HOUR_MULT * rate_mult * cls_mult.get(c, 1.0)
        lam = np.tile(lam_h, days)          # per-hour rate for each hour of the horizon
        n = r.poisson(lam)
        times = np.concatenate([h + r.random(k) for h, k in enumerate(n)]) if n.sum() else np.array([])
        mu = math.log(MEAN_SVC[c] * svc_mult * svc_cls_mult.get(c, 1.0)) - sig2 / 2
        s = r.lognormal(mu, sig, size=len(times))
        rows.append(np.column_stack([times * 60.0, np.full(len(times), c), s]))
    a = np.vstack(rows)
    return a[np.argsort(a[:, 0], kind="stable")]

class Policy:
    """kind: 'pooled' | 'flex' | 'aging'
       n_ft: number of on-duty doctors assigned to the fast-track (T4/5) group (only when >=5 doctors on duty)
       q: flex fast-track doctors switch to T3 when T3 queue length >= q
       theta: aging threshold in minutes (T4/5 patients waiting >= theta compete with T3 by arrival time)"""
    def __init__(self, name, kind="pooled", n_ft=0, q=3, theta=None):
        self.name, self.kind, self.n_ft, self.q, self.theta = name, kind, n_ft, q, theta

def run(patients, policy, staff, warm_days, meas_days):
    n = len(patients)
    T0 = warm_days * 1440.0; T1 = (warm_days + meas_days) * 1440.0
    queues = {c: deque() for c in CLASSES}         # holds patient indices FIFO
    start = np.full(n, np.nan)
    on = {"G": 0, "F": 0}; busy = {"G": 0, "F": 0}; target = {"G": 0, "F": 0}
    comp = []                                       # heap (time, group)
    ev_shift_next = 0.0
    ai = 0
    arr_t = patients[:, 0]; arr_c = patients[:, 1].astype(int); svc = patients[:, 2]

    def low():
        q4, q5 = queues[4], queues[5]
        if q4 and q5:
            return q4.popleft() if arr_t[q4[0]] <= arr_t[q5[0]] else q5.popleft()
        if q4: return q4.popleft()
        if q5: return q5.popleft()
        return None

    def pick(group, now):
        q2, q3, q4, q5 = queues[2], queues[3], queues[4], queues[5]
        if group == "F":
            # flexible fast-track
            if q2: return q2.popleft()
            if len(q3) >= policy.q: return q3.popleft()
            x = low()
            if x is not None: return x
            if q3: return q3.popleft()
            return None
        # general doctor
        if q2: return q2.popleft()
        if policy.kind == "aging" and policy.theta is not None:
            cand = []
            if q3: cand.append((arr_t[q3[0]], 3))
            for c in (4, 5):
                if queues[c] and now - arr_t[queues[c][0]] >= policy.theta:
                    cand.append((arr_t[queues[c][0]], c))
            if cand:
                return queues[min(cand)[1]].popleft()
        if q3: return q3.popleft()
        return low()

    def dispatch(now):
        progress = True
        while progress:
            progress = False
            for g in ("G", "F"):
                while on[g] - busy[g] > 0:
                    p = pick(g, now)
                    if p is None: break
                    start[p] = now; busy[g] += 1
                    heapq.heappush(comp, (now + svc[p], g)); progress = True

    def set_staff(now):
        total = staff_at(int(now // 60), staff)
        if policy.kind == "flex":
            f = min(policy.n_ft, max(total - 3, 0)) if total >= 5 else 0   # fast-track only when >=5 doctors on duty
        else:
            f = 0
        new = {"G": total - f, "F": f}
        for g in ("G", "F"):
            target[g] = new[g]
            if on[g] < target[g]: on[g] = target[g]
            elif on[g] > target[g]:
                idle = on[g] - busy[g]
                rem = min(idle, on[g] - target[g]); on[g] -= rem

    next_shift = 0.0
    while True:
        t_arr = arr_t[ai] if ai < n and arr_t[ai] < T1 else math.inf
        t_comp = comp[0][0] if comp else math.inf
        t_sh = next_shift if next_shift < T1 else math.inf
        now = min(t_arr, t_comp, t_sh)
        if now == math.inf:
            # no more arrivals/shifts: drain
            if any(len(q) for q in queues.values()) and comp is not None:
                pass
            if not comp and not any(len(q) for q in queues.values()): break
        if now == t_sh:   # shift change (hourly)
            set_staff(now); next_shift += 60.0; dispatch(now)
        elif now == t_comp:
            _, g = heapq.heappop(comp); busy[g] -= 1
            if on[g] > target[g]: on[g] -= 1
            dispatch(now)
        elif now == t_arr:
            queues[arr_c[ai]].append(ai); ai += 1; dispatch(now)
        else:
            break
        if now == math.inf: break
    # Drain after horizon: keep staffing at last level, process leftovers
    while comp or any(len(q) for q in queues.values()):
        if comp:
            tnow, g = heapq.heappop(comp); busy[g] -= 1
            if on[g] > target[g]: on[g] -= 1
            dispatch(tnow)
        else:
            set_staff(T1 - 1); dispatch(T1)   # safety (should not trigger)
            if not comp: break
    wait = start - arr_t
    m = (arr_t >= T0) & (arr_t < T1)
    return arr_c[m], wait[m]

def summarize(cls, wait):
    out = {}
    for c in CLASSES:
        w = wait[cls == c] + EXTRA_DELAY[c]
        out[c] = dict(mean=w.mean(), p90=np.percentile(w, 90), n=len(w),
                      le15=(w <= 15).mean(), le30=(w <= 30).mean())
    w45 = wait[(cls == 4) | (cls == 5)]
    out["45"] = dict(mean=w45.mean(), p90=np.percentile(w45, 90), n=len(w45))
    return out
