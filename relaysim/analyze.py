"""Turn results/runs.jsonl into the E4 and E3 tables (CSV + Markdown) and figures.
    python -m relaysim.analyze --runs results/runs.jsonl --out results
"""
import argparse, json, os
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ATK = ["fake_small", "fake_large", "relabel", "blackhole"]
DEF = ["none", "D1", "D1+D2", "D1+D2+D3"]


def ci(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return 0.0
    return stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))


def load(path):
    """rows = [json.loads(l) for l in open(path)]"""
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    df = pd.DataFrame(rows)
    df["latency"] = df["latency"].astype(float)
    return df


def summarize(g):
    n = len(g)
    lat_cens = g["latency"].fillna(g["latency"].max() if g["latency"].notna().any() else 0)
    return pd.Series(dict(
        n=n,
        conv_rate=g["converged"].mean(),
        latency_h=g["latency"].mean() / 3600,          # converged runs only
        latency_h_ci=ci(g["latency"]) / 3600,
        missing_pct=100 * g["missing_frac"].mean(),    # convergence distance at end of trace
        missing_pct_ci=100 * ci(g["missing_frac"]),
        lost_peak_pct=100 * g["lost_peak"].mean(),
        lost_peak_pct_ci=100 * ci(g["lost_peak"]),
        storage_mean=g["storage_mean"].mean(),
        storage_peak=g["storage_peak"].max(),
        kB_per_contact=g["bytes_per_contact"].mean() / 1024,
        ops_per_contact=g["ops_per_contact"].mean(),
        detected=g["detected"].mean(),
        phantom=g["phantom"].mean(),
    ))


def agg(df, by):
    return df.groupby(by, sort=False).apply(summarize, include_groups=False).reset_index()


def md(df, floatfmt="{:.2f}"):
    cols = list(df.columns)
    s = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    for _, r in df.iterrows():
        s += "| " + " | ".join(floatfmt.format(v) if isinstance(v, (float, np.floating)) else str(v) for v in r) + " |\n"
    return s


