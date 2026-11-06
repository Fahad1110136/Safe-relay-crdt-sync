"""Discrete-event simulator of relay-based CRDT synchronisation (base protocol of [6]),
three dishonest-relay behaviours, and the keyless defenses D1, D2, D3.

Model of a CRDT state: a replica's state is the set of updates it has seen; because each
replica numbers its own updates, that set is a prefix per origin, i.e. exactly its version
vector.  A State object therefore carries
    label   - the version vector *advertised* with the sealed blob (what relays can see)
    content - the true vector of the sealed blob (what a replica sees after opening it)
    valid   - False if the blob fails signature verification (fabricated by an attacker)
Honest states have label == content.
"""
import operator
import numpy as np
from .config import Params, RunConfig

ge = operator.ge


class State:
    __slots__ = ("id", "label", "content", "valid")

    def __init__(self, i, label, content, valid=True):
        self.id, self.label, self.content, self.valid = i, label, content, valid


class Relay:
    __slots__ = ("idx", "honest", "kind", "main", "prob", "known_c", "agg")

    def __init__(self, idx, R, kind=None):
        self.idx = idx
        self.kind = kind            # None (honest) or attack name
        self.honest = kind is None
        self.main = []              # list[State]
        self.prob = []              # list[(State, t_in)]   (D2)
        self.known_c = [0] * R      # last true own-counter seen from each replica
        self.agg = [0] * R          # attacker bookkeeping: aggregate of labels seen


