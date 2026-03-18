from abc import ABC, abstractmethod
from typing import Any

from mesa import Agent, Model
from objects import PickUp, PutDown, Radioactivity, Transform, Waste, WasteDisposalZone
from utils import COLOR_TO_ZONE, Action, Color, Move, Zone


class Knowledge:
    """Beliefs and knowledges of a robot."""

    def __init__(self):
        self.round: int = 0
        self.positions: list[tuple[int, int]] = []

        self.last_seen: dict[tuple[int, int], int] = {}
        self.cell_data: dict[tuple[int, int], Any] = {}
        self.carried_wastes: list[list[Waste]] = []
        self.visitable_cells: set[tuple[int, int]] = set()

        # Specific coordinates
        self.min_x_zone: int | None = None
        self.disposal_pos: tuple[int, int] | None = None

        # Other custom data
        self.data: dict[str, Any] = {}


class Robot(Agent, ABC):
    """Abstract class to represent robots"""

    def __init__(self, model: Model, color: Color):
        super().__init__(model)
        self.color = color
        self.carrying: list[Waste] = []
        self.knowledge = Knowledge()

    @property
    def name(self):
        """Name of the robot"""
        return f"Agent {self.color.value} ({self.unique_id})"

    @property
    def zone(self) -> Zone:
        """Zone of the robot"""
        return COLOR_TO_ZONE[self.color]

    @property
    def zone_min_radioactivity(self) -> float:
        """Minimum radioactivity in the main zone of the robot"""
        return (self.zone.value - 1) / 3

    @property
    def max_radioactivity(self) -> float:
        """Maximum radioactivity the robot can support"""
        return self.zone.value / 3

    def __get_cell_data(self, pos: tuple[int, int]) -> dict:
        """Get the data of a given cell"""
        cellmates = self.model.grid.get_cell_list_contents([pos])

        radioactivity_cell = next(
            (a for a in cellmates if isinstance(a, Radioactivity)), None
        )
        if radioactivity_cell is None:
            raise ValueError(f"No radioactivity found in cell {pos} for {self.name}")

        wastes = [a for a in cellmates if isinstance(a, Waste)]

        waste_disposal = next(
            (a for a in cellmates if isinstance(a, WasteDisposalZone)), None
        )

        return {
            "pos": pos,
            "radioactivity": radioactivity_cell.radioactivity,
            "wastes": wastes,
            "waste_disposal": waste_disposal,
            "visitable": radioactivity_cell.radioactivity <= self.max_radioactivity
            and pos != self.pos,
            "is_lower_zone": radioactivity_cell.radioactivity
            <= self.zone_min_radioactivity,
        }

    def perceive(self) -> dict:
        """
        Perception step of the robot that allows to:
        - detect objects
        - analyze presence of other agents
        - ...
        """
        neighborhood = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=True
        )
        data_per_cell = {pos: self.__get_cell_data(pos) for pos in neighborhood}
        return data_per_cell

    def update_knowledge(self, percepts: dict):
        """Update the knowledge of the robot based on its perception."""
        cur_pos = self.pos
        self.knowledge.round += 1
        self.knowledge.positions.append(cur_pos)
        self.knowledge.visitable_cells.clear()

        for pos, data in percepts.items():
            self.knowledge.last_seen[pos] = self.knowledge.round
            self.knowledge.cell_data[pos] = data
            self.knowledge.carried_wastes.append(self.carrying)

            # Mise à jour de la zone de dépôt si elle est visitable
            if data["visitable"]:
                self.knowledge.visitable_cells.add(pos)

            # Mise à jour de la position de la zone de dépôt si elle est détectée
            if (
                data["waste_disposal"] is not None
                and self.knowledge.disposal_pos is None
            ):
                self.knowledge.disposal_pos = pos

            # Recherche de la frontière avec la zone inférieure
            if not percepts[cur_pos]["is_lower_zone"] and data["is_lower_zone"]:
                self.knowledge.min_x_zone = cur_pos[0]

    @abstractmethod
    def deliberate(self, knowledge: Knowledge) -> Action:
        """
        Deliberation step of the robot.
        It returns one or several actions to execute.
        """

    def step_agent(self):
        """
        Execute one step of the agent
        """
        percepts = self.perceive()
        self.update_knowledge(percepts)
        action = self.deliberate(self.knowledge)
        self.model.do(self, action)

    def _move_randomly(self, knowledge: Knowledge, axis: int | None = None) -> Move:
        """Helper method to move randomly in the visitable neighborhood."""
        pos = knowledge.positions[-1]
        available_directions = [
            (x - pos[0], y - pos[1]) for x, y in knowledge.visitable_cells
        ]

        # Filtrer les directions pour ne pas changer d'axe si un axe est spécifié
        if axis == 0:
            available_directions = [d for d in available_directions if d[1] == 0]
        elif axis == 1:
            available_directions = [d for d in available_directions if d[0] == 0]

        next_direction = self.model.random.choice(available_directions)
        return Move(next_direction)

    def _move_towards(
        self, target_pos: tuple[int | None, int | None], knowledge: Knowledge
    ) -> Move:
        """Helper method to move towards a target position."""
        pos = knowledge.positions[-1]
        tx, ty = target_pos
        dx, dy = 0, 0
        if tx is not None:
            dx = tx - pos[0]
        if ty is not None:
            dy = ty - pos[1]

        direction = (0, 0)
        if abs(dx) > abs(dy):
            direction = (1 if dx > 0 else -1, 0)
        elif dy != 0:
            direction = (0, 1 if dy > 0 else -1)

        next_pos = (pos[0] + direction[0], pos[1] + direction[1])
        if next_pos in knowledge.visitable_cells:
            return Move(direction)

        # Si la cellule ciblée n'est pas visitable, on se déplace aléatoirement
        return self._move_randomly(knowledge)


