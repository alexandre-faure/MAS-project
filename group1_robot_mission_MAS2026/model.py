"""
models.py

Authors:
- Alexandre Faure
- Sarah Lamik
- Ylias Larbi
"""

from itertools import product

import solara
from agents import GreenRobot, RedRobot, Robot, YellowRobot
from mesa import Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid
from objects import PickUp, PutDown, Radioactivity, Transform, Waste, WasteDisposalZone
from utils import Action, Color, Move, Wait, Zone

update_counter = solara.reactive(0)


class RobotMissionModel(Model):
    """
    Modèle principal.
    - Crée la grille, les zones radioactives, les déchets et les robots.
    - Arbitre toutes les actions via do().
    """

    def __init__(
        self,
        width: int = 18,
        height: int = 14,
        n_green_robots: int = 4,
        n_yellow_robots: int = 3,
        n_red_robots: int = 2,
        n_green_wastes: int = 20,
        seed: int = None,
        green_robot_is_random: bool = False,
        green_robot_has_memory: bool = True,
        yellow_robot_is_random: bool = False,
        yellow_robot_has_memory: bool = True,
        red_robot_is_random: bool = False,
        red_robot_has_memory: bool = True,
    ):
        super().__init__(seed=seed)

        assert width % 3 == 0, "Width must be divisible by 3 for equal zones"
        self.width = width
        self.height = height
        self.zone_width = width // 3
        self.grid = MultiGrid(width, height, torus=False)
        self.running = True

        # Construction du monde
        assert (
            n_green_wastes <= self.zone_width * self.height
        ), "Too many wastes for zone 1"

        self._place_radioactivity()
        self.waste_disposal_pos = self._place_waste_disposal()
        self._place_initial_wastes(n_green_wastes)
        self._place_robots(
            n_green_robots,
            n_yellow_robots,
            n_red_robots,
            green_robot_is_random,
            green_robot_has_memory,
            yellow_robot_is_random,
            yellow_robot_has_memory,
            red_robot_is_random,
            red_robot_has_memory,
        )

        # Collecte de données
        self.datacollector = DataCollector(
            model_reporters={
                "Déchets verts": lambda m: m.nb_wastes_by_color(Color.GREEN),
                "Déchets jaunes": lambda m: m.nb_wastes_by_color(Color.YELLOW),
                "Déchets rouges": lambda m: m.nb_wastes_by_color(Color.RED),
                "Déposés": lambda m: m.nb_collected_wastes,
            },
        )

    def _place_radioactivity(self):
        """Une instance Radioactivity par cellule."""
        for _, (x, y) in self.grid.coord_iter():
            zone = Zone(x // self.zone_width + 1)
            self.grid.place_agent(Radioactivity(self, zone), (x, y))

    def _place_waste_disposal(self) -> tuple[int, int]:
        """Zone de dépôt : colonne la plus à l'est, hauteur aléatoire."""
        y = self.random.randint(0, self.height - 1)
        disposal_pos = (self.width - 1, y)
        self.grid.place_agent(WasteDisposalZone(self), disposal_pos)
        return disposal_pos

    def _place_initial_wastes(self, n: int):
        """Déchets verts initiaux uniquement dans z1."""
        possible_positions = product(range(self.zone_width), range(self.height))
        waste_positions = self.random.sample(list(possible_positions), n)
        for x, y in waste_positions:
            self.grid.place_agent(Waste(self, Color.GREEN), (x, y))

    def _place_robots(
        self,
        n_green: int,
        n_yellow: int,
        n_red: int,
        green_robot_is_random: bool,
        green_robot_has_memory: bool,
        yellow_robot_is_random: bool,
        yellow_robot_has_memory: bool,
        red_robot_is_random: bool,
        red_robot_has_memory: bool,
    ):
        """Place les robots dans leurs zones respectives."""
        possible_positions = {
            GreenRobot: product(range(self.zone_width), range(self.height)),
            YellowRobot: product(
                range(self.zone_width, 2 * self.zone_width),
                range(self.height),
            ),
            RedRobot: product(
                range(2 * self.zone_width, self.width), range(self.height)
            ),
        }

        green_positions = self.random.sample(
            list(possible_positions[GreenRobot]), n_green
        )
        for x, y in green_positions:
            self.grid.place_agent(
                GreenRobot(self, green_robot_is_random, green_robot_has_memory), (x, y)
            )

        yellow_positions = self.random.sample(
            list(possible_positions[YellowRobot]), n_yellow
        )
        for x, y in yellow_positions:
            self.grid.place_agent(
                YellowRobot(self, yellow_robot_is_random, yellow_robot_has_memory),
                (x, y),
            )

        red_positions = self.random.sample(list(possible_positions[RedRobot]), n_red)
        for x, y in red_positions:
            self.grid.place_agent(
                RedRobot(self, red_robot_is_random, red_robot_has_memory), (x, y)
            )

    # ── DO — arbitre des actions ──────────────
    def do(self, agent: Robot, action: Action) -> dict:
        """
        Exécute l'action demandée par l'agent après vérification.
        """
        if isinstance(action, Wait):
            return

        elif isinstance(action, Move):
            nx, ny = -1, -1
            if action.direction is not None:
                dx, dy = action.direction
                nx, ny = agent.pos[0] + dx, agent.pos[1] + dy
            elif action.position is not None:
                nx, ny = action.position
            else:
                raise ValueError(
                    f"Invalid move action by {agent.name}: no direction or position provided"
                )
            # Vérification : pas d'autre robot
            if any(
                isinstance(a, Robot)
                for a in self.grid.get_cell_list_contents([(nx, ny)])
            ):
                raise ValueError(
                    f"Invalid move by {agent.name}: cell occupied by another robot"
                )
            self.grid.move_agent(agent, (nx, ny))

        elif isinstance(action, PickUp):
            waste = action.waste
            # Vérification : le déchet est bien là
            cell_contents = self.grid.get_cell_list_contents([agent.pos])
            if waste in cell_contents:
                self.grid.remove_agent(waste)
                agent.carrying.append(waste)

        elif isinstance(action, Transform):
            cur_step = self.steps
            wastes = action.wastes
            if any(w.waste_type != agent.color for w in wastes) or len(wastes) != 2:
                raise ValueError(
                    f"Invalid transform action by {agent.name}: must transform 2 wastes of its color"
                )

            new_waste = None
            if agent.color == Color.GREEN:
                new_waste = Waste(self, Color.YELLOW, cur_step)
            elif agent.color == Color.YELLOW:
                new_waste = Waste(self, Color.RED, cur_step)
            else:
                raise ValueError(f"Robot {agent.name} cannot transform wastes")

            # Supprime les déchets transformés
            for w in wastes:
                w.set_processed(cur_step)
            agent.carrying.clear()

            # On donne à l'agent le nouveau déchet transformé
            assert (
                len(agent.carrying) == 0
            ), f"All wastes should have been removed after transform for {agent.name}"
            agent.carrying.append(new_waste)

        elif isinstance(action, PutDown):
            is_processed = agent.pos == self.waste_disposal_pos
            for waste in agent.carrying:
                self.grid.place_agent(waste, agent.pos)
                if is_processed:
                    waste.set_processed(self.steps)
            agent.carrying.clear()

        else:
            raise ValueError(
                f"Unknown action type: {action.action_type} for agent {agent}"
            )

        return

    def nb_wastes_by_color(self, waste_type: Color) -> int:
        """Nombre de déchets d'une couleur donnée sur la grille et portés par les robots."""
        agents = self.agents
        return sum(
            1
            for a in agents
            if isinstance(a, Waste) and a.waste_type == waste_type and not a.processed
        )

    @property
    def nb_wastes(self) -> int:
        """Nombre total de déchets totaux sur la grille (hors déchets portés par les robots)."""
        agents = self.agents
        return sum(
            1
            for a in agents
            if isinstance(a, Waste) and a.pos is not None and not a.processed
        )

    @property
    def nb_collected_wastes(self) -> int:
        """Nombre de déchets déposés dans la zone de dépôt."""
        agents = self.agents
        return sum(
            1
            for a in agents
            if isinstance(a, Waste)
            and a.pos == self.waste_disposal_pos
            and not a.processed
        )

    def step(self):
        """
        Une étape de simulation : collecte de données, activation des robots, vérification de fin.
        """
        self.datacollector.collect(self)
        # Activer les robots dans un ordre aléatoire
        robots: list[Robot] = (
            list(self.agents_by_type[GreenRobot])
            + list(self.agents_by_type[YellowRobot])
            + list(self.agents_by_type[RedRobot])
        )
        self.random.shuffle(robots)
        for robot in robots:
            robot.step_agent()

        # Arrêter quand tout est collecté
        if self.nb_wastes == self.nb_collected_wastes and all(
            len(r.carrying) == 0 for r in robots
        ):
            self.running = False

        # Incrémenter le compteur de mise à jour pour rafraîchir la visualisation
        update_counter.value += 1
