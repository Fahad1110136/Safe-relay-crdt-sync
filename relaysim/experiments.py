# """Experiment grids for E4 (ablation and cost) and E3 (defense effectiveness), plus a
# resumable parallel runner.   Usage:
#     python -m relaysim.experiments --exp E4 E3 --seeds 20 --out results/runs.jsonl
# Optional: --trace-csv real_trace.csv  (use one real trace for every seed; relays 0..L-1, replicas L..)
# """
# import argparse, json, os, sys, time
# from multiprocessing import Pool
# from .config import Params, RunConfig
# from .trace import get_trace, load_trace_csv
# from .sim import run_one

# ATTACKS = ["fake_small", "fake_large", "relabel", "blackhole"]
# P = Params()


# def grid_E4(seeds):
#     cfgs = []
#     for s in seeds:
#         # (a) ablation at f = 30 %, B = 2 (none = reference for damage)
#         for a in ATTACKS:
#             for d in ["none", "D1", "D1+D2", "D1+D2+D3"]:
#                 cfgs.append(RunConfig(a, 30, d, 2, s))
#         # (b) probation-size sweep at f = 30 %
#         for a in ATTACKS:
#             for d in ["D1+D2", "D1+D2+D3"]:
#                 for B in (0, 2, 4):
#                     cfgs.append(RunConfig(a, 30, d, B, s))
#         # (c) overhead at f = 0 (nothing is wrong)
#         cfgs.append(RunConfig("none", 0, "none", 2, s))
#         cfgs.append(RunConfig("none", 0, "D1", 2, s))
#         for d in ["D1+D2", "D1+D2+D3"]:
#             for B in (0, 2, 4):
#                 cfgs.append(RunConfig("none", 0, d, B, s))
#     return cfgs


# def grid_E3(seeds):
#     cfgs = []
#     for s in seeds:
#         for a in ATTACKS:
#             for f in (10, 30, 50):
#                 cfgs.append(RunConfig(a, f, "none", 2, s))          # E2 reference (undefended)
#                 cfgs.append(RunConfig(a, f, "D1+D2+D3", 2, s))      # E3 defended, B = 2
#     return cfgs


# _TR = {}
# _CSV = None


# def _trace(seed):
#     if _CSV:
#         if "csv" not in _TR:
#             _TR["csv"] = load_trace_csv(_CSV)
#         return _TR["csv"]
#     if seed not in _TR:
#         _TR.clear()
#         _TR[seed] = get_trace(seed, P)
#     return _TR[seed]


# def work(cfg):
#     r = run_one(cfg, _trace(cfg.seed), P)
#     r.update(cfg.asdict())
#     r["key"] = cfg.key()
#     return r


# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--exp", nargs="+", default=["E4", "E3"])
#     ap.add_argument("--seeds", type=int, default=20)
#     ap.add_argument("--out", default="results/runs.jsonl")
#     ap.add_argument("--workers", type=int, default=os.cpu_count())
#     ap.add_argument("--trace-csv", default=None)
#     a = ap.parse_args()
#     global _CSV
#     _CSV = a.trace_csv
#     os.makedirs(os.path.dirname(a.out), exist_ok=True)
#     done = set()
#     if os.path.exists(a.out):
#         with open(a.out) as fh:
#             for line in fh:
#                 done.add(json.loads(line)["key"])
#     seeds = list(range(a.seeds))
#     for exp in a.exp:                      # run order = order given (E4 first, then E3)
#         cfgs = {"E4": grid_E4, "E3": grid_E3}[exp](seeds)
#         todo = [c for c in dict.fromkeys(cfgs) if c.key() not in done]
#         todo.sort(key=lambda c: c.seed)    # keeps one trace in memory per worker
#         print(f"[{exp}] {len(cfgs)} configs, {len(todo)} to run", flush=True)
#         t0 = time.time()
#         with open(a.out, "a") as fh, Pool(a.workers) as pool:
#             for i, r in enumerate(pool.imap_unordered(work, todo, chunksize=4), 1):
#                 fh.write(json.dumps(r) + "\n"); fh.flush(); done.add(r["key"])
#                 if i % 50 == 0:
#                     print(f"  {i}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
#         print(f"[{exp}] done in {time.time()-t0:.0f}s", flush=True)


