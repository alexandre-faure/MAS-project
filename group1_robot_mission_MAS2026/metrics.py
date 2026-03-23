"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 23/03/2026"""

from mesa import Model
from utils import COLORS, Color


def ratio_collected(model: Model) -> float:
    """Calculates the ratio of collected wastes to total wastes."""
    init_green_wastes = model.n_green_wastes
    total_wastes = init_green_wastes * (
        1 + 1 / 2 + 1 / 4
    )  # Total wastes including transformed ones

    # Number of wastes in circulation by color
    nb_wastes_in_circulation = {col: model.nb_wastes_by_color(col) for col in COLORS}

    nb_uncollected_wastes = (
        nb_wastes_in_circulation[Color.GREEN] * (1 + 1 / 2 + 1 / 4)
        + nb_wastes_in_circulation[Color.YELLOW] * (1 + 1 / 2)
        + nb_wastes_in_circulation[Color.RED]
    )

    return 1 - nb_uncollected_wastes / total_wastes if total_wastes > 0 else 0.0