class Sim:
    def __init__(self, cfg: RunConfig, trace, p: Params):
        self.cfg, self.p = cfg, p
        R, L = p.n_replicas, p.n_relays
        self.R, self.L = R, L
        d = cfg.defense
        self.d1 = "D1" in d
        self.d2 = ("D2" in d) and cfg.B > 0
        self.d3 = "D3" in d
        self.B = cfg.B
        self.sbytes = p.blob_bytes + p.counter_bytes * R
        self._id = 0
        # replicas
        self.rcon = [[0] * R for _ in range(R)]   # true content (update counts per origin)
        self.rvec = [[0] * R for _ in range(R)]   # believed version vector
        self.rcache = [None] * R
        self.produced = [0] * R
        # relays / attackers (paired design: same placement for every defense, same seed)
        rng = np.random.default_rng(777 + cfg.seed)
        perm = rng.permutation(L)
        n_bad = int(round(cfg.f / 100.0 * L)) if cfg.attack != "none" else 0
        bad = set(int(x) for x in perm[:n_bad])
        self.relays = [Relay(i, R, cfg.attack if i in bad else None) for i in range(L)]
        self.honest_ids = [r.idx for r in self.relays if r.honest]
        # workload
        rng2 = np.random.default_rng(555 + cfg.seed)
        phase = rng2.uniform(0, p.upd_period_s, R)
        ut, ur = [], []
        for i in range(R):
            for k in range(p.n_updates_per_replica):
                ut.append(p.upd_start_s + phase[i] + k * p.upd_period_s)
                ur.append(i)
        self.upd_t, self.upd_r = np.array(ut), np.array(ur)
        self.t_last = float(self.upd_t.max())
        self.trace = trace
        # metrics
        self.bytes = 0
        self.ops = 0
        self.contacts_h = 0
        self.peak_states = 0
        self.detected = 0
        self.sig_rej = 0
        self.label_rej = 0
        self.conv_time = None
        self.ever = [0] * R
        self.series_missing, self.series_lost, self.series_store = [], [], []
        self.lost_peak = 0

    # ------------------------------------------------------------------ helpers
    def new_state(self, label, content, valid=True):
        self._id += 1
        return State(self._id, label, content, valid)

    def replica_state(self, i):
        lab, con = tuple(self.rvec[i]), tuple(self.rcon[i])
        c = self.rcache[i]
        if c is None or c.label != lab or c.content != con:
            c = self.new_state(lab, con)
            self.rcache[i] = c
        return c

    def corroborated(self, rl, label):
        return all(map(ge, rl.known_c, label))

    # ------------------------------------------------------------------ replicas
    def replica_receive(self, i, s):
        if not s.valid:                       # signature check fails
            self.sig_rej += 1
            return
        con, vec = self.rcon[i], self.rvec[i]
        if self.d1:                           # D1: label bound to the state
            if s.label != s.content:
                self.label_rej += 1
                return
            for j in range(self.R):
                if s.content[j] > con[j]:
                    con[j] = s.content[j]
                    vec[j] = con[j]
        else:                                 # base protocol, Algorithm 2: pointwise max of labels
            if all(map(ge, vec, s.label)):
                return
            for j in range(self.R):
                if s.content[j] > con[j]:
                    con[j] = s.content[j]
                if j != i and s.label[j] > vec[j]:
                    vec[j] = s.label[j]
                if j == i:
                    vec[j] = con[j]
                elif vec[j] < con[j]:
                    vec[j] = con[j]

    # ------------------------------------------------------------------ relay store logic
    def normalize(self, rl, pool, trusted, now, use_d2):
        """Discard dominated states, then greedy set cover. Dominated states go to the
        probation buffer (D2) unless some dominator is corroborated/trusted."""
        seen, P = set(), []
        for s in pool:
            if s.id not in seen:
                seen.add(s.id)
                P.append(s)
        n = len(P)
        self.ops += n * n
        nd, to_prob = [], []
        for s in P:
            dominated = hard = False
            for d in P:
                if d is s:
                    continue
                if all(map(ge, d.label, s.label)):
                    if d.label == s.label:
                        if d.id < s.id:
                            dominated = hard = True
                        continue
                    dominated = True
                    if d.id in trusted or self.corroborated(rl, d.label):
                        hard = True
            if not dominated:
                nd.append(s)
            elif use_d2 and not hard:
                to_prob.append(s)
        # greedy set cover over the aggregate vector
        chosen = []
        if nd:
            R = self.R
            agg = [max(s.label[j] for s in nd) for j in range(R)]
            unc = {j for j in range(R) if agg[j] > 0}
            while unc:
                best = max(nd, key=lambda s: (sum(1 for j in unc if s.label[j] == agg[j]), -s.id))
                chosen.append(best)
                unc -= {j for j in unc if best.label[j] == agg[j]}
        rl.main = chosen
        if use_d2:
            ids_main = {s.id for s in chosen}
            ids_prob = {s.id for s, _ in rl.prob}
            for s in to_prob:
                if s.id not in ids_main and s.id not in ids_prob:
                    rl.prob.append((s, now))
            rl.prob = [(s, t) for s, t in rl.prob
                       if s.id not in ids_main and now - t <= self.p.prob_ttl_s]
            while len(rl.prob) > self.B:
                rl.prob.pop(0)
        sz = len(rl.main) + len(rl.prob)
        if sz > self.peak_states and rl.honest:
            self.peak_states = sz

    # ------------------------------------------------------------------ attackers
    def attacker_offer(self, rl):
        p = self.p
        if rl.kind == "fake_small" or rl.kind == "fake_large":
            dl = p.fake_small_delta if rl.kind == "fake_small" else p.fake_large_delta
            lab = tuple(a + dl for a in rl.agg)
            return [self.new_state(lab, (0,) * self.R, valid=False)]
        if rl.kind == "relabel":
            return [self.new_state(tuple(c + p.relabel_delta for c in s.content), s.content)
                    for s in rl.main]
        return []                                   # blackhole: forwards nothing

    def attacker_ingest(self, rl, states, now):
        good = [s for s in states if s.valid]
        for s in good:
            for j in range(self.R):
                if s.label[j] > rl.agg[j]:
                    rl.agg[j] = s.label[j]
        self.normalize(rl, rl.main + good, set(), now, False)

    # ------------------------------------------------------------------ contacts
    def contact_relay_replica(self, x, ri, now):
        rl = self.relays[x]
        if not rl.honest:
            if rl.kind != "blackhole":
                for s in self.attacker_offer(rl):
                    self.replica_receive(ri, s)
            self.attacker_ingest(rl, [self.replica_state(ri)], now)
            return
        self.contacts_h += 1
        c = self.rcon[ri][ri]                       # replica's true own counter (D3 evidence)
        if self.d3:
            bad = [s for s in rl.main if s.label[ri] > c]
            badp = [(s, t) for s, t in rl.prob if s.label[ri] > c]
            self.ops += len(rl.main) + len(rl.prob)
            if bad or badp:
                self.detected += len(bad) + len(badp)
                bad_ids = {s.id for s in bad} | {s.id for s, _ in badp}
                rl.main = [s for s in rl.main if s.id not in bad_ids]
                rl.main += [s for s, _ in rl.prob if s.id not in bad_ids]   # restore probation
                rl.prob = []
        rl.known_c[ri] = c
        offered = rl.main + [s for s, _ in rl.prob]
        for s in offered:
            self.replica_receive(ri, s)
        rs = self.replica_state(ri)
        for j in range(self.R):                     # updates handed to the relay layer
            if rs.content[j] > self.ever[j]:
                self.ever[j] = rs.content[j]
        self.bytes += (len(offered) + 1) * self.sbytes
        pool = [s for s in rl.main if s.id != rs.id] + [rs]
        rl.prob = [(s, t) for s, t in rl.prob if not all(map(ge, rs.label, s.label))]
        self.normalize(rl, pool, {rs.id}, now, self.d2)

    def contact_relay_relay(self, a, b, now):
        A, B = self.relays[a], self.relays[b]
        if not A.honest and not B.honest:
            return
        self.contacts_h += 1
        if A.honest and B.honest:
            sa, sb = list(A.main), list(B.main)
            self.bytes += (len(sa) + len(sb)) * self.sbytes
            ida, idb = {s.id for s in sa}, {s.id for s in sb}
            if not idb <= ida:
                self.normalize(A, sa + sb, set(), now, self.d2)
            if not ida <= idb:
                self.normalize(B, sb + sa, set(), now, self.d2)
        else:
            H, D = (A, B) if A.honest else (B, A)
            sh = list(H.main)
            offer = self.attacker_offer(D)
            self.bytes += (len(sh) + len(offer)) * self.sbytes
            if offer:
                self.normalize(H, sh + offer, set(), now, self.d2)
            if D.kind != "blackhole":
                self.attacker_ingest(D, sh, now)

    # ------------------------------------------------------------------ metrics
    def converged(self):
        pr = self.produced
        return all(self.rcon[i][j] == pr[j] for i in range(self.R) for j in range(self.R))

    def sample(self):
        R = self.R
        pr = self.produced
        missing = sum(pr[j] - self.rcon[i][j] for i in range(R) for j in range(R))
        cov = [0] * R
        tot = 0
        for i in self.honest_ids:
            rl = self.relays[i]
            sts = rl.main + [s for s, _ in rl.prob]
            tot += len(sts)
            for s in sts:
                if s.valid:
                    for j in range(R):
                        if s.content[j] > cov[j]:
                            cov[j] = s.content[j]
        lost = 0
        for j in range(R):
            if cov[j] > self.ever[j]:
                self.ever[j] = cov[j]
            minrep = min(self.rcon[i][j] for i in range(R))
            lost += max(0, self.ever[j] - max(cov[j], minrep))
        self.lost_peak = max(self.lost_peak, lost)
        self.series_missing.append(missing)
        self.series_lost.append(lost)
        self.series_store.append(tot / max(1, len(self.honest_ids)))

    # ------------------------------------------------------------------ main loop
    def run(self):
        p = self.p
        tt, ta, tb = self.trace
        nc = len(tt)
        times = np.concatenate([self.upd_t, tt])
        order = np.argsort(times, kind="stable")
        ev_t = times[order].tolist()
        ev_i = order.tolist()
        nu = len(self.upd_t)
        ta_l, tb_l, ur_l = ta.tolist(), tb.tolist(), self.upd_r.tolist()
        L = self.L
        next_sample = 0.0
        for t, ix in zip(ev_t, ev_i):
            while next_sample <= t and next_sample <= p.duration_s:
                self.sample()
                next_sample += p.sample_dt_s
            if ix < nu:
                r = ur_l[ix]
                self.rcon[r][r] += 1
                self.rvec[r][r] = self.rcon[r][r]
                self.produced[r] += 1
                continue
            k = ix - nu
            a, b = ta_l[k], tb_l[k]
            if b >= L:
                self.contact_relay_replica(a, b - L, t)
                if self.conv_time is None and t >= self.t_last and self.converged():
                    self.conv_time = t
            else:
                self.contact_relay_relay(a, b, t)
        while next_sample <= p.duration_s:
            self.sample()
            next_sample += p.sample_dt_s
        return self.result()

    def result(self):
        R = self.R
        total = sum(self.produced)
        phantom = sum(self.rvec[i][j] - self.rcon[i][j] for i in range(R) for j in range(R))
        ch = max(1, self.contacts_h)
        return dict(
            converged=self.conv_time is not None,
            latency=(self.conv_time - self.t_last) if self.conv_time is not None else None,
            final_missing=self.series_missing[-1],
            missing_frac=self.series_missing[-1] / (total * R),
            lost_peak=self.lost_peak / total,
            lost_final=self.series_lost[-1] / total,
            storage_mean=float(np.mean(self.series_store)),
            storage_peak=self.peak_states,
            bytes_per_contact=self.bytes / ch,
            ops_per_contact=self.ops / ch,
            contacts_h=self.contacts_h,
            detected=self.detected,
            sig_rej=self.sig_rej,
            label_rej=self.label_rej,
            phantom=phantom,
            series_missing=self.series_missing,
            series_lost=self.series_lost,
        )


def run_one(cfg: RunConfig, trace, p: Params):
    return Sim(cfg, trace, p).run()
