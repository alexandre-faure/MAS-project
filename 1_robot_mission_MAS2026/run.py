from mesa.visualization import SolaraViz, make_space_component
from model import RobotMissionModel
from server import agent_portrayal, post_process


def run_server():
    robot_mission_model = RobotMissionModel()

    model_params = {
        "width": {
            "type": "SliderInt",
            "value": 18,
            "label": "Largeur de la zone:",
            "min": 6,
            "max": 100,
            "step": 3,
        },
        "height": {
            "type": "SliderInt",
            "value": 8,
            "label": "Hauteur de la zone:",
            "min": 3,
            "max": 100,
            "step": 1,
        },
        "n_green_robots": {
            "type": "SliderInt",
            "value": 3,
            "label": "Nombre de robots vers:",
            "min": 1,
            "max": 10,
            "step": 1,
        },
        "n_yellow_robots": {
            "type": "SliderInt",
            "value": 2,
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
            "value": 8,
            "label": "Nombre de déchets verts initiaux:",
            "min": 4,
            "max": 64,
            "step": 4,
        },
    }

    SpaceGraph = make_space_component(agent_portrayal, post_process=post_process)

    page = SolaraViz(
        robot_mission_model,
        components=[SpaceGraph],
        model_params=model_params,
        name="Robot Mission Model",
    )
    return page


if __name__ == "__main__":
    page = run_server()
