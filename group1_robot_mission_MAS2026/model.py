# Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026
from itertools import product

import solara
from agents import GreenRobot, RedRobot, Robot, YellowRobot
from mesa import Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid
from objects import PickUp, PutDown, Radioactivity, Transform, Waste, WasteDisposalZone
from utils import Action, Color, Move, Wait, Zone
from communication.agent.CommunicatingAgent import CommunicatingAgent
from communication.message.MessageService import MessageService
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
        self.message_service = MessageService(self)
        self._place_robots(n_green_robots, n_yellow_robots, n_red_robots)
        

        # Collecte de données
        self.datacollector = DataCollector(
            model_reporters={
                "Déchets verts": lambda m: m.nb_wastes_by_color(Color.GREEN),
                "Déchets jaunes": lambda m: m.nb_wastes_by_color(Color.YELLOW),
                "Déchets rouges": lambda m: m.nb_wastes_by_color(Color.RED),
                "Déposés": lambda m: m.nb_collected_wastes,
            }
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

    def _place_robots(self, n_green: int, n_yellow: int, n_red: int):
        """Place les robots dans leurs zones respectives."""
        possible_positions = {
            GreenRobot: product(range(self.zone_width), range(self.height)),
            YellowRobot: product(
                range(self.zone_width, 2 * self.zone_width), #toutes les zones sont de même largeur
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
            self.grid.place_agent(GreenRobot(self), (x, y))

        yellow_positions = self.random.sample(
            list(possible_positions[YellowRobot]), n_yellow
        )
        for x, y in yellow_positions:
            self.grid.place_agent(YellowRobot(self), (x, y))

        red_positions = self.random.sample(list(possible_positions[RedRobot]), n_red)
        for x, y in red_positions:
            self.grid.place_agent(RedRobot(self), (x, y))

    # ── DO — arbitre des actions ──────────────
    def do(self, agent: Robot, action: Action) -> dict:
        """
        Exécute l'action demandée par l'agent après vérification.
        """
        if isinstance(action, Wait):
            return

        elif isinstance(action, Move):
            dx, dy = action.direction
            x, y = agent.pos
            nx, ny = x + dx, y + dy
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
            wastes = action.wastes
            if any(w.waste_type != agent.color for w in wastes) or len(wastes) != 2:
                raise ValueError(
                    f"Invalid transform action by {agent.name}: must transform 2 wastes of its color"
                )

            new_waste = None
            if agent.color == Color.GREEN:
                new_waste = Waste(self, Color.YELLOW)
            elif agent.color == Color.YELLOW:
                new_waste = Waste(self, Color.RED)
            else: #agent red
                raise ValueError(f"Robot {agent.name} cannot transform wastes")

            # Supprime les déchets transformés
            for w in wastes:
                w.remove()
            agent.carrying.clear()

            # On donne à l'agent le nouveau déchet transformé
            assert (
                len(agent.carrying) == 0
            ), f"All wastes should have been removed after transform for {agent.name}"
            agent.carrying.append(new_waste)

        elif isinstance(action, PutDown):
            for waste in agent.carrying:
                self.grid.place_agent(waste, agent.pos)
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
            if isinstance(a, Waste)
            and a.waste_type == waste_type
            and (waste_type != Color.RED or a.pos != self.waste_disposal_pos) 
            # les déchets rouges déposés sont comptés dans nb_collected_wastes, pas ici
        )

    @property
    def nb_wastes(self) -> int:
        """Nombre total de déchets totaux sur la grille (hors déchets portés par les robots)."""
        agents = self.agents
        return sum(1 for a in agents if isinstance(a, Waste) and a.pos is not None)

    @property
    def nb_collected_wastes(self) -> int:
        """Nombre de déchets déposés dans la zone de dépôt."""
        agents = self.agents
        return sum(
            1
            for a in agents
            if isinstance(a, Waste) and a.pos == self.waste_disposal_pos
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
