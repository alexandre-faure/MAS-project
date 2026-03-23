"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from abc import ABC, abstractmethod
from typing import Any

from communication import CommunicatingAgent
from communication.message.Message import Message
from communication.message.MessagePerformative import MessagePerformative
from mesa import Model
from objects import PickUp, PutDown, Radioactivity, Transform, Waste, WasteDisposalZone
from utils import COLOR_TO_ZONE, Action, Color, Move, Wait, Zone


class Knowledge:
    """Beliefs and knowledges of a robot."""

    def __init__(self):
        self.round: int = 0
        self.positions: list[tuple[int, int]] = []

        self.last_seen: dict[tuple[int, int], int] = {}
        self.last_visited: dict[tuple[int, int], int] = {}
        self.cell_data: dict[tuple[int, int], Any] = {}
        self.carried_wastes: list[list[Waste]] = []
        self.visitable_cells: set[tuple[int, int]] = set()
        self.in_grid_cells: set[tuple[int, int]] = set()
        self.known_wastes: set[tuple[int, int]] = set()
        self.robots_neighborhood: set[str] = set()

        # Specific coordinates
        self.min_x_zone: int | None = None
        self.max_x_zone: int | None = None
        self.disposal_pos: tuple[int, int] | None = None

        # Other custom data
        self.data: dict[str, Any] = {}

    def merge_with_other(self, other: "Knowledge"):
        """Merge this knowledge with another one (e.g. during communication between robots)."""
        if other is None:
            return

        cells_better_known_by_other = {
            pos: round_seen
            for pos, round_seen in other.last_seen.items()
            if pos not in self.last_seen or round_seen > self.last_seen[pos]
        }
        self.last_seen.update(cells_better_known_by_other)

        self.cell_data.update(
            {
                pos: other.cell_data[pos]
                for pos in cells_better_known_by_other
                if pos in other.cell_data
            }
        )
        for pos in cells_better_known_by_other:
            if pos in other.known_wastes:
                self.known_wastes.add(pos)
            else:
                self.known_wastes.discard(pos)

        if self.min_x_zone is None:
            self.min_x_zone = other.min_x_zone

        if self.max_x_zone is None:
            self.max_x_zone = other.max_x_zone

        if self.disposal_pos is None:
            self.disposal_pos = other.disposal_pos