def pm(m, c):
    return f"{m:.2f} ± {c:.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="results/runs.jsonl")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    df = load(a.runs)
    df["_v"] = df["defense"] + "|B" + df["B"].astype(str)
    report = []

    # ======================================================= E4 : ablation and cost
    e4a = df[(df.f == 30) & (df.B == 2) & (df.attack.isin(ATK))]
    t = agg(e4a, ["attack", "defense"])
    t["attack"] = pd.Categorical(t["attack"], ATK); t["defense"] = pd.Categorical(t["defense"], DEF)
    t = t.sort_values(["attack", "defense"])
    t.to_csv(f"{a.out}/E4a_ablation_f30.csv", index=False)
    show = pd.DataFrame({
        "attack": t.attack, "defense": t.defense, "conv. rate": t.conv_rate,
        "latency [h] (conv. runs)": [pm(m, c) for m, c in zip(t.latency_h, t.latency_h_ci)],
        "missing at end [%]": [pm(m, c) for m, c in zip(t.missing_pct, t.missing_pct_ci)],
        "lost-update peak [%]": [pm(m, c) for m, c in zip(t.lost_peak_pct, t.lost_peak_pct_ci)],
        "phantom updates/run": t.phantom, "D3 detections/run": t.detected})
    report.append("## E4(a) Ablation at f = 30 %, B = 2 (mean ± 95 % CI, 20 seeds)\n\n" + md(show))

    e4b = df[(df.f == 30) & (df.defense.isin(["D1+D2", "D1+D2+D3"])) & (df.attack.isin(ATK))]
    t = agg(e4b, ["attack", "defense", "B"])
    t["attack"] = pd.Categorical(t["attack"], ATK)
    t = t.sort_values(["attack", "defense", "B"])
    t.to_csv(f"{a.out}/E4b_probation_sweep_f30.csv", index=False)
    show = pd.DataFrame({
        "attack": t.attack, "defense": t.defense, "B": t.B, "conv. rate": t.conv_rate,
        "missing at end [%]": [pm(m, c) for m, c in zip(t.missing_pct, t.missing_pct_ci)],
        "lost-update peak [%]": [pm(m, c) for m, c in zip(t.lost_peak_pct, t.lost_peak_pct_ci)],
        "mean states/relay": t.storage_mean, "peak states": t.storage_peak})
    report.append("## E4(b) Probation size B in {0,2,4} at f = 30 %\n\n" + md(show))

    e4c = df[(df.f == 0)]
    t = agg(e4c, ["defense", "B"])
    t["defense"] = pd.Categorical(t["defense"], DEF)
    t = t.sort_values(["defense", "B"])
    base = t[t.defense == "none"].iloc[0]
    t["latency_vs_none_%"] = 100 * (t.latency_h / base.latency_h - 1)
    t["bytes_vs_none_%"] = 100 * (t.kB_per_contact / base.kB_per_contact - 1)
    t["ops_vs_none_%"] = 100 * (t.ops_per_contact / base.ops_per_contact - 1)
    t.to_csv(f"{a.out}/E4c_overhead_f0.csv", index=False)
    show = pd.DataFrame({
        "defense": t.defense, "B": t.B, "conv. rate": t.conv_rate,
        "latency [h]": [pm(m, c) for m, c in zip(t.latency_h, t.latency_h_ci)],
        "latency Δ%": t["latency_vs_none_%"], "mean states": t.storage_mean, "peak states": t.storage_peak,
        "kB/contact": t.kB_per_contact, "traffic Δ%": t["bytes_vs_none_%"],
        "cmp/contact": t.ops_per_contact, "CPU Δ%": t["ops_vs_none_%"]})
    report.append("## E4(c) Overhead when every relay is honest (f = 0)\n\n" + md(show))

    # ======================================================= E3 : defense effectiveness
    e3 = df[(df.attack.isin(ATK)) & (df.f.isin([10, 30, 50])) & (df.B == 2) & (df.defense.isin(["none", "D1+D2+D3"]))]
    t = agg(e3, ["attack", "f", "defense"])
    t["attack"] = pd.Categorical(t["attack"], ATK)
    t = t.sort_values(["attack", "f", "defense"])
    t.to_csv(f"{a.out}/E3_defense.csv", index=False)
    show = pd.DataFrame({
        "attack": t.attack, "f [%]": t.f, "defense": t.defense, "conv. rate": t.conv_rate,
        "latency [h]": [pm(m, c) for m, c in zip(t.latency_h, t.latency_h_ci)],
        "missing at end [%]": [pm(m, c) for m, c in zip(t.missing_pct, t.missing_pct_ci)],
        "lost-update peak [%]": [pm(m, c) for m, c in zip(t.lost_peak_pct, t.lost_peak_pct_ci)],
        "phantom updates/run": t.phantom})
    report.append("## E3 Defense effectiveness (D1+D2+D3, B = 2) vs. undefended\n\n" + md(show))
    rows = []
    for (atk, f), g in e3.groupby(["attack", "f"]):
        b = g[g.defense == "none"].set_index("seed"); o = g[g.defense == "D1+D2+D3"].set_index("seed")
        d = (b["missing_frac"] - o["missing_frac"]).dropna()
        red = 100 * d.mean() / b["missing_frac"].mean() if b["missing_frac"].mean() > 0 else np.nan
        rows.append(dict(attack=atk, f=f, undefended_missing_pct=100 * b.missing_frac.mean(),
                         defended_missing_pct=100 * o.missing_frac.mean(),
                         paired_reduction_pp=pm(100 * d.mean(), 100 * ci(d)),
                         damage_removed_pct=red,
                         conv_rate_gain_pp=100 * (o.converged.mean() - b.converged.mean())))
    pr = pd.DataFrame(rows)
    pr["attack"] = pd.Categorical(pr["attack"], ATK); pr = pr.sort_values(["attack", "f"])
    pr.to_csv(f"{a.out}/E3_damage_removed.csv", index=False)
    report.append("## E3 Damage removed by the defense (paired by seed)\n\n" + md(pr))
    # open(f"{a.out}/RESULTS.md", "w").write("# Results (generated)\n\n" + "\n".join(report))
    open(f"{a.out}/RESULTS.md", "w", encoding="utf-8").write("# Results (generated)\n\n" + "\n".join(report))

    # ======================================================= figures
    # E3: convergence rate and missing updates vs f
    fig, ax = plt.subplots(2, 4, figsize=(15, 6), sharex=True)
    for c, atk in enumerate(ATK):
        for d, lab, col in [("none", "no defense", "tab:red"), ("D1+D2+D3", "D1+D2+D3 (B=2)", "tab:green")]:
            g = e3[(e3.attack == atk) & (e3.defense == d)]
            fs = sorted(g.f.unique())
            ax[0, c].plot(fs, [g[g.f == f].converged.mean() for f in fs], "o-", color=col, label=lab)
            m = [100 * g[g.f == f].missing_frac.mean() for f in fs]
            e = [100 * ci(g[g.f == f].missing_frac) for f in fs]
            ax[1, c].errorbar(fs, m, yerr=e, fmt="o-", color=col, capsize=3)
        ax[0, c].set_title(atk); ax[0, c].set_ylim(-0.05, 1.05); ax[1, c].set_xlabel("dishonest relays f [%]")
        ax[1, c].set_xticks([10, 30, 50])
    ax[0, 0].set_ylabel("convergence rate"); ax[1, 0].set_ylabel("updates still missing [%]")
    ax[0, 0].legend(); fig.suptitle("E3: defense effectiveness"); fig.tight_layout()
    fig.savefig(f"{a.out}/E3_effectiveness.png", dpi=140); plt.close(fig)

    # E3: convergence distance over time at f = 30
    fig, ax = plt.subplots(1, 4, figsize=(15, 3.4), sharey=True)
    for c, atk in enumerate(ATK):
        for d, lab, col in [("none", "no defense", "tab:red"), ("D1+D2+D3", "D1+D2+D3", "tab:green")]:
            g = e3[(e3.attack == atk) & (e3.defense == d) & (e3.f == 30)]
            S = np.array(g.series_missing.tolist(), float)
            tt = np.arange(S.shape[1]) * 300 / 3600
            ax[c].plot(tt, S.mean(0), color=col, label=lab)
            ax[c].fill_between(tt, S.mean(0) - [ci(S[:, i]) for i in range(S.shape[1])],
                               S.mean(0) + [ci(S[:, i]) for i in range(S.shape[1])], color=col, alpha=.2)
        ax[c].axvline(12, color="gray", ls=":"); ax[c].set_title(f"{atk} (f=30%)"); ax[c].set_xlabel("time [h]")
    ax[0].set_ylabel("missing updates (all replicas)"); ax[0].legend(); fig.tight_layout()
    fig.savefig(f"{a.out}/E3_distance_over_time.png", dpi=140); plt.close(fig)

    # E4(a): ablation bars
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.8))
    w = 0.2
    for k, d in enumerate(DEF):
        g = e4a[e4a.defense == d]
        ax[0].bar(np.arange(4) + (k - 1.5) * w, [100 * g[g.attack == x].missing_frac.mean() for x in ATK], w, label=d)
        ax[1].bar(np.arange(4) + (k - 1.5) * w, [100 * g[g.attack == x].lost_peak.mean() for x in ATK], w, label=d)
    for i, tl in enumerate(["updates missing at end [%]", "lost-update peak [%]"]):
        ax[i].set_xticks(range(4)); ax[i].set_xticklabels(ATK); ax[i].set_ylabel(tl)
    ax[0].legend(); fig.suptitle("E4: ablation at f = 30 %, B = 2"); fig.tight_layout()
    fig.savefig(f"{a.out}/E4_ablation.png", dpi=140); plt.close(fig)

    # E4(b)+(c): B sweep and overhead
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.8))
    for d, col in [("D1+D2", "tab:blue"), ("D1+D2+D3", "tab:green")]:
        for atk, ls in [("fake_large", "-"), ("relabel", "--")]:
            g = e4b[(e4b.defense == d) & (e4b.attack == atk)]
            ax[0].plot([0, 2, 4], [100 * g[g.B == B].missing_frac.mean() for B in (0, 2, 4)], "o" + ls, color=col, label=f"{d}, {atk}")
    ax[0].set_xlabel("probation size B"); ax[0].set_ylabel("updates missing at end [%]"); ax[0].set_xticks([0, 2, 4]); ax[0].legend(fontsize=7)
    t0 = e4c.groupby(["defense", "B"], sort=False).agg(st=("storage_mean", "mean"), kb=("bytes_per_contact", "mean")).reset_index()
    t0["name"] = t0.defense + np.where(t0.defense.str.contains("D2"), " B=" + t0.B.astype(str), "")
    ax[1].bar(range(len(t0)), t0.kb / 1024, color="tab:orange"); ax[1].set_xticks(range(len(t0)))
    ax[1].set_xticklabels(t0.name, rotation=60, ha="right", fontsize=7); ax[1].set_ylabel("kB per contact (f = 0)")
    fig.suptitle("E4: probation-size sweep and honest-network overhead"); fig.tight_layout()
    fig.savefig(f"{a.out}/E4_sweep_overhead.png", dpi=140); plt.close(fig)
    # print(open(f"{a.out}/RESULTS.md").read())
    print("Done. Tables and figures written to", a.out)

if __name__ == "__main__":
    main()
