"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from mesa.visualization import SolaraViz
from model import DEFAULT_PARAMS, RobotMissionModel
from server import RatioToCollectTracker, SpaceGraph, WastesCollectionTracker


def run_server():
    robot_mission_model = RobotMissionModel()

    model_params = {
        "width": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["width"],
            "label": "Largeur de la zone:",
            "min": 6,
            "max": 42,
            "step": 3,
        },
        "height": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["height"],
            "label": "Hauteur de la zone:",
            "min": 3,
            "max": 42,
            "step": 1,
        },
        "n_green_robots": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["n_green_robots"],
            "label": "Nb robots verts:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_yellow_robots": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["n_yellow_robots"],
            "label": "Nb robots jaunes:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_red_robots": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["n_red_robots"],
            "label": "Nb robots rouges:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_green_wastes": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["n_green_wastes"],
            "label": "Nb déchets verts:",
            "min": 4,
            "max": 64,
            "step": 4,
        },
        "n_yellow_wastes": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["n_yellow_wastes"],
            "label": "Nb déchets jaunes:",
            "min": 0,
            "max": 64,
            "step": 2,
        },
        "n_red_wastes": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["n_red_wastes"],
            "label": "Nb déchets rouges:",
            "min": 0,
            "max": 64,
            "step": 1,
        },
        "max_step": {
            "type": "SliderInt",
            "value": DEFAULT_PARAMS["max_step"],
            "label": "Nb steps max:",
            "min": 50,
            "max": 500,
            "step": 50,
        },
        "seed": {
            "type": "InputText",
            "value": DEFAULT_PARAMS["seed"],
            "label": "Seed (optionnel):",
            "on_value": lambda value: int(value) if value.isdigit() else None,
        },
        "robots_behavior": {
            "type": "Select",
            "value": DEFAULT_PARAMS["robots_behavior"],
            "label": "Comportement des robots:",
            "values": ["Aléatoire", "Mémoire", "Communication"],
        },
    }

    return SolaraViz(
        robot_mission_model,
        components=[
            SpaceGraph,
            WastesCollectionTracker,
            RatioToCollectTracker,
        ],
        model_params=model_params,
        name="Robot Mission Model",
    )


if __name__ == "__main__":
    page = run_server()
