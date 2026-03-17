import matplotlib.pyplot as plt
import solara
from agents import GreenRobot, RedRobot, Robot, YellowRobot
from matplotlib import patches
from matplotlib.figure import Figure
from mesa import Agent
from model import RobotMissionModel
from objects import Radioactivity, Waste, WasteDisposalZone
from utils import Color, Zone

# Couleurs
COLORS = {
    Zone.Z1: "#d4edda",
    Zone.Z2: "#fff3cd",
    Zone.Z3: "#f8d7da",
    GreenRobot: "#28a745",
    YellowRobot: "#ffc107",
    RedRobot: "#dc3545",
    Color.GREEN: "#8BC34A",
    Color.YELLOW: "#FFD700",
    Color.RED: "#FF5733",
    WasteDisposalZone: "#6f42c1",
}


def agent_portrayal(agent: Agent):

    # Radioactivité
    if isinstance(agent, Radioactivity):
        return {"zorder": -1, "color": "none"}

    # Zone de dépôt
    if isinstance(agent, WasteDisposalZone):
        return {
            "color": COLORS[WasteDisposalZone],
            "size": 30,
            "zorder": 1,
        }

    # Déchets
    if isinstance(agent, Waste):
        return {
            "color": COLORS[agent.waste_type],
            "size": 100,
            "zorder": 2,
            "marker": "x",
        }

    # Robots
    base_robot = {
        "marker": "o",
        "size": 30,
        "zorder": 3,
    }
    if isinstance(agent, GreenRobot):
        return {
            **base_robot,
            "color": COLORS[GreenRobot],
        }
    if isinstance(agent, YellowRobot):
        return {
            **base_robot,
            "color": COLORS[YellowRobot],
        }
    if isinstance(agent, RedRobot):
        return {
            **base_robot,
            "color": COLORS[RedRobot],
        }

    return {}


def post_process(ax):
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_facecolor("whitesmoke")


@solara.component
def SpaceGraph(model: RobotMissionModel):
    """Dessine la grille à un instant t."""
    fig = Figure(figsize=(10, 8))
    ax = fig.subplots()
    ax.clear()
    W, H = model.width, model.height
    zw = model.zone_width

    # ── Fond des zones ────────────────────────
    ax.add_patch(patches.Rectangle((0, 0), zw, H, color=COLORS[Zone.Z1], zorder=0))
    ax.add_patch(patches.Rectangle((zw, 0), zw, H, color=COLORS[Zone.Z2], zorder=0))
    ax.add_patch(
        patches.Rectangle((2 * zw, 0), W - 2 * zw, H, color=COLORS[Zone.Z3], zorder=0)
    )

    # ── Grille ────────────────────────────────
    for x in range(W + 1):
        ax.axvline(x, color="gray", linewidth=0.3, alpha=0.5)
    for y in range(H + 1):
        ax.axhline(y, color="gray", linewidth=0.3, alpha=0.5)

    # ── Frontières de zones ───────────────────
    ax.axvline(zw, color="#555", linewidth=1.5, linestyle="--", alpha=0.7)
    ax.axvline(2 * zw, color="#555", linewidth=1.5, linestyle="--", alpha=0.7)

    # ── Contenu des cellules ──────────────────
    for x in range(W):
        for y in range(H):
            cell = model.grid.get_cell_list_contents([(x, y)])

            # Zone de dépôt
            if any(isinstance(a, WasteDisposalZone) for a in cell):
                ax.add_patch(
                    patches.Rectangle(
                        (x + 0.05, y + 0.05),
                        0.9,
                        0.9,
                        color=COLORS[WasteDisposalZone],
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
                    fontsize=9,
                    zorder=3,
                )

            # Déchets (petits carrés)
            waste_offset = 0.0
            for a in cell:
                if isinstance(a, Waste) and a.pos is not None:
                    c = COLORS[a.waste_type]
                    ax.add_patch(
                        patches.Rectangle(
                            (x + 0.1 + waste_offset, y + 0.1),
                            0.25,
                            0.25,
                            color=c,
                            zorder=2,
                        )
                    )
                    waste_offset += 0.22

            # Robots (cercles)
            for a in cell:
                if isinstance(a, GreenRobot):
                    circle = plt.Circle(
                        (x + 0.5, y + 0.5), 0.35, color=COLORS[GreenRobot], zorder=4
                    )
                    ax.add_patch(circle)
                    label = f"{len(a.carrying)}G"
                    ax.text(
                        x + 0.5,
                        y + 0.5,
                        label,
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white",
                        fontweight="bold",
                        zorder=5,
                    )

                elif isinstance(a, YellowRobot):
                    circle = plt.Circle(
                        (x + 0.5, y + 0.5), 0.35, color=COLORS[YellowRobot], zorder=4
                    )
                    ax.add_patch(circle)
                    label = f"{len(a.carrying)}Y"
                    ax.text(
                        x + 0.5,
                        y + 0.5,
                        label,
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="#333",
                        fontweight="bold",
                        zorder=5,
                    )

                elif isinstance(a, RedRobot):
                    circle = plt.Circle(
                        (x + 0.5, y + 0.5), 0.35, color=COLORS[RedRobot], zorder=4
                    )
                    ax.add_patch(circle)
                    label = f"{len(a.carrying)}R"
                    ax.text(
                        x + 0.5,
                        y + 0.5,
                        label,
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white",
                        fontweight="bold",
                        zorder=5,
                    )

    # ── Labels des zones ──────────────────────
    ax.text(zw / 2, H + 0.15, "z1 — faible", ha="center", fontsize=9, color="#2d6a2d")
    ax.text(zw * 1.5, H + 0.15, "z2 — moyen", ha="center", fontsize=9, color="#7a5c00")
    ax.text(zw * 2.5, H + 0.15, "z3 — élevé", ha="center", fontsize=9, color="#8b1a1a")

    # ── Légende ───────────────────────────────
    legend_elems = [
        patches.Patch(color=COLORS[GreenRobot], label="Robot vert"),
        patches.Patch(color=COLORS[YellowRobot], label="Robot jaune"),
        patches.Patch(color=COLORS[RedRobot], label="Robot rouge"),
        patches.Patch(color=COLORS[Color.GREEN], label="Déchet vert"),
        patches.Patch(color=COLORS[Color.YELLOW], label="Déchet jaune"),
        patches.Patch(color=COLORS[Color.RED], label="Déchet rouge"),
        patches.Patch(color=COLORS[WasteDisposalZone], alpha=0.5, label="Zone dépôt"),
    ]
    ax.legend(
        handles=legend_elems,
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        fontsize=8,
        framealpha=0.9,
    )

    ax.set_xlim(0, W)
    ax.set_ylim(0, H + 0.4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(
        f"Step {model.steps} — déposés : {model.nb_collected_wastes}",
        fontsize=11,
        pad=6,
    )
    solara.FigureMatplotlib(fig)
