"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from abc import ABC, abstractmethod
from random import randint
from typing import Any

from matplotlib.colors import same_color

from communication import CommunicatingAgent
from communication.message.Message import Message
from communication.message.MessagePerformative import MessagePerformative
from mesa import Model
from objects import Radioactivity, Waste, WasteDisposalZone
from utils import (
    COLOR_TO_ZONE,
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
        self.robots_neighborhood: set[str] = set() #contains robots objects and not only their names
        
        # flag to indicate if the robot should move (used to avoid picking up a waste when it was just dropped)
        # Specific coordinates
        self.min_x_zone: int | None = None
        self.max_x_zone: int | None = None
        self.disposal_pos: tuple[int, int] | None = None

        # Other custom data
        self.data: dict[str, Any] = {}

        # Behavior (should explore for x steps before going to explore the border for yellow and red)
        self.must_explore: int = Robot.EXPLORE_DURATION

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
    EXPLORE_DURATION = 10
    MAX_PATROL_DURATION = 20

    def __init__(self, model: Model, color: Color, robot_behavior: RobotBehavior):
        # CommunicatingAgent attend un paramètre `name` — on lui passe un nom par défaut
        # pour éviter le TypeError à l'initialisation. Le vrai nom est exposé via la property `name`.
        super().__init__(model, name=f"robot_{id(self)}")
        self.color = color
        self.has_memory = robot_behavior in [
            RobotBehavior.MEMORY,
            RobotBehavior.COMMUNICATION,
        ]
        self.is_random = robot_behavior == RobotBehavior.RANDOM
        self.carrying: list[Waste] = []
        self.knowledge = Knowledge()
        self.wait_answer = False
        self.messages_to_send: list[Message] = []
        self.drop_object: bool = False
        self.carried_since = 0
        self.must_move = False 
        self.nb_exploring_steps = 0
        self.nb_wastes_collected = 0

    @property
    def name(self):
        return f"Agent {self.color.value} ({self.unique_id})"

    @property
    def zone(self) -> Zone:
        return COLOR_TO_ZONE[self.color]

    @property
    def zone_min_radioactivity(self) -> float:
        return (self.zone.value - 1) / 3

    @property
    def max_radioactivity(self) -> float:
        return self.zone.value / 3

    def is_locked(self, knowledge: Knowledge, max_wait: int = 3) -> bool:
        if len(knowledge.positions) < max_wait + 1:
            return False
        last_positions = knowledge.positions[-(max_wait + 1):]
        return all(pos == self.pos for pos in last_positions)

    def __get_cell_data(self, pos: tuple[int, int]) -> dict:
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
            "is_lower_zone": radioactivity_cell.radioactivity <= self.zone_min_radioactivity,
            "robots": other_robots,
            "is_higher_zone": radioactivity_cell.radioactivity > self.max_radioactivity,
        }

    def perceive(self) -> dict:
        neighborhood = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=True
        )
        data_per_cell = {pos: self.__get_cell_data(pos) for pos in neighborhood}
        return data_per_cell

    def _build_knowledge_message(self) -> dict:
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
            "carried_wastes": [
                w.waste_type.value for w in self.carrying if w is not None
            ],
        }

    def _prepare_broadcast_knowledge(self):
        """Append one INFORM_REF message to every same-color peer."""
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
            performative = message.get_performative()

            # Knowledge broadcast — always process
            if performative == MessagePerformative.INFORM_REF:
                payload = message.get_content()
                if not isinstance(payload, dict):
                    continue
                sender_id = payload.get("sender_id")
                msg_timestamp: int = payload.get("timestamp", -1)
                known_wastes = payload.get("known_wastes")

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

            # Someone is offering us a waste object
            elif performative == MessagePerformative.PROPOSE_TO_GIVE:
                payload = message.get_content()
                sender_id = payload.get("sender_id") if isinstance(payload, dict) else None
                proposed_waste: Waste = payload.get("proposed_waste")

                # Accept if the proposed waste is of our color and we have room
                if (
                    proposed_waste is not None
                    and proposed_waste.waste_type == self.color
                    and len(self.carrying) < 2
                ):
                    self.messages_to_send.append(
                        Message(
                            self.get_name(),
                            message.get_exp(),
                            MessagePerformative.ACCEPT_EXCHANGE,
                            {"accepted_waste": proposed_waste.waste_type.value,
                             "sender_id": self.unique_id},
                        )
                    )
                    self.wait_answer = False
                else:
                    self.messages_to_send.append(
                        Message(
                            self.get_name(),
                            message.get_exp(),
                            MessagePerformative.REJECT_EXCHANGE,
                            {"rejected_waste": proposed_waste,
                             "sender_id": self.unique_id},
                        )
                    )
                    self.wait_answer = False

            # Our outgoing proposal was accepted → we should drop the waste
            elif performative == MessagePerformative.ACCEPT_EXCHANGE:
                self.drop_object = True
                self.wait_answer = False

            # Our outgoing proposal was rejected → stop waiting, try elsewhere
            elif performative == MessagePerformative.REJECT_EXCHANGE:
                self.wait_answer = False

    def update_knowledge(self, percepts: dict):
        cur_pos = self.pos
        self.knowledge.robots_neighborhood.clear()
        self.knowledge.round += 1
        self.knowledge.positions.append(cur_pos)
        self.knowledge.visitable_cells.clear()
        self.knowledge.last_visited[cur_pos] = self.knowledge.round
        self.knowledge.must_explore = max(self.knowledge.must_explore - 1, 0)

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
                if not cur_pos_data.get("is_higher_zone") and data.get(
                    "is_higher_zone"
                ):
                    self.knowledge.max_x_zone = cur_pos[0]

            # Track neighbouring robots (for exchange proposals)
            for robot in data.get("robots", []):
                if robot is not self:
                    self.knowledge.robots_neighborhood.add(robot)

    @abstractmethod
    def deliberate(self, knowledge: Knowledge) -> Action:
        pass

    def step_agent(self):
        self._process_incoming_messages()
        percepts = self.perceive()
        self.update_knowledge(percepts)
        action = self.deliberate(self.knowledge)
        self.model.do(self, action)

    # ------------------------------------------------------------------ helpers

    def _find_neighbour_of_color(self, color: Color) -> "Robot | None":
        """Return the first neighbouring robot of the given color, or None."""
        for data in self.knowledge.cell_data.values():
            for robot in data.get("robots", []):
                if robot is not self and robot.color == color:
                    return robot
        return None


    def _prepare_exchange_proposal(self, waste: Waste, receiver_name: str) -> Message:
        """Prepare a PROPOSE_TO_GIVE message for a specific receiver (by agent name)."""
        return Message(
            self.get_name(),
            receiver_name,
            MessagePerformative.PROPOSE_TO_GIVE,
            {"proposed_waste": waste, "sender_id": self.unique_id},
        )

    def _discover_randomly(self, knowledge: Knowledge, axis: int | None = None) -> Move:
        if not knowledge.positions:
            return Wait()

        cur_pos = knowledge.positions[-1]
        available_moves = [
            (knowledge.last_visited.get(pos, -1), pos)
            for pos in knowledge.visitable_cells
            if (not in_area or knowledge.cell_data[pos]["my_zone"])
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
        return Move(direction=next_direction)

    def _move_in_direction(self, direction: tuple[int, int], knowledge: Knowledge) -> Action:
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
            return Move(direction=direction)

        if not self.is_locked(knowledge):
            return Wait()

        return self._discover_randomly(knowledge)

    def _move_randomly(self, knowledge: Knowledge) -> Move:
        visitable_cells = knowledge.visitable_cells
        if not visitable_cells:
            return Wait()
        next_pos = self.model.random.choice(list(visitable_cells))
        return Move(position=next_pos)

    def _move_towards(self, target_pos: tuple[int | None, int | None], knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            return Wait()
        if target_pos is None:
            return Wait()

        cur_pos = knowledge.positions[-1]
        tx, ty = target_pos
        if tx is None:
            tx = cur_pos[0]
        if ty is None:
            ty = cur_pos[1]

        next_candidates = [
            (abs(x - tx) + abs(y - ty), (x, y)) for (x, y) in knowledge.visitable_cells
        ]
        if not next_candidates:
            return Wait()

        min_dist = min(next_candidates, key=lambda x: x[0])[0]
        best_next = [pos for dist, pos in next_candidates if dist == min_dist]

        return Move(position=self.model.random.choice(best_next))

    def _go_to_closest_waste(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            return Wait()

        cur_pos = knowledge.positions[-1]
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
        if not knowledge.carried_wastes:
            return []
        return knowledge.carried_wastes[-1]

    def pick_up(self, waste: Waste) -> Action:
        """Helper method to return a PickUp action for a given waste."""
        self.nb_wastes_collected += 1
        return PickUp(waste)


class GreenRobot(Robot):
    """Green robot in zone 1.
    Priority 0a: flush outgoing messages (replies built last step)
    Priority 0b: drop waste when peer accepted our proposal
    Priority 0c: wait for the peer's answer to our proposal (while still broadcasting
    knowledge)
    Priority 1: transform 2 green wastes → 1 yellow
    Priority 2: deposit yellow waste at z1/z2 boundary
    Priority 3: propose exchange if carrying waste for too long
    Priority 4: pick up / explore / broadcast"""

    def __init__(self, model: Model, is_random: bool = False, has_memory: bool = True):
        super().__init__(model, Color.GREEN)
        self.is_random = is_random
        self.has_memory = has_memory

    def deliberate(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            return Wait()

        pos = knowledge.positions[-1]
        carried_wastes = self._get_current_carried_wastes(knowledge)
        current_cell_data = knowledge.cell_data.get(pos, {})
        same_color_carried_wastes = [w for w in carried_wastes if w is not None and w.waste_type == self.color]

        # Maintain carried_since: only count steps where we are actually carrying something
        if carried_wastes:
            self.carried_since += 1
        else:
            self.carried_since = 0

        # ── Priority 0a: flush outgoing messages (replies built last step) ────
        # _process_incoming_messages() may have appended ACCEPT/REJECT replies;
        # send them before any other action so the peer is never left waiting.
        if self.messages_to_send:
            msgs = list(self.messages_to_send)
            self.messages_to_send.clear()
            return SendMessages(msgs)

        # ── Priority 0b: drop waste when the peer accepted our proposal ───────
        # drop_object is set by _process_incoming_messages() upon ACCEPT_EXCHANGE.
        if self.drop_object and carried_wastes:
            waste_to_drop = next(
                (w for w in carried_wastes if w is not None and w.waste_type == self.color),
                None,
            )
            if waste_to_drop is not None:
                self.drop_object = False
                self.carried_since = 0
                return PutDown(waste_to_drop)

        # ── Priority 0c: wait for the peer's answer to our proposal ──────────
        # While waiting we still broadcast knowledge so peers stay informed,
        # then return SendMessages. If there is nothing to send (no peers),
        # fall through to normal logic.
        if self.wait_answer:
            self._prepare_broadcast_knowledge()
            self.wait_answer = False
            if self.messages_to_send:
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            # No peers → give up waiting and continue
            

        # ── Priority 1: transform 2 green wastes → 1 yellow ─────────────────
        if len(carried_wastes) == 2 and all(
            w is not None and w.waste_type == Color.GREEN for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # ── Priority 2: deposit yellow waste at z1/z2 boundary ───────────────
        if (
            len(carried_wastes) == 1
            and carried_wastes[0] is not None
            and carried_wastes[0].waste_type == Color.YELLOW
        ):
            if knowledge.max_x_zone is not None and pos[0] == knowledge.max_x_zone:
                self.carried_since = 0
                return PutDown(carried_wastes[0])
            return self._move_in_direction((1, 0), knowledge)

        # ── Priority 3: propose exchange if carrying waste for too long ───────
        # Only propose when not already waiting and there is a same-color neighbour.
        if same_color_carried_wastes and self.carried_since > 10 and not self.wait_answer and not self.must_move:
            neighbour = self._find_neighbour_of_color(Color.GREEN)
            if neighbour is not None:
                self.messages_to_send.append(
                    self._prepare_exchange_proposal(carried_wastes[0], neighbour.get_name())
                )
                self.wait_answer = True
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            else :
                self.must_move = True
                 # if we are carrying something for a long time but have no neighbour to exchange with, we should move to try to find someone to exchange with or a better position to drop the waste
                return PutDown(carried_wastes[0]) 
            # if we have no neighbour to exchange with, just drop the waste and try again (we might be in a better position next step)

        # ── Priority 4:pick up / explore ───────────
        epsilon = 0.01
        if randint(0, 100) < epsilon * 100: #broacast knowledge with some probability even if we have something else to do, to increase information flow in the system
            self._prepare_broadcast_knowledge()
            return SendMessages(list(self.messages_to_send)) if self.messages_to_send else Wait()
        
        # Pick up a green waste on the current cell
        green_wastes = current_cell_data.get("wastes", [])
        if green_wastes and len(carried_wastes) < 2:
            return self.pick_up(green_wastes[0])

        # Move towards the nearest known green waste
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        if self.is_random:
            return self._move_randomly(knowledge)
        return self._discover_randomly(knowledge)


# ══════════════════════════════════════════════════════════════════════════════
#  YellowRobot
# ══════════════════════════════════════════════════════════════════════════════

class YellowRobot(Robot):
    """Yellow robot in zone 2.
        Prioririty 0a: flus outgoing messages
        Priotity 0b: drop waste when peer accepted our proposal
        Priority 0c: wait for answer to our proposal (while still broadcasting knowledge)
        Priority 1: transform 2 yellow wastes → 1 red
        Priority 2: deposit red waste at z2/z3 boundary
        Priority 3: propose exchange if carrying too long
        Priority 4: pick up / explore / broadcast
        """

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
        same_color_carried_wastes = [w for w in carried_wastes if w is not None and w.waste_type == self.color]

        if carried_wastes:
            self.carried_since += 1
        else:
            self.carried_since = 0

        # ── Priority 0a: flush outgoing messages ─────────────────────────────
        if self.messages_to_send:
            msgs = list(self.messages_to_send)
            self.messages_to_send.clear()
            return SendMessages(msgs)

        # ── Priority 0b: drop waste when peer accepted our proposal ──────────
        if self.drop_object and carried_wastes:
            waste_to_drop = next(
                (w for w in carried_wastes if w is not None and w.waste_type == self.color),
                None,
            )
            if waste_to_drop is not None:
                self.drop_object = False
                self.carried_since = 0
                return PutDown(waste_to_drop)

        # ── Priority 0c: wait for answer to our proposal ─────────────────────
        if self.wait_answer:
            self._prepare_broadcast_knowledge()
            self.wait_answer = False
            if self.messages_to_send:
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            

        # ── Priority 1: transform 2 yellow wastes → 1 red ────────────────────
        if len(carried_wastes) == 2 and all(
            w is not None and w.waste_type == Color.YELLOW for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # ── Priority 2: deposit red waste at z2/z3 boundary ───────────────
        if (
            len(carried_wastes) == 1
            and carried_wastes[0] is not None
            and carried_wastes[0].waste_type == Color.RED
        ):
            if knowledge.max_x_zone is not None and pos[0] == knowledge.max_x_zone:
                self.carried_since = 0
                self.knowledge.must_explore = Robot.EXPLORE_DURATION + 1
                return PutDown(carried_wastes[0])
            return self._move_in_direction((1, 0), knowledge)


        # ── Priority 3: propose exchange if carrying too long ─────────────────
        if same_color_carried_wastes and self.carried_since > 10 and not self.wait_answer and not self.must_move:
            neighbour = self._find_neighbour_of_color(Color.YELLOW)
            if neighbour is not None:
                self.messages_to_send.append(
                    self._prepare_exchange_proposal(carried_wastes[0], neighbour.get_name())
                )
                self.wait_answer = True
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            else :
                self.must_move = True
                return PutDown(carried_wastes[0])

        # ── Priority 4: pick up /  explore / broadcast─────────────────────────
        epsilon = 0.01
        if randint(0, 100) < epsilon * 100: #broacast knowledge with some probability even if we have something else to do, to increase information flow in the system
            self._prepare_broadcast_knowledge()
            return SendMessages(list(self.messages_to_send)) if self.messages_to_send else Wait()
        

        yellow_wastes = current_cell_data.get("wastes", [])
        if yellow_wastes and len(carried_wastes) < 2:
            return self.pick_up(yellow_wastes[0])

        self.must_move = False
         # reset must_move flag once we have moved or picked up a waste
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        if self.is_random:
            return self._move_randomly(knowledge)

        if knowledge.min_x_zone is None:
            return self._move_in_direction((-1, 0), knowledge)
        if not knowledge.must_explore and pos[0] != knowledge.min_x_zone - 1:
            return self._move_towards((knowledge.min_x_zone - 1, None), knowledge)

        return self._discover_randomly(knowledge, axis=1)


# ══════════════════════════════════════════════════════════════════════════════
#  RedRobot
# ══════════════════════════════════════════════════════════════════════════════

class RedRobot(Robot):
    """Red robot in zone 3."""

    def __init__(self, model: Model, is_random: bool = False, has_memory: bool = True):
        super().__init__(model, Color.RED)
        self.is_random = is_random
        self.has_memory = has_memory

    def deliberate(self, knowledge: Knowledge) -> Action:
        """
        Priorities :
        1: find disposal zone (if not known)
        0a: flush outgoing messages (replies to proposals)
        0b: drop waste if peer accepted our proposal
        0c: wait for answer to our proposal (while still broadcasting knowledge)
        
        2: deposit at disposal zone if carrying
        4: pick up red waste on current cell
        3: carry red waste to disposal zone if we know it   
        5: go to nearest known red waste
        6: broadcast knowledge and explore
        """
        
        if not knowledge.positions:
            return Wait()

        pos = knowledge.positions[-1]
        carried_wastes = self._get_current_carried_wastes(knowledge)
        current_cell_data = knowledge.cell_data.get(pos, {})
        disposal_pos = knowledge.disposal_pos

        if carried_wastes:
            self.carried_since += 1
        else:
            self.carried_since = 0
        
        # ── Priority 1: find disposal zone ───────────────────────────────────
        if not self.is_random and disposal_pos is None:
            if (pos[0] + 1, pos[1]) in knowledge.in_grid_cells:
                return self._move_in_direction((1, 0), knowledge)
            return self._discover_randomly(knowledge, axis=1)
        
        # ── Priority 0a: flush outgoing messages ─────────────────────────────
        if self.messages_to_send:
            msgs = list(self.messages_to_send)
            self.messages_to_send.clear()
            return SendMessages(msgs)

        # ── Priority 0b: drop waste when peer accepted our proposal ──────────
        if self.drop_object and carried_wastes:
            waste_to_drop = next(
                (w for w in carried_wastes if w is not None and w.waste_type == self.color),
                None,
            )
            if waste_to_drop is not None:
                self.drop_object = False
                self.carried_since = 0
                return PutDown(waste_to_drop)

        # ── Priority 0c: wait for answer ─────────────────────────────────────
        if self.wait_answer:
            self.wait_answer = False
            self._prepare_broadcast_knowledge()
            if self.messages_to_send:
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            
        # ── Priority 2: deposit at disposal zone ─────────────────────────────
        if carried_wastes and pos == disposal_pos:
            self.carried_since = 0
            self.knowledge.must_explore = Robot.EXPLORE_DURATION + 1
            return PutDown(carried_wastes[0])
        
        # ── Priority 4: pick up red waste ─────────────────────────────────────
        # if the robot is on a cell with red wastes, it picks up one
        red_wastes = current_cell_data.get("wastes", [])
        if red_wastes:
            return PickUp(red_wastes[0])


        # ── Priority 3: carry red waste to disposal zone ──────────────────────
        if carried_wastes and self.has_memory and knowledge.disposal_pos is not None:
            self._prepare_broadcast_knowledge()
            if self.messages_to_send:
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            return self._move_towards(knowledge.disposal_pos, knowledge)



        # ── Priority 5: go to nearest known red waste ─────────────────────────
        if self.has_memory and knowledge.known_wastes:
            self._prepare_broadcast_knowledge()
            if self.messages_to_send:
                msgs = list(self.messages_to_send)
                self.messages_to_send.clear()
                return SendMessages(msgs)
            return self._go_to_closest_waste(knowledge)

        # ── Priority 6: broadcast and explore ────────────────────────────────
        epsilon = 0.01
        if randint(0, 100) < epsilon * 100: #broacast knowledge with some probability even if we have something else to do, to increase information flow in the system
            self._prepare_broadcast_knowledge()
            return SendMessages(list(self.messages_to_send)) if self.messages_to_send else Wait()
        
        if self.messages_to_send:
            msgs = list(self.messages_to_send)
            self.messages_to_send.clear()
            return SendMessages(msgs)

        if self.is_random:
            return self._move_randomly(knowledge)

        if knowledge.min_x_zone is None:
            return self._move_in_direction((-1, 0), knowledge)
        if not knowledge.must_explore and pos[0] != knowledge.min_x_zone - 1:
            return self._move_towards((knowledge.min_x_zone - 1, None), knowledge)

        return self._discover_randomly(knowledge, axis=1)