class GreenRobot(Robot):
    """Green robot in zone 1."""

    def __init__(self, model: Model):
        super().__init__(model, Color.GREEN)

    def deliberate(self, knowledge: Knowledge) -> Action:
        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        current_cell_data = knowledge.cell_data[pos]

        # 1. Transformer 2 verts → 1 jaune
        if len(carried_wastes) == 2 and all(
            w.waste_type == Color.GREEN for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # 2. Déposer le jaune à la frontière z1/z2
        if len(carried_wastes) == 1 and carried_wastes[0].waste_type == Color.YELLOW:
            if (pos[0] + 1, pos[1]) not in knowledge.visitable_cells:
                return PutDown(carried_wastes[0])
            return Move((1, 0))

        # 3. Ramasser un déchet vert sur la cellule
        green_wastes = [
            w for w in current_cell_data["wastes"] if w.waste_type == Color.GREEN
        ]
        if green_wastes and len(carried_wastes) < 2:
            return PickUp(green_wastes[0])

        # 4. Se déplacer aléatoirement dans z1
        return self._move_randomly(knowledge)


class YellowRobot(Robot):
    """Yellow robot in zone 2."""

    def __init__(self, model: Model):
        super().__init__(model, Color.YELLOW)

    def deliberate(self, knowledge: Knowledge) -> Action:
        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        current_cell_data = knowledge.cell_data[pos]

        # 1. Transformer 2 jaunes → 1 rouge
        if len(carried_wastes) == 2 and all(
            w.waste_type == Color.YELLOW for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # 2. Déposer le rouge à la frontière z2/z3
        if len(carried_wastes) == 1 and carried_wastes[0].waste_type == Color.RED:
            if (pos[0] + 1, pos[1]) not in knowledge.visitable_cells:
                return PutDown(carried_wastes[0])
            return Move((1, 0))

        # 3. Ramasser un déchet jaune
        yellow_wastes = [
            w for w in current_cell_data["wastes"] if w.waste_type == Color.YELLOW
        ]
        if yellow_wastes and len(carried_wastes) < 2:
            return PickUp(yellow_wastes[0])

        # 4. Inspecter la frontière pour être prêt à récupérer les déchets jaunes déposés par les verts
        if knowledge.min_x_zone is None:
            # On explore à l'ouest
            return self._move_towards((0, None), knowledge)
        if pos[0] != knowledge.min_x_zone - 1:
            # On se place à l'ouest de la frontière
            return self._move_towards((knowledge.min_x_zone - 1, None), knowledge)

        # 4. Se déplacer aléatoirement à la frontière
        return self._move_randomly(knowledge, axis=1)


class RedRobot(Robot):
    """Red robot in zone 3."""

    def __init__(self, model: Model):
        super().__init__(model, Color.RED)

    def update_knowledge(self, percepts):
        super().update_knowledge(percepts)
        # Gestion de la stratégie de recherche de la zone de dépôt
        if self.knowledge.disposal_pos is None:
            if self.knowledge.data.get("disposal_search_direction") is None:
                self.knowledge.data["disposal_search_direction"] = (0, 1)
            elif (self.pos[0], self.pos[1] + 1) not in self.knowledge.visitable_cells:
                self.knowledge.data["disposal_search_direction"] = (0, -1)
        elif self.knowledge.data.get("disposal_search_direction") is not None:
            self.knowledge.data["disposal_search_direction"] = None

    def deliberate(self, knowledge: Knowledge) -> Action:
        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        current_cell_data = knowledge.cell_data[pos]
        disposal_pos = knowledge.disposal_pos

        # 1. Déposer si on est sur la zone de dépôt
        if carried_wastes and pos == disposal_pos:
            return PutDown(carried_wastes[0])

        # 2. Si on porte un rouge, naviguer vers la zone de dépôt
        if carried_wastes:
            # Si on ne connaît pas encore la position de la zone de dépôt, explorer vers l'est
            if disposal_pos is None:
                # Aller vers l'est pour trouver la zone de dépôt
                if (pos[0] + 1, pos[1]) in knowledge.visitable_cells:
                    return Move((1, 0))
                # Sinon, se déplacer aléatoirement pour explorer
                return self._move_randomly(knowledge)

            # Si on connaît la position de la zone de dépôt, se diriger vers celle-ci
            return self._move_towards(knowledge.disposal_pos, knowledge)

        # 3. Ramasser un déchet rouge
        red_wastes = [
            w
            for w in current_cell_data["wastes"]
            if w.waste_type == Color.RED and pos != disposal_pos
        ]
        if red_wastes:
            return PickUp(red_wastes[0])

        # 4. Chercher la zone de dépôt si pas encore trouvée
        if disposal_pos is None:
            # Aller vers l'est pour trouver la zone de dépôt
            if (pos[0] + 1, pos[1]) in knowledge.visitable_cells:
                return Move((1, 0))
            # Sinon, on suit la stratégie d'exploration
            return Move(knowledge.data["disposal_search_direction"])

        # 5. Inspecter la frontière pour être prêt à récupérer les déchets rouges déposés par les jaunes
        if knowledge.min_x_zone is None:
            # On explore à l'ouest
            return self._move_towards((0, None), knowledge)
        if pos[0] != knowledge.min_x_zone - 1:
            # On se place à l'ouest de la frontière
            return self._move_towards((knowledge.min_x_zone - 1, None), knowledge)

        # 4. Se déplacer aléatoirement à la frontière
        return self._move_randomly(knowledge, axis=1)
