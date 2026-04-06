"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 23/03/2026
Comparison view: three scenarios on the same initial grid.
  Scenario 1 — random, no memory, no communication
  Scenario 2 — strategy + memory, no communication
  Scenario 3 — strategy + memory + communication (full system)

Launch with:
    solara run comparison_server.py
"""

import threading
import time
import types

import matplotlib.pyplot as plt
import solara
from agents import GreenRobot, RedRobot, YellowRobot
from matplotlib import patches
from matplotlib.figure import Figure
from model import DEFAULT_PARAMS, RobotMissionModel
from objects import Waste, WasteDisposalZone
from utils import Color, Zone

# ── Palette ───────────────────────────────────────────────────────────────────
ZONE_COLORS = {Zone.Z1: "#d4edda", Zone.Z2: "#fff3cd", Zone.Z3: "#f8d7da"}
ROBOT_COLORS = {GreenRobot: "#28a745", YellowRobot: "#ffc107", RedRobot: "#dc3545"}
WASTE_COLORS = {Color.GREEN: "#8BC34A", Color.YELLOW: "#FFD700", Color.RED: "#FF5733"}
DISPOSAL_COLOR = "#6f42c1"

RENDER_EVERY = 1  # re-render every N simulation steps

# ── Scenario definitions ──────────────────────────────────────────────────────
SCENARIOS = [
    {
        "label": "Scénario 1",
        "subtitle": "Aléatoire — pas de patrouille, pas de mémoire, pas de communication",
        "accent": "#6c757d",
        "no_comms": True,
        "kwargs": dict(robots_behavior="random"),
    },
    {
        "label": "Scénario 2",
        "subtitle": "Patrouille + mémoire — sans communication",
        "accent": "#0d6efd",
        "no_comms": True,
        "kwargs": dict(robots_behavior="memory"),
    },
    {
        "label": "Scénario 3",
        "subtitle": "Patrouille + mémoire + communication",
        "accent": "#198754",
        "no_comms": False,
        "kwargs": dict(robots_behavior="communication"),
    },
]


# ── Model factory ─────────────────────────────────────────────────────────────


def _noop_broadcast(self):
    pass


def _make_models(seed: int, params: dict) -> list:
    result = []
    for scenario in SCENARIOS:
        m = RobotMissionModel(seed=seed, **params, **scenario["kwargs"])
        if scenario["no_comms"]:
            for agent in m.agents:
                if hasattr(agent, "_broadcast_knowledge"):
                    agent._broadcast_knowledge = types.MethodType(
                        _noop_broadcast, agent
                    )
        result.append(m)
    return result


# ── Drawing helpers ───────────────────────────────────────────────────────────


def _draw_grid(ax, model, accent):
    W, H, zw = model.width, model.height, model.zone_width

    ax.add_patch(patches.Rectangle((0, 0), zw, H, color=ZONE_COLORS[Zone.Z1], zorder=0))
    ax.add_patch(
        patches.Rectangle((zw, 0), zw, H, color=ZONE_COLORS[Zone.Z2], zorder=0)
    )
    ax.add_patch(
        patches.Rectangle(
            (2 * zw, 0), W - 2 * zw, H, color=ZONE_COLORS[Zone.Z3], zorder=0
        )
    )
    ax.add_patch(
        patches.Rectangle(
            (0, 0), W, H, fill=False, edgecolor="#555", linewidth=1.5, zorder=1
        )
    )

    for x in range(W + 1):
        ax.axvline(x, color="gray", linewidth=0.2, alpha=0.35)
    for y in range(H + 1):
        ax.axhline(y, color="gray", linewidth=0.2, alpha=0.35)
    ax.axvline(zw, color="#555", linewidth=1.5, linestyle="--", alpha=0.6)
    ax.axvline(2 * zw, color="#555", linewidth=1.5, linestyle="--", alpha=0.6)

    for x in range(W):
        for y in range(H):
            cell = model.grid.get_cell_list_contents([(x, y)])
            if any(isinstance(a, WasteDisposalZone) for a in cell):
                ax.add_patch(
                    patches.Rectangle(
                        (x + 0.05, y + 0.05),
                        0.9,
                        0.9,
                        color=DISPOSAL_COLOR,
                        alpha=0.3,
                        zorder=1,
                    )
                )
                ax.text(
                    x + 0.5,
                    y + 0.5,
                    "⬛",
                    ha="center",
                    va="center",
                    fontsize=7,
                    zorder=3,
                )
            wo = 0.0
            for a in cell:
                if isinstance(a, Waste) and a.pos is not None:
                    ax.add_patch(
                        patches.Rectangle(
                            (x + 0.1 + wo, y + 0.1),
                            0.22,
                            0.22,
                            color=WASTE_COLORS[a.waste_type],
                            zorder=2,
                        )
                    )
                    wo += 0.20
            for a in cell:
                for RCls, rcol in ROBOT_COLORS.items():
                    if isinstance(a, RCls):
                        ax.add_patch(
                            plt.Circle((x + 0.5, y + 0.5), 0.33, color=rcol, zorder=4)
                        )
                        short = {GreenRobot: "G", YellowRobot: "Y", RedRobot: "R"}[RCls]
                        tc = "white" if RCls != YellowRobot else "#333"
                        ax.text(
                            x + 0.5,
                            y + 0.5,
                            f"{len(a.carrying)}{short}",
                            ha="center",
                            va="center",
                            fontsize=6,
                            color=tc,
                            fontweight="bold",
                            zorder=5,
                        )

    ax.text(zw / 2, H + 0.2, "z1", ha="center", fontsize=8, color="#2d6a2d")
    ax.text(zw * 1.5, H + 0.2, "z2", ha="center", fontsize=8, color="#7a5c00")
    ax.text(zw * 2.5, H + 0.2, "z3", ha="center", fontsize=8, color="#8b1a1a")
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")
    status = "✓ terminé" if not model.running else f"step {model.steps}"
    ax.set_title(
        f"{status}  —  déposés : {model.nb_collected_wastes}",
        fontsize=9,
        color=accent,
        pad=16,
    )


def _draw_ratio(ax, model, accent):
    df = model.datacollector.get_model_vars_dataframe()
    if df.empty or "Ratio collecté" not in df.columns:
        ax.text(
            0.5,
            0.5,
            "Pas encore de données",
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="#aaa",
        )
        ax.set_axis_off()
        return
    ax.plot(df.index, df["Ratio collecté"], color=accent, linewidth=2)
    ax.fill_between(df.index, df["Ratio collecté"], alpha=0.10, color=accent)
    ax.set_xlim(0, model.max_step)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Step", fontsize=8)
    ax.set_ylabel("Ratio collecté", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.2)
    if len(df) > 0:
        final = df["Ratio collecté"].iloc[-1]
        ax.annotate(
            f"{final:.0%}",
            xy=(df.index[-1], final),
            xytext=(-32, 6),
            textcoords="offset points",
            fontsize=8,
            color=accent,
            fontweight="bold",
        )


# ── Solara components ─────────────────────────────────────────────────────────


@solara.component
def ScenarioPanel(model, meta, tick):
    # tick is a plain prop — parent re-renders with new tick → this re-renders too
    accent = meta["accent"]

    fig_grid = Figure(figsize=(5.5, 3.8))
    _draw_grid(fig_grid.subplots(), model, accent)
    fig_grid.tight_layout(pad=0.2)
    fig_grid.subplots_adjust(left=0.01, right=0.99, bottom=0.02, top=0.88)

    fig_ratio = Figure(figsize=(5.5, 2.6))
    _draw_ratio(fig_ratio.subplots(), model, accent)
    fig_ratio.tight_layout(pad=0.8)

    with solara.Column(
        style={
            "border": f"2px solid {accent}",
            "border-radius": "10px",
            "padding": "12px",
            "background": "#fafafa",
            "min-width": "300px",
            "flex": "1",
        }
    ):
        solara.Text(
            meta["label"],
            style={"font-weight": "700", "font-size": "15px", "color": accent},
        )
        solara.Text(
            meta["subtitle"],
            style={"font-size": "11px", "color": "#666", "margin-bottom": "6px"},
        )
        solara.FigureMatplotlib(fig_grid)
        solara.FigureMatplotlib(fig_ratio)


@solara.component
def ComparisonView():
    seed, set_seed = solara.use_state(42)
    width, set_width = solara.use_state(DEFAULT_PARAMS["width"])
    height, set_height = solara.use_state(DEFAULT_PARAMS["height"])
    n_green_robots, set_n_green_robots = solara.use_state(
        DEFAULT_PARAMS["n_green_robots"]
    )
    n_yellow_robots, set_n_yellow_robots = solara.use_state(
        DEFAULT_PARAMS["n_yellow_robots"]
    )
    n_red_robots, set_n_red_robots = solara.use_state(DEFAULT_PARAMS["n_red_robots"])
    n_green_wastes, set_n_green_wastes = solara.use_state(
        DEFAULT_PARAMS["n_green_wastes"]
    )
    n_yellow_wastes, set_n_yellow_wastes = solara.use_state(
        DEFAULT_PARAMS["n_yellow_wastes"]
    )
    n_red_wastes, set_n_red_wastes = solara.use_state(DEFAULT_PARAMS["n_red_wastes"])
    max_step, set_max_step = solara.use_state(DEFAULT_PARAMS["max_step"])
    models, set_models = solara.use_state([])
    is_running, set_is_running = solara.use_state(False)
    tick, set_tick = solara.use_state(0)

    # cancel_flag: a one-element list used as a mutable cell so the thread
    # closure can see mutations made from the main thread after launch.
    cancel_flag = solara.use_ref([False])

    def build_params():
        return dict(
            width=width,
            height=height,
            n_green_robots=n_green_robots,
            n_yellow_robots=n_yellow_robots,
            n_red_robots=n_red_robots,
            n_green_wastes=n_green_wastes,
            n_yellow_wastes=n_yellow_wastes,
            n_red_wastes=n_red_wastes,
            max_step=max_step,
        )

    def _launch_thread(current_models):
        cancel_flag.current[0] = False

        def loop():
            step_count = 0
            flag = cancel_flag.current
            while not flag[0]:
                if not current_models or all(not m.running for m in current_models):
                    set_is_running(False)
                    set_tick(lambda t: t + 1)
                    break
                for m in current_models:
                    if m.running:
                        m.step()
                step_count += 1
                if step_count % RENDER_EVERY == 0:
                    # set_* is thread-safe: schedules a re-render without
                    # touching the render cycle directly
                    set_tick(lambda t: t + 1)
                time.sleep(0.005)  # tiny yield to keep UI responsive

        threading.Thread(target=loop, daemon=True).start()

    def on_reset():
        cancel_flag.current[0] = True  # stop any running thread
        set_is_running(False)
        new_models = _make_models(seed, build_params())
        set_models(new_models)
        set_tick(lambda t: t + 1)

    def on_step():
        if not models:
            return
        for m in models:
            if m.running:
                m.step()
        set_tick(lambda t: t + 1)

    def on_play():
        if not models:
            new_models = _make_models(seed, build_params())
            set_models(new_models)
            set_tick(lambda t: t + 1)
            set_is_running(True)
            _launch_thread(new_models)
        else:
            set_is_running(True)
            _launch_thread(models)

    def on_pause():
        cancel_flag.current[0] = True
        set_is_running(False)

    # ── UI ────────────────────────────────────────────────────────────────────
    with solara.Column(
        style={"padding": "20px", "font-family": "sans-serif", "max-width": "1600px"}
    ):
        solara.Text(
            "Comparaison de scénarios",
            style={"font-size": "22px", "font-weight": "800", "margin-bottom": "2px"},
        )
        solara.Text(
            "Même grille initiale — trois stratégies robots",
            style={"font-size": "13px", "color": "#666", "margin-bottom": "16px"},
        )

        with solara.Card(
            title="Paramètres", elevation=1, style={"margin-bottom": "14px"}
        ):
            with solara.Row(style={"flex-wrap": "wrap", "gap": "24px"}):
                with solara.Column(style={"min-width": "200px"}):
                    solara.InputInt("Seed", value=seed, on_value=set_seed)
                    solara.SliderInt(
                        "Largeur",
                        value=width,
                        on_value=set_width,
                        min=6,
                        max=36,
                        step=3,
                    )
                    solara.SliderInt(
                        "Hauteur", value=height, on_value=set_height, min=3, max=36
                    )
                with solara.Column(style={"min-width": "200px"}):
                    solara.SliderInt(
                        "Robots verts",
                        value=n_green_robots,
                        on_value=set_n_green_robots,
                        min=1,
                        max=10,
                    )
                    solara.SliderInt(
                        "Robots jaunes",
                        value=n_yellow_robots,
                        on_value=set_n_yellow_robots,
                        min=1,
                        max=10,
                    )
                    solara.SliderInt(
                        "Robots rouges",
                        value=n_red_robots,
                        on_value=set_n_red_robots,
                        min=1,
                        max=10,
                    )
                with solara.Column(style={"min-width": "200px"}):
                    solara.SliderInt(
                        "Déchets verts",
                        value=n_green_wastes,
                        on_value=set_n_green_wastes,
                        min=4,
                        max=64,
                        step=4,
                    )
                    solara.SliderInt(
                        "Déchets jaunes",
                        value=n_yellow_wastes,
                        on_value=set_n_yellow_wastes,
                        min=0,
                        max=64,
                        step=2,
                    )
                    solara.SliderInt(
                        "Déchets rouges",
                        value=n_red_wastes,
                        on_value=set_n_red_wastes,
                        min=0,
                        max=64,
                        step=1,
                    )
                with solara.Column(style={"min-width": "200px"}):
                    solara.SliderInt(
                        "Pas maximum",
                        value=max_step,
                        on_value=set_max_step,
                        min=50,
                        max=500,
                        step=10,
                    )

        with solara.Row(
            style={"gap": "10px", "margin-bottom": "18px", "align-items": "center"}
        ):
            solara.Button("⟳  Réinitialiser", on_click=on_reset)
            if not is_running:
                solara.Button("▶  Démarrer", on_click=on_play, color="primary")
            else:
                solara.Button("⏸  Pause", on_click=on_pause, color="primary")
            solara.Button("→  Un pas", on_click=on_step, disabled=is_running)
            if models:
                solara.Text(
                    f"Step : {models[0].steps}",
                    style={"font-size": "13px", "color": "#555", "margin-left": "10px"},
                )

        if not models:
            solara.Text(
                "Cliquez sur « Réinitialiser » ou « Démarrer » pour lancer la comparaison.",
                style={"color": "#999", "font-size": "14px", "padding": "30px 0"},
            )
        else:
            with solara.Row(
                style={"gap": "14px", "align-items": "flex-start", "flex-wrap": "wrap"}
            ):
                for model, meta in zip(models, SCENARIOS):
                    ScenarioPanel(model, meta, tick)


@solara.component
def Page():
    ComparisonView()
