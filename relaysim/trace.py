"""Contact traces. A trace is three arrays (t, a, b): at time t, relay a meets node b.
Node ids: relays 0..L-1, replicas L..L+R-1.  Relay-relay contacts appear once with a<b.

generate_trace() builds a synthetic VBN-like trace (random-waypoint relays, static replicas).
load_trace_csv() lets you plug in the real VBN trace (columns: t,a,b using the id convention above).
"""
import os
import numpy as np
from .config import Params


def generate_trace(seed: int, p: Params):
    L, R = p.n_relays, p.n_replicas
    rng = np.random.default_rng(10_000 + seed)
    A = p.area_m
    pos = rng.uniform(0, A, (L, 2))
    tgt = rng.uniform(0, A, (L, 2))
    spd = rng.uniform(p.speed_lo, p.speed_hi, L)
    pause = np.zeros(L)
    rep = rng.uniform(0, A, (R, 2))
    prev = np.zeros((L, L + R), dtype=bool)
    triu = np.triu(np.ones((L, L), dtype=bool), k=1)
    T, X, Y = [], [], []
    for k in range(int(p.duration_s / p.step_s)):
        moving = pause <= 0
        d = tgt - pos
        dist = np.linalg.norm(d, axis=1)
        mv = spd * p.step_s
        frac = np.minimum(mv, dist) / np.maximum(dist, 1e-9)
        pos = np.where(moving[:, None], pos + d * frac[:, None], pos)
        arrived = moving & (dist <= mv)
        n = int(arrived.sum())
        if n:
            tgt[arrived] = rng.uniform(0, A, (n, 2))
            spd[arrived] = rng.uniform(p.speed_lo, p.speed_hi, n)
            pause[arrived] = rng.uniform(0, p.pause_max_s, n)
        pause[~moving] -= p.step_s
        allpos = np.vstack([pos, rep])
        D = np.linalg.norm(pos[:, None, :] - allpos[None, :, :], axis=2)
        inr = D <= p.range_m
        inr[np.arange(L), np.arange(L)] = False
        inr[:, :L] &= triu
        new = inr & ~prev
        prev = inr
        a, b = np.nonzero(new)
        if len(a):
            T.append(np.full(len(a), k * p.step_s))
            X.append(a)
            Y.append(b)
    return np.concatenate(T), np.concatenate(X).astype(np.int32), np.concatenate(Y).astype(np.int32)


def load_trace_csv(path):
    arr = np.loadtxt(path, delimiter=",", skiprows=1)
    order = np.argsort(arr[:, 0], kind="stable")
    arr = arr[order]
    return arr[:, 0], arr[:, 1].astype(np.int32), arr[:, 2].astype(np.int32)


def get_trace(seed: int, p: Params, cache_dir="trace_cache"):
    os.makedirs(cache_dir, exist_ok=True)
    fn = os.path.join(cache_dir, f"trace_L{p.n_relays}_R{p.n_replicas}_s{seed}.npz")
    if os.path.exists(fn):
        z = np.load(fn)
        return z["t"], z["a"], z["b"]
    t, a, b = generate_trace(seed, p)
    np.savez_compressed(fn, t=t, a=a, b=b)
    return t, a, b
