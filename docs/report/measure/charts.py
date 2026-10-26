"""Charts for Chapter 3, drawn from the measurements in docs/report/data/.

    uv run --no-project --with matplotlib python docs/report/measure/charts.py

Print figures, so no hover layer. Colours are the first three slots of the
reference categorical palette (they pass the all-pairs check), text stays in
neutral ink, bars are thin with a hairline solid grid, and no chart uses a
second y-axis.
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
FIGS = HERE.parent / "figures"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "text.color": INK,
    "axes.labelcolor": INK2,
    "axes.edgecolor": GRID,
    "axes.linewidth": 1,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "grid.linestyle": "-",
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
})


def save(fig, name):
    fig.savefig(FIGS / name)
    plt.close(fig)
    print("wrote", name)


def concurrency():
    d = json.loads((DATA / "concurrency.json").read_text())
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    labels = ["Booking requests sent", "Places on the trek", "Bookings accepted", "Places left afterwards"]
    values = [d["clients"], d["slots"], d["succeeded"], d["available_slots_after"]]
    colors = [INK2, BLUE, AQUA, ORANGE]
    bars = ax.barh(labels[::-1], values[::-1], height=0.45, color=colors[::-1])
    for bar, v in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.6, bar.get_y() + bar.get_height() / 2, str(v),
                va="center", color=INK, fontsize=9)
    ax.set_xlim(0, max(values) * 1.12)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("count")
    save(fig, "fig-3-concurrency.png")


def latency():
    d = json.loads((DATA / "latency.json").read_text())
    names = list(d)
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    width = 0.22
    for k, (pct, color) in enumerate([("p50", BLUE), ("p90", ORANGE), ("p99", AQUA)]):
        xs = [i + (k - 1) * (width + 0.03) for i in range(len(names))]
        vals = [d[n][pct] for n in names]
        ax.bar(xs, vals, width=width, color=color, label=pct)
        for x, v in zip(xs, vals):
            ax.text(x, v + max(vals) * 0.015 + 2, f"{v:.0f}", ha="center", va="bottom", fontsize=7.5, color=INK2)
    ax.set_xticks(range(len(names)), [n.replace(" (", "\n(") for n in names])
    ax.set_ylabel("response time (ms)")
    ax.set_ylim(0, max(d[n]["p99"] for n in names) * 1.18)
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8)
    save(fig, "fig-3-latency.png")


def keda():
    rows = list(csv.DictReader((DATA / "keda.csv").open()))
    t = [int(r["seconds"]) for r in rows]
    queued = [int(r["queued"] or 0) for r in rows]
    desired = [int(r["worker_replicas"] or 0) for r in rows]
    ready = [int(r["worker_ready"] or 0) for r in rows]

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(6.2, 3.8), sharex=True,
                                      gridspec_kw={"height_ratios": [1.1, 1]})
    top.plot(t, queued, color=BLUE, linewidth=2, solid_capstyle="round")
    top.fill_between(t, queued, color=BLUE, alpha=0.10, linewidth=0)
    top.set_ylabel("messages queued")
    bottom.step(t, ready, where="post", color=AQUA, linewidth=2, label="replicas running")
    bottom.plot(t, desired, linestyle="none", marker="o", markersize=4.5, color=ORANGE,
                markeredgecolor="white", markeredgewidth=1, label="replicas requested by KEDA")
    bottom.set_ylabel("worker replicas")
    bottom.set_xlabel("seconds after 3000 export jobs were queued")
    bottom.set_ylim(0, max(desired + ready) + 2.2)
    bottom.legend(loc="upper center", ncol=2, fontsize=8)
    fig.align_ylabels()
    save(fig, "fig-3-keda.png")


def rollout():
    phases = json.loads((DATA / "rollout.json").read_text())
    fig, ax = plt.subplots(figsize=(6.2, 1.9))
    start = 0
    palette = [BLUE, ORANGE, AQUA, INK2, BLUE]
    for k, (name, end) in enumerate(phases):
        ax.barh([0], [end - start], left=start, height=0.5, color=palette[k % len(palette)],
                edgecolor="white", linewidth=2, label=f"{name} ({end - start} s)")
        start = end
    ax.text(start + 0.6, 0, f"{start} s", va="center", fontsize=9, color=INK)
    ax.set_yticks([])
    ax.set_xlim(0, start * 1.1)
    ax.set_ylim(-0.5, 0.5)
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.02), fontsize=8)
    ax.set_xlabel("seconds since the rollout started")
    ax.grid(axis="y", visible=False)
    save(fig, "fig-3-rollout.png")


def metrics():
    d = json.loads((DATA / "metrics.json").read_text())
    fig, axes = plt.subplots(len(d), 1, figsize=(6.2, 1.5 * len(d)), sharex=True)
    for ax, (name, series) in zip(axes, d.items()):
        xs = [p[0] for p in series["points"]]
        ys = [p[1] for p in series["points"]]
        ax.plot(xs, ys, color=BLUE, linewidth=2)
        ax.fill_between(xs, ys, color=BLUE, alpha=0.10, linewidth=0)
        ax.set_ylabel(series["unit"], fontsize=8)
        ax.set_title(name, loc="left", fontsize=9, color=INK)
    axes[-1].set_xlabel("minutes since the start of the test window")
    fig.tight_layout()
    save(fig, "fig-3-metrics.png")


if __name__ == "__main__":
    for fn in (concurrency, latency, keda, rollout, metrics):
        try:
            fn()
        except FileNotFoundError as e:
            print("skipped", fn.__name__, "-", e.filename)
