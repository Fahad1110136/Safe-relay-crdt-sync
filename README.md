# Relaysim – E1 (sanity), E2 (attack impact), E3 (defense), E4 (ablation & cost)

Simulator for "Keeping Offline Sync Safe from Dishonest Relays": relay-based CRDT sync (base protocol of [6]),
three dishonest-relay behaviours (fake-label small/large, relabelling, black-hole) and the keyless defenses
D1 (label binding at replicas), D2 (bounded probation buffer, size B), D3 (plausibility check from replica counters).

## Run
    pip install numpy pandas scipy matplotlib pytest
    python -m pytest -q tests                                   # 12 sanity tests
    python -m relaysim.experiments --exp E1 E2 E3 E4 --seeds 20 --workers 4 --out results/runs.jsonl  
    python -m relaysim.analyze --runs results/runs.jsonl --out results 

## Re-Run (from Scratch)
    Remove-Item trace_cache -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item results\runs.jsonl -ErrorAction SilentlyContinue
    python -m pytest -q tests
    python -m relaysim.experiments --exp E4 E3 E2 E1 --seeds 20 --workers 4 --out results/runs.jsonl
    python -m relaysim.analyze --runs results/runs.jsonl --out results

## Layout
- relaysim/config.py       Table I parameters (60 relays, 10 replicas, 1 update/5 min, 01:00-12:00, trace ends 14:00, 20 seeds, B in {0,2,4})
- relaysim/trace.py        synthetic VBN-like contact trace + loader for a real trace CSV (t,a,b; relays 0..59, replicas 60..69)
- relaysim/sim.py          protocol, attacks, defenses, metrics
- relaysim/experiments.py  E1-E4 grids + parallel resumable runner
- relaysim/analyze.py      tables, figures, Wilcoxon signed-rank tests
- tests/test_protocol.py   sanity tests

## Experiments
- E1: f=0, relay ratio 20/33/50/100 % (share of buses acting as relays); checks latency/distance fall with more relays and stores <= R.
- E2: attacks with f in {10,30,50} %, no defense (RQ1). Same configs as the undefended arm of E3, so no extra runs.
- E3: same attacks, no defense vs D1+D2+D3 (B=2); paired by seed, Wilcoxon signed-rank.
- E4: D1 / D1+D2 / D1+D2+D3 at f=30 %; B in {0,2,4}; overhead (states per relay, states sent per contact) at f=0.
Every defended/undefended pair uses the same trace, attacker placement and seed (paired design).

## Metrics
Per-update convergence latency (+ share of updates never caught up), convergence distance (mean over replicas and time, and at trace end),
convergence rate (Di = 0 at trace end), undelivered-update ratio, peak/mean states per relay, states sent per contact.

## Modelling choices you should check against the base paper
- Trace is SYNTHETIC (random waypoint, 3x3 km, 100 m range, trace ends 14:00) because the VBN trace was not provided; the area was calibrated so honest runs converge within the ~2 h cool-down. Pass --trace-csv to use the real one. Report it as synthetic.
- A state's content is its version vector (updates are per-origin prefixes); label = advertised vector, valid = signature OK.
- Fake blob: label = attacker's aggregate + delta (small: +1 on one random entry; large: +1000 on every entry), fails signature. Relabel: real state, label = content + 1000 on every entry.
- Undefended replica applies Algorithm 2 (pointwise max of labels, own entry excluded so the replica's own counter stays true) -> "phantom" updates under relabelling.
- D2: dominated states go to probation (size B, oldest evicted); they leave only when a replica-sourced state dominates them; no age limit (T = remaining trace length). The earlier "corroboration" shortcut is disabled (Sim.USE_CORROBORATION = False).
- D3: states with label[r] > c_r are deleted; only probation states no longer dominated by a remaining state return to the store.