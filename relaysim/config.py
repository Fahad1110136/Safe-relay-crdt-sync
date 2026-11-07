# """Parameters. Table I of the report is encoded in Params / the experiment grids."""
# from dataclasses import dataclass, asdict


# @dataclass(frozen=True)
# class Params:
#     # --- topology (Table I: VBN trace, 60 relays, 10 static replicas) ---
#     n_replicas: int = 10
#     n_relays: int = 60
#     # --- synthetic VBN-like mobility (only used if no real trace is supplied) ---
#     area_m: float = 5000.0
#     range_m: float = 100.0
#     step_s: float = 10.0
#     duration_s: float = 86400.0
#     speed_lo: float = 3.0
#     speed_hi: float = 12.0
#     pause_max_s: float = 60.0
#     # --- workload (Table I: 1 update / 5 min / replica, [01:00-12:00]) ---
#     upd_start_s: float = 1 * 3600.0
#     upd_end_s: float = 12 * 3600.0
#     upd_period_s: float = 300.0
#     # --- cost model ---
#     blob_bytes: int = 1024          # size of one sealed CRDT state
#     counter_bytes: int = 4          # per entry of a version vector
#     prob_ttl_s: float = 7200.0      # D2 time limit for a probation entry
#     sample_dt_s: float = 300.0      # metric sampling period
#     # --- attack strengths ---
#     fake_small_delta: int = 3       # inflation over true aggregate (small)
#     fake_large_delta: int = 1000    # inflation over true aggregate (large)
#     relabel_delta: int = 25         # inflation added to a real state's vector

#     @property
#     def n_updates_per_replica(self) -> int:
#         return int((self.upd_end_s - self.upd_start_s) / self.upd_period_s)


# ATTACKS = ("none", "fake_small", "fake_large", "relabel", "blackhole")
# DEFENSES = ("none", "D1", "D1+D2", "D1+D2+D3")


# @dataclass(frozen=True)
# class RunConfig:
#     attack: str = "none"
#     f: int = 0              # dishonest percentage of relays
#     defense: str = "none"
#     B: int = 2              # probation size (only used by D2)
#     seed: int = 0

#     def key(self) -> str:
#         return f"{self.attack}|{self.f}|{self.defense}|{self.B}|{self.seed}"

#     def asdict(self):
#         return asdict(self)









"""Parameters. Table I / Table II of the D-II report are encoded here and in experiments.py."""
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Params:
    # --- topology (Table I: VBN, 60 relays, 10 static replicas) ---
    n_replicas: int = 10
    n_relays: int = 60
    # --- synthetic VBN-like mobility (used only if no real trace is supplied) ---
    area_m: float = 3000.0
    range_m: float = 100.0
    step_s: float = 10.0
    duration_s: float = 14 * 3600.0      # updates stop at 12:00 -> ~2 h cool-down
    speed_lo: float = 3.0
    speed_hi: float = 12.0
    pause_max_s: float = 60.0
    min_replica_sep_frac: float = 0.25   # replicas placed far apart: min distance = 25 % of the area side
    # --- workload (1 update / 5 min / replica, [01:00-12:00], random start offset) ---
    upd_start_s: float = 1 * 3600.0
    upd_end_s: float = 12 * 3600.0
    upd_period_s: float = 300.0
    # --- cost model ---
    blob_bytes: int = 1024
    counter_bytes: int = 4
    sample_dt_s: float = 300.0
    # --- attacks (Sec. III-C) ---
    fake_small_delta: int = 1        # +1 on ONE randomly chosen entry of V_agg
    fake_large_delta: int = 1000     # +10^3 on EVERY entry of V_agg (also the relabelling label)

    @property
    def n_updates_per_replica(self) -> int:
        return int((self.upd_end_s - self.upd_start_s) / self.upd_period_s)


ATTACKS = ("none", "fake_small", "fake_large", "relabel", "blackhole")
DEFENSES = ("none", "D1", "D1+D2", "D1+D2+D3")


@dataclass(frozen=True)
class RunConfig:
    attack: str = "none"
    f: int = 0              # dishonest percentage of (active) relays
    defense: str = "none"
    B: int = 2              # probation size (D2)
    seed: int = 0
    relay_pct: int = 100    # E1: share of the buses that act as relays

    def key(self) -> str:
        return f"{self.attack}|{self.f}|{self.defense}|{self.B}|{self.seed}|{self.relay_pct}"

    def asdict(self):
        return asdict(self)