# relaysim – E4 (ablation & cost) and E3 (defense effectiveness)

Simulator for "Keeping Offline Sync Safe from Dishonest Relays": relay-based CRDT sync (base protocol of [6]),
three dishonest-relay behaviours (fake-label small/large, relabelling, black-hole) and the keyless defenses
D1 (label binding at replicas), D2 (bounded probation buffer, size B), D3 (plausibility check from replica counters).

## Run
    pip install numpy pandas scipy matplotlib pytest
    python -m pytest -q tests                                   # 8 sanity tests
    python -m relaysim.experiments --exp E4 E3 --seeds 20 --workers 4 --out results/runs.jsonl   # resumable
    python -m relaysim.analyze --runs results/runs.jsonl --out results   # tables (CSV+RESULTS.md) + figures

## Layout
- relaysim/config.py       Table I parameters (60 relays, 10 replicas, 1 update/5 min, 01:00-12:00, 20 seeds, B in {0,2,4})
- relaysim/trace.py        synthetic VBN-like contact trace + loader for a real trace CSV (t,a,b; relays 0..59, replicas 60..69)
- relaysim/sim.py          protocol, attacks, defenses, metrics
- relaysim/experiments.py  E4 and E3 grids + parallel resumable runner (E4 runs first, then E3)
- relaysim/analyze.py      tables and figures
- tests/test_protocol.py   sanity tests

## Experiments (Table II)
- E4: D1 / D1+D2 / D1+D2+D3 at f=30 %; B in {0,2,4}; overhead at f=0.
- E3: same attacks with f in {10,30,50} %, no defense vs D1+D2+D3 (B=2). The undefended arm is the E2 reference.
Every defended/undefended pair uses the same trace, attacker placement and seed (paired design).

## Modelling choices you should check against the base paper
- Trace is SYNTHETIC (random waypoint, 5x5 km, 100 m range) because the VBN trace was not provided; pass --trace-csv to use the real one.
- A state's content is its version vector (updates are per-origin prefixes); label = advertised vector, valid = signature OK.
- Fake blob: label = attacker's aggregate + delta (3 small / 1000 large), fails signature. Relabel: real state, label = content + 25.
- Undefended replica applies Algorithm 2 (pointwise max of labels, own entry excluded) -> "phantom" updates under relabelling.
- A fake/relabelled dominator is "corroborated" for D2 only if all its entries are <= the counters the relay itself saw at replicas.
- Lost-update ratio = peak share of produced updates that were handed to the honest relay layer, are absent from it, and are not yet at all replicas.
- Traffic = 1 KiB per state + 4 B per vector entry; CPU = label comparisons per contact.
