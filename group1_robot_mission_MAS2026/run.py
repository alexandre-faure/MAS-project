"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from mesa.visualization import SolaraViz
from model import RobotMissionModel
from server import SpaceGraph, WastesCollectionTracker


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
        "green_robot_is_random": {
            "type": "Checkbox",
            "value": False,
            "label": "Les robots verts explorent-ils aléatoirement ?",
        },
        "green_robot_has_memory": {
            "type": "Checkbox",
            "value": True,
            "label": "Les robots verts apprennent de leur environnement ?",
        },
        "yellow_robot_is_random": {
            "type": "Checkbox",
            "value": False,
            "label": "Les robots jaunes explorent-ils aléatoirement ?",
        },
        "yellow_robot_has_memory": {
            "type": "Checkbox",
            "value": True,
            "label": "Les robots jaunes apprennent de leur environnement ?",
        },
        "red_robot_is_random": {
            "type": "Checkbox",
            "value": False,
            "label": "Les robots rouges explorent-ils aléatoirement ?",
        },
        "red_robot_has_memory": {
            "type": "Checkbox",
            "value": True,
            "label": "Les robots rouges apprennent de leur environnement ?",
        },
    }

    page = SolaraViz(
        robot_mission_model,
        components=[SpaceGraph, WastesCollectionTracker],
        model_params=model_params,
        name="Robot Mission Model",
    )
    return page


if __name__ == "__main__":
    page = run_server()