# if __name__ == "__main__":
#     main()






"""Experiment grids of Table II (E1 sanity, E2 attack impact, E3 defense, E4 ablation and cost)
plus a resumable parallel runner.   Usage:
    python -m relaysim.experiments --exp E4 E3 E2 E1 --seeds 20 --out results/runs.jsonl
Optional: --trace-csv real_trace.csv  (use one real trace for every seed; relays 0..L-1, replicas L..)
"""
import argparse, json, os, sys, time
from multiprocessing import Pool
from .config import Params, RunConfig
from .trace import get_trace, load_trace_csv
from .sim import run_one

ATTACKS = ["fake_small", "fake_large", "relabel", "blackhole"]
P = Params()


def grid_E4(seeds):
    cfgs = []
    for s in seeds:
        # (a) ablation at f = 30 %, B = 2 (none = reference for damage)
        for a in ATTACKS:
            for d in ["none", "D1", "D1+D2", "D1+D2+D3"]:
                cfgs.append(RunConfig(a, 30, d, 2, s))
        # (b) probation-size sweep at f = 30 %
        for a in ATTACKS:
            for d in ["D1+D2", "D1+D2+D3"]:
                for B in (0, 2, 4):
                    cfgs.append(RunConfig(a, 30, d, B, s))
        # (c) overhead at f = 0 (nothing is wrong)
        cfgs.append(RunConfig("none", 0, "none", 2, s))
        cfgs.append(RunConfig("none", 0, "D1", 2, s))
        for d in ["D1+D2", "D1+D2+D3"]:
            for B in (0, 2, 4):
                cfgs.append(RunConfig("none", 0, d, B, s))
    return cfgs


def grid_E1(seeds):
    return [RunConfig("none", 0, "none", 2, s, pct) for s in seeds for pct in (20, 33, 50, 100)]


def grid_E2(seeds):
    return [RunConfig(a, f, "none", 2, s) for s in seeds for a in ATTACKS for f in (10, 30, 50)]


def grid_E3(seeds):
    cfgs = []
    for s in seeds:
        for a in ATTACKS:
            for f in (10, 30, 50):
                cfgs.append(RunConfig(a, f, "none", 2, s))          # E2 reference (undefended)
                cfgs.append(RunConfig(a, f, "D1+D2+D3", 2, s))      # E3 defended, B = 2
    return cfgs


_TR = {}
_CSV = None


def _trace(seed):
    if _CSV:
        if "csv" not in _TR:
            _TR["csv"] = load_trace_csv(_CSV)
        return _TR["csv"]
    if seed not in _TR:
        _TR.clear()
        _TR[seed] = get_trace(seed, P)
    return _TR[seed]


def work(cfg):
    r = run_one(cfg, _trace(cfg.seed), P)
    r.update(cfg.asdict())
    r["key"] = cfg.key()
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", nargs="+", default=["E4", "E3", "E2", "E1"])
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--out", default="results/runs.jsonl")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--trace-csv", default=None)
    a = ap.parse_args()
    global _CSV
    _CSV = a.trace_csv
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    done = set()
    if os.path.exists(a.out):
        with open(a.out, encoding="utf-8") as fh:
            for line in fh:
                done.add(json.loads(line)["key"])
    seeds = list(range(a.seeds))
    for exp in a.exp:                      # run order = order given (E4 first, then E3)
        cfgs = {"E4": grid_E4, "E3": grid_E3, "E2": grid_E2, "E1": grid_E1}[exp](seeds)
        todo = [c for c in dict.fromkeys(cfgs) if c.key() not in done]
        todo.sort(key=lambda c: c.seed)    # keeps one trace in memory per worker
        print(f"[{exp}] {len(cfgs)} configs, {len(todo)} to run", flush=True)
        t0 = time.time()
        with open(a.out, "a", encoding="utf-8") as fh, Pool(a.workers) as pool:
            for i, r in enumerate(pool.imap_unordered(work, todo, chunksize=4), 1):
                fh.write(json.dumps(r) + "\n"); fh.flush(); done.add(r["key"])
                if i % 50 == 0:
                    print(f"  {i}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
        print(f"[{exp}] done in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()