class Robot(CommunicatingAgent, ABC):

    def __init__(self, model: Model, color: Color):
        # CommunicatingAgent attend un paramètre `name` — on lui passe un nom par défaut
        # pour éviter le TypeError à l'initialisation. Le vrai nom est exposé via la property `name`.
        super().__init__(model, name=f"robot_{id(self)}")
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

    def is_locked(self, knowledge: Knowledge, max_wait: int = 3) -> bool:
        """Check if the robot is stuck in a position by waiting several times."""
        if len(knowledge.positions) < max_wait + 1:
            return False
        last_positions = knowledge.positions[-(max_wait + 1) :]
        return all(pos == self.pos for pos in last_positions)

    def __get_cell_data(self, pos: tuple[int, int]) -> dict:
        """Get the data of a given cell"""
        cellmates = self.model.grid.get_cell_list_contents([pos])

        radioactivity_cell = next(
            (a for a in cellmates if isinstance(a, Radioactivity)), None
        )
        if radioactivity_cell is None:
            raise ValueError(f"No radioactivity found in cell {pos} for {self.name}")

        wastes = [
            a
            for a in cellmates
            if isinstance(a, Waste) and a.waste_type == self.color
            #  disposal_pos peut être None, on vérifie avant de comparer
            and (
                self.knowledge.disposal_pos is None
                or a.pos != self.knowledge.disposal_pos
            )
        ]

        waste_disposal = next(
            (a for a in cellmates if isinstance(a, WasteDisposalZone)), None
        )

        other_robots = [a for a in cellmates if isinstance(a, Robot)]
        visitable = (
            (radioactivity_cell.radioactivity <= self.max_radioactivity)
            and pos != self.pos
            and not other_robots
        )

        return {
            "pos": pos,
            "radioactivity": radioactivity_cell.radioactivity,
            "wastes": wastes,
            "waste_disposal": waste_disposal,
            "visitable": visitable,
            "is_lower_zone": radioactivity_cell.radioactivity
            <= self.zone_min_radioactivity,
            "is_higher_zone": radioactivity_cell.radioactivity > self.max_radioactivity,
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

    def _build_knowledge_message(self) -> dict:
        """Write the message content containing the knowledge of
        the robot to share with other robots during communication."""
        return {
            "timestamp": self.knowledge.round,
            "sender_id": self.unique_id,
            "known_wastes": {
                pos: self.knowledge.last_seen[pos]
                for pos in self.knowledge.known_wastes
                if pos in self.knowledge.last_seen
                and self.knowledge.last_seen[pos] is not None
            },
            "carried_wastes": [
                w.waste_type.value for w in self.carrying if w is not None
            ],
        }

    def _broadcast_knowledge(self):
        """Send a message containing the knowledge of the robot
        to all other robots of the same color."""
        payload = self._build_knowledge_message()
        same_color_robots = self.model.agents_by_type.get(type(self), [])
        for agent in same_color_robots:
            if agent.unique_id != self.unique_id:
                self.send_message(
                    Message(
                        self.get_name(),
                        agent.get_name(),
                        MessagePerformative.INFORM_REF,
                        payload,
                    )
                )

    def _process_incoming_messages(self):
        """Process received messages and merge knowledge."""
        for message in self.get_new_messages():

            if message is None:
                continue
            if message.get_performative() != MessagePerformative.INFORM_REF:
                continue

            payload = message.get_content()
            if not isinstance(payload, dict):
                continue

            msg_timestamp: int = payload.get("timestamp", -1)
            known_wastes = payload.get("known_wastes")
            sender_id = payload.get("sender_id")

            if isinstance(known_wastes, dict):
                for pos_raw, round_seen in known_wastes.items():

                    pos = tuple(pos_raw) if not isinstance(pos_raw, tuple) else pos_raw
                    if round_seen is None:
                        continue
                    our_round = self.knowledge.last_seen.get(pos, -1)
                    if round_seen > our_round:
                        self.knowledge.last_seen[pos] = round_seen
                        self.knowledge.known_wastes.add(pos)

            if sender_id is not None:
                carried = payload.get("carried_wastes")
                self.knowledge.data[f"carried_by_{sender_id}"] = {
                    "wastes": carried if isinstance(carried, list) else [],
                    "timestamp": msg_timestamp,
                }

    def update_knowledge(self, percepts: dict):
        """Update the knowledge of the robot based on its perception."""
        cur_pos = self.pos
        self.knowledge.robots_neighborhood.clear()
        self.knowledge.round += 1
        self.knowledge.positions.append(cur_pos)
        self.knowledge.visitable_cells.clear()
        self.knowledge.last_visited[cur_pos] = self.knowledge.round

        for pos, data in percepts.items():
            if data is None:
                continue

            self.knowledge.in_grid_cells.add(pos)
            self.knowledge.last_seen[pos] = self.knowledge.round
            self.knowledge.cell_data[pos] = data
            self.knowledge.carried_wastes.append(self.carrying.copy())

            if len(data.get("wastes", [])) > 0:
                self.knowledge.known_wastes.add(pos)
            else:
                self.knowledge.known_wastes.discard(pos)

            if data.get("visitable"):
                self.knowledge.visitable_cells.add(pos)

            if (
                data.get("waste_disposal") is not None
                and self.knowledge.disposal_pos is None
            ):
                self.knowledge.disposal_pos = pos

            cur_pos_data = percepts.get(cur_pos)
            if cur_pos_data is not None:
                if not cur_pos_data.get("is_lower_zone") and data.get("is_lower_zone"):
                    self.knowledge.min_x_zone = cur_pos[0]
                if not cur_pos_data.get("is_higher_zone") and data.get(
                    "is_higher_zone"
                ):
                    self.knowledge.max_x_zone = cur_pos[0]

    @abstractmethod
    def deliberate(self, knowledge: Knowledge) -> Action:
        """
        Deliberation step of the robot.
        It returns one or several actions to execute.
        """

    def step_agent(self):
        """Execute one step of the agent"""
        self._process_incoming_messages()
        percepts = self.perceive()
        self.update_knowledge(percepts)
        action = self.deliberate(self.knowledge)
        self.model.do(self, action)
        self._broadcast_knowledge()

    def _discover_randomly(self, knowledge: Knowledge, axis: int | None = None) -> Move:
        """
        Move randomly towards a visitable cell not recently visited.
        Axis:
        - 0 : prefer horizontal moves (east-west)
        - 1 : prefer vertical moves (north-south)
        - None: no axis preference
        """

        if not knowledge.positions:
            return Wait()

        cur_pos = knowledge.positions[-1]
        available_moves = [
            (knowledge.last_visited.get(pos, -1), pos)
            for pos in knowledge.visitable_cells
        ]
        if not available_moves:
            return Wait()

        available_moves.sort(key=lambda x: x[0])
        available_directions = [
            (t, (x - cur_pos[0], y - cur_pos[1])) for t, (x, y) in available_moves
        ]

        if axis == 0:
            available_directions = [d for d in available_directions if d[1][1] == 0]
        elif axis == 1:
            available_directions = [d for d in available_directions if d[1][0] == 0]

        if not available_directions:
            return Wait()

        candidates = [
            d[1] for d in available_directions if d[0] == available_directions[0][0]
        ]

        if not candidates:
            return Wait()

        next_direction = self.model.random.choice(candidates)
        return Move(direction=next_direction)

    def _move_in_direction(
        self, direction: tuple[int, int], knowledge: Knowledge
    ) -> Action:

        if not knowledge.positions:
            return Wait()

        cur_pos = knowledge.positions[-1]

        if not direction[0] and not direction[1]:
            return Wait()
        if direction[0] and direction[1]:
            direction = (direction[0], 0)

        next_pos = (cur_pos[0] + direction[0], cur_pos[1] + direction[1])

        if next_pos in knowledge.visitable_cells:
            return Move(direction=direction)

        if not self.is_locked(knowledge):
            return Wait()

        return self._discover_randomly(knowledge)

    def _move_randomly(self, knowledge: Knowledge) -> Move:
        """Helper method to move in a random direction."""
        visitable_cells = knowledge.visitable_cells
        if not visitable_cells:
            return Wait()
        next_pos = self.model.random.choice(list(visitable_cells))
        return Move(position=next_pos)

    def _move_towards(
        self, target_pos: tuple[int | None, int | None], knowledge: Knowledge
    ) -> Action:
        """Helper method to move towards a target position."""

        if not knowledge.positions:
            return Wait()

        if target_pos is None:
            return Wait()

        cur_pos = knowledge.positions[-1]
        tx, ty = target_pos
        dx, dy = 0, 0
        if tx is not None:
            dx = tx - cur_pos[0]
        if ty is not None:
            dy = ty - cur_pos[1]

        direction = (0, 0)
        if abs(dx) > abs(dy):
            direction = (1 if dx > 0 else -1, 0)
        elif dy != 0:
            direction = (0, 1 if dy > 0 else -1)

        return self._move_in_direction(direction, knowledge)

    def _go_to_closest_waste(self, knowledge: Knowledge) -> Action:

        if not knowledge.positions:
            return Wait()

        cur_pos = knowledge.positions[-1]
        #  on filtre les positions de known_wastes dont on n'a pas de cell_data
        # (connues par communication mais jamais vues directement) pour éviter des
        # incohérences, tout en gardant les positions valides
        valid_wastes = [pos for pos in knowledge.known_wastes if pos is not None]
        if not valid_wastes:
            return self._discover_randomly(knowledge)

        manhattan_distances = [
            (abs(pos[0] - cur_pos[0]) + abs(pos[1] - cur_pos[1]), pos)
            for pos in valid_wastes
        ]
        _, closest_waste_pos = min(manhattan_distances, key=lambda x: x[0])
        return self._move_towards(closest_waste_pos, knowledge)

    def _get_current_carried_wastes(self, knowledge: Knowledge) -> list[Waste]:
        """Safe accessor for the current carried wastes."""
        #  carried_wastes peut être vide au premier tour
        if not knowledge.carried_wastes:
            return []
        return knowledge.carried_wastes[-1]


class GreenRobot(Robot):
    """Green robot in zone 1."""

    def __init__(self, model: Model, is_random: bool = False, has_memory: bool = True):
        super().__init__(model, Color.GREEN)
        self.is_random = is_random
        self.has_memory = has_memory

    def deliberate(self, knowledge: Knowledge) -> Action:
        # utilisation du helper sécurisé pour carried_wastes
        if not knowledge.positions:
            return Wait()

        pos = knowledge.positions[-1]
        carried_wastes = self._get_current_carried_wastes(knowledge)
        current_cell_data = knowledge.cell_data.get(pos, {})

        # 1. Transformer 2 verts → 1 jaune
        if len(carried_wastes) == 2 and all(
            w is not None and w.waste_type == Color.GREEN for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # 2. Déposer le jaune à la frontière z1/z2
        if (
            len(carried_wastes) == 1
            and carried_wastes[0] is not None
            and carried_wastes[0].waste_type == Color.YELLOW
        ):
            if knowledge.max_x_zone is not None and pos[0] == knowledge.max_x_zone:
                return PutDown(carried_wastes[0])
            return self._move_in_direction((1, 0), knowledge)

        # 3. Ramasser un déchet vert sur la cellule
        green_wastes = current_cell_data.get("wastes", [])
        if green_wastes and len(carried_wastes) < 2:
            return PickUp(green_wastes[0])

        # 4. Aller vers le déchet vert connu le plus proche
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        # 5. Explorer aléatoirement dans z1
        if self.is_random:
            return self._move_randomly(knowledge)
        return self._discover_randomly(knowledge)


class YellowRobot(Robot):
    """Yellow robot in zone 2."""

    def __init__(self, model: Model, is_random: bool = False, has_memory: bool = True):
        super().__init__(model, Color.YELLOW)
        self.is_random = is_random
        self.has_memory = has_memory

    def deliberate(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            return Wait()

        pos = knowledge.positions[-1]
        carried_wastes = self._get_current_carried_wastes(knowledge)
        current_cell_data = knowledge.cell_data.get(pos, {})

        # 1. Transformer 2 jaunes → 1 rouge
        if len(carried_wastes) == 2 and all(
            w is not None and w.waste_type == Color.YELLOW for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # 2. Déposer le rouge à la frontière z2/z3
        if (
            len(carried_wastes) == 1
            and carried_wastes[0] is not None
            and carried_wastes[0].waste_type == Color.RED
        ):
            if knowledge.max_x_zone is not None and pos[0] == knowledge.max_x_zone:
                return PutDown(carried_wastes[0])
            return self._move_in_direction((1, 0), knowledge)

        # 3. Ramasser un déchet jaune
        yellow_wastes = current_cell_data.get("wastes", [])
        if yellow_wastes and len(carried_wastes) < 2:
            return PickUp(yellow_wastes[0])

        # 4. Aller vers le déchet jaune connu le plus proche
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        # 5. Si le robot est naïf, il explore aléatoirement
        if self.is_random:
            return self._move_randomly(knowledge)

        # 6. Inspecter la frontière pour être prêt à récupérer les déchets jaunes déposés par les verts
        if knowledge.min_x_zone is None:
            return self._move_in_direction((-1, 0), knowledge)
        if pos[0] != knowledge.min_x_zone - 1:
            return self._move_towards((knowledge.min_x_zone - 1, None), knowledge)

        # 7. Explorer aléatoirement à la frontière
        return self._discover_randomly(knowledge, axis=1)


class RedRobot(Robot):
    """Red robot in zone 3."""

    def __init__(self, model: Model, is_random: bool = False, has_memory: bool = True):
        super().__init__(model, Color.RED)
        self.is_random = is_random
        self.has_memory = has_memory

    def deliberate(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            return Wait()

        pos = knowledge.positions[-1]
        carried_wastes = self._get_current_carried_wastes(knowledge)
        current_cell_data = knowledge.cell_data.get(pos, {})
        disposal_pos = knowledge.disposal_pos

        # 1. Trouver la zone de dépôt si on ne la connaît pas encore
        if not self.is_random and disposal_pos is None:
            if (pos[0] + 1, pos[1]) in knowledge.in_grid_cells:
                return self._move_in_direction((1, 0), knowledge)
            return self._discover_randomly(knowledge, axis=1)

        # 2. Déposer si on est sur la zone de dépôt
        if carried_wastes and pos == disposal_pos:
            return PutDown(carried_wastes[0])

        # 3. Si on porte un rouge, naviguer vers la zone de dépôt
        if carried_wastes and self.has_memory and knowledge.disposal_pos is not None:
            return self._move_towards(knowledge.disposal_pos, knowledge)

        # 4. Ramasser un déchet rouge si on n'en porte pas déjà un
        red_wastes = current_cell_data["wastes"]
        if red_wastes and not self.carrying:
            return PickUp(red_wastes[0])

        # 5. Aller vers le déchet rouge connu le plus proche
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        # 6. Si le robot est naïf, il explore aléatoirement
        if self.is_random:
            return self._move_randomly(knowledge)

        # 7. Inspecter la frontière pour être prêt à récupérer les déchets rouges déposés par les jaunes
        if knowledge.min_x_zone is None:
            return self._move_in_direction((-1, 0), knowledge)
        if pos[0] != knowledge.min_x_zone - 1:
            return self._move_towards((knowledge.min_x_zone - 1, None), knowledge)

        # 8. Explorer aléatoirement à la frontière
        return self._discover_randomly(knowledge, axis=1)
