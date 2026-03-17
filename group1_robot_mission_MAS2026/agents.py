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
        self.last_visited: dict[tuple[int, int], int] = {}
        self.cell_data: dict[tuple[int, int], Any] = {}
        self.carried_wastes: list[list[Waste]] = []
        self.visitable_cells: set[tuple[int, int]] = set()
        self.disposal_pos: tuple[int, int] | None = None


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
        print(f"{self.name} perceives neighborhood: {neighborhood}")
        data_per_cell = {pos: self.__get_cell_data(pos) for pos in neighborhood}
        return data_per_cell

    def update_knowledge(self, percepts: dict):
        """Update the knowledge of the robot based on its perception."""
        self.knowledge.round += 1
        self.knowledge.positions.append(self.pos)
        self.knowledge.visitable_cells.clear()

        for pos, data in percepts.items():
            self.knowledge.last_visited[pos] = self.knowledge.round
            self.knowledge.cell_data[pos] = data
            self.knowledge.carried_wastes.append(self.carrying)

            if data["visitable"]:
                self.knowledge.visitable_cells.add(pos)

            if (
                data["waste_disposal"] is not None
                and self.knowledge.disposal_pos is None
            ):
                self.knowledge.disposal_pos = pos

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

    def _move_randomly(self, knowledge: Knowledge) -> Move:
        """Helper method to move randomly in the visitable neighborhood."""
        pos = knowledge.positions[-1]
        available_directions = [
            (x - pos[0], y - pos[1]) for x, y in knowledge.visitable_cells
        ]
        print(
            f"{self.name} at {self.pos} (or {pos}), available directions: {available_directions}"
        )
        next_direction = self.model.random.choice(available_directions)
        print(
            f"{self.name} at {self.pos} chooses to move in direction {next_direction}"
        )
        return Move(next_direction)


class GreenRobot(Robot):
    """Green robot in zone 1."""

    def __init__(self, model: Model):
        super().__init__(model, Color.GREEN)

    def deliberate(self, knowledge: Knowledge) -> Action:
        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]

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
        green_wastes = [w for w in carried_wastes if w.waste_type == Color.GREEN]
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
        yellow_wastes = [w for w in carried_wastes if w.waste_type == Color.YELLOW]
        if yellow_wastes and len(carried_wastes) < 2:
            return PickUp(yellow_wastes[0])

        # 4. Se déplacer aléatoirement dans z1-z2
        return self._move_randomly(knowledge)


class RedRobot(Robot):
    """Red robot in zone 3."""

    def __init__(self, model: Model):
        super().__init__(model, Color.RED)

    def deliberate(self, knowledge: Knowledge) -> Action:
        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        disposal_pos = knowledge.disposal_pos

        # 1. Déposer si on est sur la zone de dépôt
        if carried_wastes and pos == disposal_pos:
            return PutDown(carried_wastes[0])

        # 2. Si on porte un rouge, naviguer vers la zone de dépôt
        if carried_wastes:
            dx = (
                1
                if disposal_pos[0] > pos[0]
                else (-1 if disposal_pos[0] < pos[0] else 0)
            )
            dy = (
                1
                if disposal_pos[1] > pos[1]
                else (-1 if disposal_pos[1] < pos[1] else 0)
            )
            # Préférer le déplacement horizontal
            if dx != 0:
                return Move((dx, 0))
            return Move((0, dy))

        # 3. Ramasser un déchet rouge
        red_wastes = [w for w in carried_wastes if w.waste_type == Color.RED]
        if red_wastes:
            return PickUp(red_wastes[0])

        # 4. Se déplacer aléatoirement
        return self._move_randomly(knowledge)
