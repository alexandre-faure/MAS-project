"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from enum import Enum
from itertools import product

import solara
from agents import GreenRobot, RedRobot, Robot, YellowRobot
from communication.message.MessageService import MessageService
from communication.message.MessageService import MessageService
from mesa import Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid
from metrics import exploration_ratio, load_balancing, ratio_collected, waste_lifespan
from objects import Radioactivity, Waste, WasteDisposalZone
from utils import (
    COLORS,
    Action,
    Color,
    Move,
    PickUp,
    PutDown,
    RobotBehavior,
    Transform,
    Wait,
    Zone,
)

update_counter = solara.reactive(0)


DEFAULT_PARAMS = dict(
    width=18,
    height=14,
    n_green_robots=4,
    n_yellow_robots=3,
    n_red_robots=2,
    n_green_wastes=20,
    n_yellow_wastes=10,
    n_red_wastes=5,
    max_step=200,
    seed=None,
    robots_behavior="Communication",
)


class RobotMissionModel(Model):
    """
    Modèle principal.
    - Crée la grille, les zones radioactives, les déchets et les robots.
    - Arbitre toutes les actions via do().
    """

    def __init__(
        self,
        width: int = DEFAULT_PARAMS["width"],
        height: int = DEFAULT_PARAMS["height"],
        n_green_robots: int = DEFAULT_PARAMS["n_green_robots"],
        n_yellow_robots: int = DEFAULT_PARAMS["n_yellow_robots"],
        n_red_robots: int = DEFAULT_PARAMS["n_red_robots"],
        n_green_wastes: int = DEFAULT_PARAMS["n_green_wastes"],
        n_yellow_wastes: int = DEFAULT_PARAMS["n_yellow_wastes"],
        n_red_wastes: int = DEFAULT_PARAMS["n_red_wastes"],
        seed: int | str | None = DEFAULT_PARAMS["seed"],
        max_step: int = DEFAULT_PARAMS["max_step"],
        robots_behavior: str = DEFAULT_PARAMS["robots_behavior"],
    ):
        if isinstance(seed, str) and not seed.isdigit():
            seed = None
        super().__init__(seed=seed)

        assert width % 3 == 0, "Width must be divisible by 3 for equal zones"
        self.width = width
        self.height = height
        self.zone_width = width // 3
        self.grid = MultiGrid(width, height, torus=False)
        self.running = True
        self.max_step = max_step

        # Construction du monde
        assert (
            max(n_green_wastes, n_yellow_wastes, n_red_wastes)
            <= self.zone_width * self.height
        ), f"Too many wastes for the zone size, don't exceed {self.zone_width * self.height} wastes for each color"

        self._place_radioactivity()
        self.waste_disposal_pos = self._place_waste_disposal()
        self.n_green_wastes = n_green_wastes
        self.n_yellow_wastes = n_yellow_wastes
        self.n_red_wastes = n_red_wastes
        self._place_initial_wastes(n_green_wastes, n_yellow_wastes, n_red_wastes)
        MessageService.reset()
        self.message_service = MessageService(self)
        robots_behavior = RobotBehavior.from_string(robots_behavior)
        self._place_robots(
            n_green_robots, n_yellow_robots, n_red_robots, robots_behavior
        )

        # Collecte de données
        self.datacollector = DataCollector(
            model_reporters={
                "Déchets verts": lambda m: m.nb_wastes_by_color(Color.GREEN),
                "Déchets jaunes": lambda m: m.nb_wastes_by_color(Color.YELLOW),
                "Déchets rouges": lambda m: m.nb_wastes_by_color(Color.RED),
                "Déposés": lambda m: m.nb_collected_wastes,
                "Ratio collecté": ratio_collected,
                "Durée de vie des déchets": waste_lifespan,
                "Ratio d'exploration": exploration_ratio,
                "Load balancing": load_balancing,
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

    def _place_initial_wastes(self, n_green: int, n_yellow: int, n_red: int):
        """Déchets verts initiaux uniquement dans z1."""
        possible_positions = list(product(range(self.zone_width), range(self.height)))
        for i, n in enumerate([n_green, n_yellow, n_red]):
            waste_positions = self.random.sample(possible_positions, n)
            for x, y in waste_positions:
                self.grid.place_agent(
                    Waste(self, COLORS[i]), (x + i * self.zone_width, y)
                )

    def _place_robots(
        self, n_green: int, n_yellow: int, n_red: int, robots_behavior: RobotBehavior
    ):
        """Place les robots dans leurs zones respectives."""
        possible_positions = {
            GreenRobot: product(range(self.zone_width), range(self.height)),
            YellowRobot: product(
                range(
                    self.zone_width, 2 * self.zone_width
                ),  # toutes les zones sont de même largeur
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
            self.grid.place_agent(GreenRobot(self, robots_behavior), (x, y))

        yellow_positions = self.random.sample(
            list(possible_positions[YellowRobot]), n_yellow
        )
        for x, y in yellow_positions:
            self.grid.place_agent(
                YellowRobot(self, robots_behavior),
                (x, y),
            )

        red_positions = self.random.sample(list(possible_positions[RedRobot]), n_red)
        for x, y in red_positions:
            self.grid.place_agent(RedRobot(self, robots_behavior), (x, y))

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
                new_waste = Waste(self, Color.YELLOW, cur_step)
            elif agent.color == Color.YELLOW:
                new_waste = Waste(self, Color.RED, cur_step)
            else:
                new_waste = Waste(self, Color.RED, cur_step)
            else:
                raise ValueError(f"Robot {agent.name} cannot transform wastes")

            # Supprime les déchets transformés
            for w in wastes:
                w.set_processed(cur_step)
                w.set_processed(cur_step)
            agent.carrying.clear()

            # On donne à l'agent le nouveau déchet transformé
            assert (
                len(agent.carrying) == 0
            ), f"All wastes should have been removed after transform for {agent.name}"
            agent.carrying.append(new_waste)

        elif isinstance(action, PutDown):
            is_processed = agent.pos == self.waste_disposal_pos
            is_processed = agent.pos == self.waste_disposal_pos
            for waste in agent.carrying:
                self.grid.place_agent(waste, agent.pos)
                if is_processed:
                    waste.set_processed(self.steps)
                if is_processed:
                    waste.set_processed(self.steps)
            agent.carrying.clear()

        else:
            raise ValueError(
                f"Unknown action type: {action.action_type} for agent {agent}"
            )

        return

    def nb_wastes_by_color(self, waste_type: Color) -> int:
        """
        Nombre de déchets d'une couleur donnée encore en circulation (sur la grille ou portés par les robots, mais pas encore déposés).
        """
        return len(self.get_wastes_by_color(waste_type, processed=False))

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
        """Nombre de déchets rouges déposés dans la zone de dépôt."""
        return len(self.get_wastes_by_color(Color.RED, processed=True))

    def get_wastes_by_color(
        self, waste_type: Color, processed: bool = False
    ) -> list[Waste]:
        """Retourne la liste des déchets d'une couleur donnée, en circulation ou traités selon le paramètre processed."""
        agents = self.agents
        return [
            a
            for a in agents
            if isinstance(a, Waste)
            and a.waste_type == waste_type
            and (processed ^ (not a.processed))
        ]

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

        # Incrémenter le compteur de mise à jour pour rafraîchir la visualisation
        update_counter.value += 1

        # Arrêter quand tout est collecté
        if self.nb_wastes == 0 and all(len(r.carrying) == 0 for r in robots):
            self.running = False

        # Arrêter si on atteint le nombre maximum de pas de temps
        if self.steps >= self.max_step:
            self.running = False
