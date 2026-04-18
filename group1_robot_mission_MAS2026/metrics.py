"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 23/03/2026"""

from agents import GreenRobot, RedRobot, Robot, YellowRobot
from mesa import Model
from utils import COLORS, Color


def ratio_collected(model: Model) -> float:
    """Calculates the ratio of collected wastes to total wastes."""
    total_wastes = (
        model.n_green_wastes * 1.75 + model.n_yellow_wastes * 1.5 + model.n_red_wastes
    )

    # Number of wastes in circulation by color
    nb_wastes_in_circulation = {col: model.nb_wastes_by_color(col) for col in COLORS}

    nb_uncollected_wastes = (
        nb_wastes_in_circulation[Color.GREEN] * 1.75
        + nb_wastes_in_circulation[Color.YELLOW] * 1.5
        + nb_wastes_in_circulation[Color.RED]
    )

    return 1 - nb_uncollected_wastes / total_wastes


def scenario_duration(model: Model) -> int:
    """Returns the duration of the scenario in time steps."""
    return model.steps


def waste_lifespan(model: Model) -> dict[Color, float]:
    """Calculates the average lifespan of wastes of a given type."""
    lifespan_by_col = {}
    for color in COLORS:
        collected_wastes = model.get_wastes_by_color(color, processed=True)
        lifespans = [w.lifespan for w in collected_wastes]
        lifespan_by_col[color] = sum(lifespans) / (len(lifespans) + 1e-5)
    return lifespan_by_col


def exploration_ratio(model: Model) -> dict[Color, float]:
    """Calculates the exploration ratio for each type of waste."""
    exploration_ratio_by_col = {col: 0 for col in COLORS}
    step = model.steps

    for color, robot_type in zip(COLORS, [GreenRobot, YellowRobot, RedRobot]):
        robots: list[Robot] = model.agents_by_type[robot_type]
        for robot in robots:
            exploration_ratio_by_col[color] += robot.nb_exploring_steps / (step + 1e-5)
        exploration_ratio_by_col[color] /= len(robots) if len(robots) > 0 else 1

    return exploration_ratio_by_col


def load_balancing(model: Model):
    """Calculates the load balancing metric for each type of waste."""
    load_balancing_by_col = {col: 0 for col in COLORS}

    for color, robot_type in zip(COLORS, [GreenRobot, YellowRobot, RedRobot]):
        robots: list[Robot] = model.agents_by_type[robot_type]
        nb_collected = [robot.nb_wastes_collected for robot in robots]
        max_col = max(nb_collected) if nb_collected else 1
        mean_col = sum(nb_collected) / len(nb_collected) if nb_collected else 0
        load_balancing_by_col[color] = max_col / (mean_col + 1e-5)

    return load_balancing_by_col