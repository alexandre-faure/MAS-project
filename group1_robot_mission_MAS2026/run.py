# Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026
from mesa.visualization import SolaraViz
from model import RobotMissionModel
from server import SpaceGraph, WastesTracker


def run_server():
    robot_mission_model = RobotMissionModel()

    model_params = {
        "width": {
            "type": "SliderInt",
            "value": 18,
            "label": "Largeur de la zone:",
            "min": 6,
            "max": 42,
            "step": 3,
        },
        "height": {
            "type": "SliderInt",
            "value": 14,
            "label": "Hauteur de la zone:",
            "min": 3,
            "max": 42,
            "step": 1,
        },
        "n_green_robots": {
            "type": "SliderInt",
            "value": 4,
            "label": "Nombre de robots verts:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_yellow_robots": {
            "type": "SliderInt",
            "value": 3,
            "label": "Nombre de robots jaunes:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_red_robots": {
            "type": "SliderInt",
            "value": 2,
            "label": "Nombre de robots rouges:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_green_wastes": {
            "type": "SliderInt",
            "value": 20,
            "label": "Nombre de déchets verts initiaux:",
            "min": 4,
            "max": 64,
            "step": 4,
        },
    }

    page = SolaraViz(
        robot_mission_model,
        components=[SpaceGraph, WastesTracker],
        model_params=model_params,
        name="Robot Mission Model",
    )
    return page


if __name__ == "__main__":
    page = run_server()
