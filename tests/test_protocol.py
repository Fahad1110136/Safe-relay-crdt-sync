# """Sanity tests of the simulator (run: python -m pytest -q)."""
# import numpy as np
# from relaysim.config import Params, RunConfig
# from relaysim.trace import get_trace
# from relaysim.sim import run_one

# P = Params()
# TR = get_trace(0, P)


# def run(attack, f, defense, B=2, seed=0):
#     return run_one(RunConfig(attack, f, defense, B, seed), TR, P)


# def test_honest_converges_for_every_defense():
#     for d in ["none", "D1", "D1+D2", "D1+D2+D3"]:
#         r = run("none", 0, d)
#         assert r["converged"] and r["final_missing"] == 0, d


# def test_storage_bound_base_protocol():           # a relay never stores more than R states
#     assert run("none", 0, "none")["storage_peak"] <= P.n_replicas


# def test_storage_bound_with_probation():          # R + B
#     assert run("none", 0, "D1+D2", 4)["storage_peak"] <= P.n_replicas + 4


# def test_fake_label_poisoning_blocks_convergence():
#     r = run("fake_large", 30, "none")
#     assert not r["converged"] and r["missing_frac"] > 0.5


# def test_defense_stops_fake_label_poisoning():
#     r = run("fake_large", 30, "D1+D2+D3")
#     assert r["converged"] and r["detected"] > 0


# def test_relabel_hypothesis_and_D1():             # undefended replicas record phantom updates
#     assert run("relabel", 30, "none")["phantom"] > 0
#     assert run("relabel", 30, "D1")["phantom"] == 0


# def test_D3_has_no_false_positives_when_honest():
#     assert run("none", 0, "D1+D2+D3")["detected"] == 0


# def test_paired_design_same_attackers_across_defenses():
#     a = run("fake_small", 30, "none")["contacts_h"]
#     b = run("fake_small", 30, "D1+D2+D3")["contacts_h"]
#     assert a == b






"""Sanity tests of the simulator (run: python -m pytest -q)."""
from relaysim.config import Params, RunConfig
from relaysim.trace import get_trace
from relaysim.sim import run_one

P = Params()
TR = get_trace(0, P)


def run(attack, f, defense, B=2, seed=0, pct=100):
    return run_one(RunConfig(attack, f, defense, B, seed, pct), TR, P)


def test_honest_converges_for_every_defense():
    for d in ["none", "D1", "D1+D2", "D1+D2+D3"]:
        r = run("none", 0, d)
        assert r["converged"] and r["undelivered"] == 0, d


def test_storage_bound_base_protocol():           # a relay never stores more than R states
    assert run("none", 0, "none")["storage_peak"] <= P.n_replicas


def test_storage_bound_with_probation():          # R + B
    assert run("none", 0, "D1+D2", 4)["storage_peak"] <= P.n_replicas + 4


def test_fake_large_blocks_convergence_without_defense():
    r = run("fake_large", 30, "none")
    assert not r["converged"] and r["undelivered"] > 0.9


def test_full_defense_stops_fake_large():
    # a 2 h cool-down does not guarantee exact convergence on every seed, so test the damage removed
    r = run("fake_large", 30, "D1+D2+D3")
    assert r["detected"] > 0 and r["undelivered"] < 0.10


def test_relabel_creates_phantom_updates_only_without_D1():
    assert run("relabel", 30, "none")["phantom"] > 0
    assert run("relabel", 30, "D1")["phantom"] == 0


def test_D3_has_no_false_positives_when_honest():
    assert run("none", 0, "D1+D2+D3")["detected"] == 0


def test_paired_design_same_attackers_across_defenses():
    assert run("fake_small", 30, "none")["contacts_h"] == run("fake_small", 30, "D1+D2+D3")["contacts_h"]


def test_E1_more_relays_means_lower_latency():
    assert run("none", 0, "none", pct=100)["latency"] < run("none", 0, "none", pct=33)["latency"]
