"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure

Multi-seed benchmark: runs all three scenarios in parallel across N seeds,
then plots averaged metrics with confidence intervals.

Usage:
    python benchmark.py [--seeds N] [--max-step S] [--output-dir DIR]
"""

import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

# ── path setup (needed for worker processes on Windows) ──────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))


def _worker_init():
    if _DIR not in sys.path:
        sys.path.insert(0, _DIR)


# ── scenario definitions (matches comparison_server.py) ──────────────────────
SCENARIOS = ["random", "memory", "communication"]
LABELS = {
    "random": "Aléatoire",
    "memory": "Mémoire",
    "communication": "Communication",
}
COLORS_SCEN = {
    "random": "#6c757d",
    "memory": "#0d6efd",
    "communication": "#198754",
}


# ── single simulation run (executed in worker process) ───────────────────────
def run_single(args: tuple) -> dict:
    scenario, seed, max_step, params_override = args
    _worker_init()
    from model import DEFAULT_PARAMS, RobotMissionModel
    from utils import Color

    params = {**DEFAULT_PARAMS, "robots_behavior": scenario, "seed": seed, "max_step": max_step}
    params.update(params_override)

    import types
    model = RobotMissionModel(**params)
    if scenario == "memory":
        for agent in model.agents:
            if hasattr(agent, "_broadcast_knowledge"):
                agent._broadcast_knowledge = types.MethodType(lambda self: None, agent)
    while model.running:
        model.step()

    df = model.datacollector.get_model_vars_dataframe()
    n = len(df)

    def pad(col):
        arr = df[col].tolist()
        return arr + [arr[-1]] * (max_step - len(arr))

    def pad_color(col, color_key):
        arr = [row[color_key] if isinstance(row, dict) else 0.0 for row in df[col]]
        return arr + [arr[-1]] * (max_step - len(arr))

    from agents import GreenRobot, RedRobot, YellowRobot
    all_robots = (
        list(model.agents_by_type[GreenRobot])
        + list(model.agents_by_type[YellowRobot])
        + list(model.agents_by_type[RedRobot])
    )
    completed = model.nb_wastes == 0 and all(len(r.carrying) == 0 for r in all_robots)

    return {
        "scenario": scenario,
        "seed": seed,
        "steps": n,
        "completed": completed,
        # time series (padded to max_step)
        "ratio_collected": pad("Ratio collecté"),
        "deposited": pad("Déposés"),
        "green_wastes": pad("Déchets verts"),
        "yellow_wastes": pad("Déchets jaunes"),
        "red_wastes": pad("Déchets rouges"),
        # final scalar metrics per color
        "lifespan": {c: df["Durée de vie des déchets"].iloc[-1].get(c, 0) for c in [Color.GREEN, Color.YELLOW, Color.RED]},
        "exploration": {c: df["Ratio d'exploration"].iloc[-1].get(c, 0) for c in [Color.GREEN, Color.YELLOW, Color.RED]},
        "load_balance": {c: df["Load balancing"].iloc[-1].get(c, 0) for c in [Color.GREEN, Color.YELLOW, Color.RED]},
    }


# ── aggregation helpers ───────────────────────────────────────────────────────
def aggregate(results: list[dict], scenario: str) -> dict:
    runs = [r for r in results if r["scenario"] == scenario]

    def ts_stats(key):
        mat = np.array([r[key] for r in runs])  # (n_seeds, max_step)
        return mat.mean(axis=0), mat.std(axis=0)

    def color_stats(key):
        from utils import Color
        colors = [Color.GREEN, Color.YELLOW, Color.RED]
        means, stds = {}, {}
        for c in colors:
            vals = np.array([r[key][c] for r in runs])
            means[c], stds[c] = vals.mean(), vals.std()
        return means, stds

    completed_runs = [r for r in runs if r["completed"]]
    steps_completed = [r["steps"] for r in completed_runs]

    return {
        "steps_mean": np.mean([r["steps"] for r in runs]),
        "steps_std": np.std([r["steps"] for r in runs]),
        "steps_all": [r["steps"] for r in runs],
        "completion_rate": len(completed_runs) / len(runs) if runs else 0.0,
        "steps_completed": steps_completed,
        "ratio_collected": ts_stats("ratio_collected"),
        "deposited": ts_stats("deposited"),
        "green_wastes": ts_stats("green_wastes"),
        "yellow_wastes": ts_stats("yellow_wastes"),
        "red_wastes": ts_stats("red_wastes"),
        "lifespan": color_stats("lifespan"),
        "exploration": color_stats("exploration"),
        "load_balance": color_stats("load_balance"),
    }


# ── plotting ──────────────────────────────────────────────────────────────────
COLOR_NAMES = None  # lazily set after import


def _color_label(c) -> str:
    return c.value.capitalize()


def plot_results(aggs: dict, max_step: int, output_dir: str):
    from utils import Color
    waste_colors = [Color.GREEN, Color.YELLOW, Color.RED]
    waste_hex = {Color.GREEN: "#28a745", Color.YELLOW: "#ffc107", Color.RED: "#dc3545"}

    steps_x = np.arange(max_step)

    # ── Figure 1: time series ─────────────────────────────────────────────────
    fig1, axes1 = plt.subplots(2, 2, figsize=(14, 10))
    fig1.suptitle("Évolution temporelle (moyenne ± 1σ)", fontsize=14, fontweight="bold")

    ts_metrics = [
        ("ratio_collected", "Ratio collecté",          axes1[0, 0]),
        ("green_wastes",    "Déchets verts restants",  axes1[0, 1]),
        ("yellow_wastes",   "Déchets jaunes restants", axes1[1, 0]),
        ("red_wastes",      "Déchets rouges restants", axes1[1, 1]),
    ]

    for key, title, ax in ts_metrics:
        for scen in SCENARIOS:
            mean, std = aggs[scen][key]
            c = COLORS_SCEN[scen]
            ax.plot(steps_x, mean, color=c, label=LABELS[scen], linewidth=1.8)
            ax.fill_between(steps_x, mean - std, mean + std, color=c, alpha=0.15)
        ax.set_title(title)
        ax.set_xlabel("Step")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    fig1.tight_layout()
    fig1.savefig(os.path.join(output_dir, "benchmark_timeseries.png"), dpi=150)
    print("Saved benchmark_timeseries.png")

    # ── Figure 2: final scalar metrics per color + completion + steps boxplot ──
    fig2, axes2 = plt.subplots(1, 5, figsize=(26, 5))
    fig2.suptitle("Métriques finales (moyenne ± 1σ)", fontsize=14, fontweight="bold")

    # Completion rate
    ax_compl = axes2[0]
    rates = [aggs[s]["completion_rate"] * 100 for s in SCENARIOS]
    bars = ax_compl.bar(
        [LABELS[s] for s in SCENARIOS], rates,
        color=[COLORS_SCEN[s] for s in SCENARIOS], alpha=0.85,
    )
    ax_compl.bar_label(bars, fmt="%.0f%%", padding=3, fontsize=9)
    ax_compl.set_ylim(0, 115)
    ax_compl.set_title("Taux de complétion")
    ax_compl.set_ylabel("% runs complétés")
    ax_compl.grid(True, alpha=0.3, axis="y")

    # Steps boxplot — only completed runs
    ax_steps = axes2[1]
    data_completed = [aggs[s]["steps_completed"] for s in SCENARIOS]
    labels_with_n = [
        f"{LABELS[s]}\n(n={len(aggs[s]['steps_completed'])})" for s in SCENARIOS
    ]
    bp = ax_steps.boxplot(
        [d if d else [float("nan")] for d in data_completed],
        labels=labels_with_n,
        patch_artist=True,
        medianprops=dict(color="black", linewidth=2),
    )
    for patch, scen in zip(bp["boxes"], SCENARIOS):
        patch.set_facecolor(COLORS_SCEN[scen])
        patch.set_alpha(0.7)
    ax_steps.set_title("Steps à complétion\n(runs complétés uniquement)")
    ax_steps.set_ylabel("Steps")
    ax_steps.grid(True, alpha=0.3, axis="y")

    scalar_metrics = [
        ("lifespan",     "Durée de vie des déchets (steps)", axes2[2]),
        ("exploration",  "Ratio d'exploration",              axes2[3]),
        ("load_balance", "Load balancing (max/mean)",        axes2[4]),
    ]

    n_scen = len(SCENARIOS)
    n_col = len(waste_colors)
    group_width = 0.8
    bar_width = group_width / n_scen
    x = np.arange(n_col)

    for key, title, ax in scalar_metrics:
        for i, scen in enumerate(SCENARIOS):
            means, stds = aggs[scen][key]
            vals = [means[c] for c in waste_colors]
            errs = [stds[c] for c in waste_colors]
            offsets = x + (i - n_scen / 2 + 0.5) * bar_width
            ax.bar(offsets, vals, bar_width * 0.9, yerr=errs, label=LABELS[scen],
                   color=COLORS_SCEN[scen], alpha=0.85, capsize=4)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels([_color_label(c) for c in waste_colors])
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, axis="y")

    fig2.tight_layout()
    fig2.savefig(os.path.join(output_dir, "benchmark_final_metrics.png"), dpi=150)
    print("Saved benchmark_final_metrics.png")

    plt.close("all")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Multi-seed scenario benchmark")
    parser.add_argument("--seeds", type=int, default=20, help="Number of seeds (default: 20)")
    parser.add_argument("--max-step", type=int, default=200, help="Max steps per run (default: 200)")
    parser.add_argument("--workers", type=int, default=None, help="Parallel workers (default: CPU count)")
    parser.add_argument("--output-dir", type=str, default=os.path.join(_DIR, "figures"), help="Output directory for figures")
    args = parser.parse_args()

    seeds = list(range(args.seeds,args.seeds+1))
    #seeds = list(range(args.seeds))
    tasks = [(scen, seed, args.max_step, {}) for scen in SCENARIOS for seed in seeds]
    total = len(tasks)

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"Running {total} simulations ({len(SCENARIOS)} scenarios × {len(seeds)} seeds) ...")

    results = []
    errors = []
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_worker_init) as pool:
        futures = {pool.submit(run_single, task): task for task in tasks}
        with tqdm(total=total, desc="Simulations", unit="run") as pbar:
            for fut in as_completed(futures):
                task = futures[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    errors.append((task[0], task[1], e))
                pbar.update(1)

    if errors:
        for scen, seed, e in errors:
            tqdm.write(f"[ERROR] {scen} seed={seed}: {e}")

    print("Aggregating and plotting ...")
    aggs = {scen: aggregate(results, scen) for scen in SCENARIOS}

    header = f"{'Scenario':<16} {'Avg steps':>10} {'Std steps':>10} {'Final ratio':>12}"
    print(f"\n{header}\n{'-' * len(header)}")
    for scen in SCENARIOS:
        a = aggs[scen]
        print(f"{LABELS[scen]:<16} {a['steps_mean']:>10.1f} {a['steps_std']:>10.1f} {aggs[scen]['ratio_collected'][0][-1]:>12.3f}")

    plot_results(aggs, args.max_step, args.output_dir)


if __name__ == "__main__":
    main()
