"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

# ══════════════════════════════════════════════════════════════════════════════
#  Fusion of agents_communication.py (file 1) and agents_base.py (file 2).
#
#  Key design decisions:
#  - step_agent: perceive → update_knowledge → deliberate → do (no broadcast)
#  - Broadcast = SendMessages action chosen in deliberate, never automatic
#  - Exchange protocol (PROPOSE_TO_GIVE / ACCEPT_EXCHANGE / REJECT_EXCHANGE)
#    is preserved from file 1, gated on self.can_communicate
#  - carried_wastes.append is called once per step (bug fix from file 2)
#  - must_move is reset as soon as the robot returns any Move action
#  - wait_answer: robot sends pending messages instead of waiting passively
#  - RedRobot: pick up first, then find disposal zone (file 2 logic)
#  - Action priority within deliberate:
#      Transform > PutDown(drop_object) > PickUp > flush messages_to_send > rest
# ══════════════════════════════════════════════════════════════════════════════

from abc import ABC, abstractmethod
from random import randint
from typing import Any

from altair import Position
from ipyvuetify import Col

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
    SendMessages,
)

# Probability of broadcasting knowledge when nothing more urgent to do
BROADCAST_EPSILON = 0.01


class Knowledge:
    """Beliefs and knowledge of a robot."""

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
        self.robots_neighborhood: set[Any] = set()  # Robot objects, not just names

        # Zone boundary coordinates (discovered at runtime)
        self.min_x_zone: int | None = None
        self.max_x_zone: int | None = None
        self.disposal_pos: tuple[int, int] | None = None

        # Arbitrary extra data (e.g. carried_wastes of peers)
        self.data: dict[str, Any] = {}

        # Steps remaining before switching from exploration to boundary patrol
        self.must_explore: int = Robot.EXPLORE_DURATION

    def merge_with_other(self, other: "Knowledge"):
        """Merge this knowledge with another (e.g. during communication)."""
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
    EXPLORE_DURATION = 10
    MAX_PATROL_DURATION = 20

    def __init__(self, model: Model, color: Color, robot_behavior: RobotBehavior):
        super().__init__(model, name=f"robot_{id(self)}")
        self.color = color
        self.last_dropped_pos: tuple[int,int] | None = None

        # Behaviour flags — not mutually exclusive
        self.has_memory = robot_behavior in [
            RobotBehavior.MEMORY,
            RobotBehavior.COMMUNICATION,
        ]
        self.is_random = robot_behavior == RobotBehavior.RANDOM
        self.can_communicate = robot_behavior == RobotBehavior.COMMUNICATION

        self.carrying: list[Waste] = []
        self.knowledge = Knowledge()

        # ── Communication state ────────────────────────────────────────────
        # Outgoing message queue: filled during deliberate, sent via SendMessages
        self.messages_to_send: list[Message] = []
        # True while waiting for a reply to an outgoing PROPOSE_TO_GIVE
        self.wait_answer: bool = False
        # Set True by _process_incoming_messages when ACCEPT_EXCHANGE is received
        self.drop_object: bool = False

        # ── Carrying / movement state ──────────────────────────────────────
        # Consecutive steps during which the robot is carrying a waste
        self.carried_since: int = 0
        # Set True after failed exchange attempt (no neighbour); reset on Move
        self.must_move: bool = False

        # ── Metrics ───────────────────────────────────────────────────────
        self.nb_exploring_steps: int = 0
        self.nb_wastes_collected: int = 0

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
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

    # ── Utility helpers ───────────────────────────────────────────────────

    def is_locked(self, knowledge: Knowledge, max_wait: int = 3) -> bool:
        """True if the robot has not moved for the last max_wait steps."""
        if len(knowledge.positions) < max_wait + 1:
            return False
        last_positions = knowledge.positions[-(max_wait + 1):]
        return all(pos == self.pos for pos in last_positions)

    def _get_current_carried_wastes(self, knowledge: Knowledge) -> list[Waste]:
        """Safe accessor for the current carried wastes."""
        if not knowledge.carried_wastes:
            return []
        return knowledge.carried_wastes[-1]

    def pick_up(self, waste: Waste) -> Action:
        self.nb_wastes_collected += 1
        # Notify same-color peers to remove this position from their targets
        if self.pos is not None:
            self._queue_pickup_notification(self.pos)
        return PickUp(waste)

    # ── Perception ────────────────────────────────────────────────────────

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
            if isinstance(a, Waste)
            and a.waste_type == self.color
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
            radioactivity_cell.radioactivity <= self.max_radioactivity
            and pos != self.pos
            and not other_robots
        )
        # Confine to own zone + 1 patrol column westward, once the border is known
        if self.knowledge.min_x_zone is not None:
            visitable = visitable and pos[0] >= self.knowledge.min_x_zone - 1

        return {
            "pos": pos,
            "radioactivity": radioactivity_cell.radioactivity,
            "wastes": wastes,
            "waste_disposal": waste_disposal,
            "visitable": visitable,
            "is_lower_zone": radioactivity_cell.radioactivity <= self.zone_min_radioactivity,
            "my_zone": (
                radioactivity_cell.radioactivity <= self.max_radioactivity
                and radioactivity_cell.radioactivity > self.zone_min_radioactivity
            ),
            "is_higher_zone": radioactivity_cell.radioactivity > self.max_radioactivity,
            "robots": other_robots,
        }

    def perceive(self) -> dict:
        neighborhood = self.model.grid.get_neighborhood(
            self.pos, moore=False, include_center=True
        )
        return {pos: self.__get_cell_data(pos) for pos in neighborhood}

    # ── Knowledge update ──────────────────────────────────────────────────

    def update_knowledge(self, percepts: dict):
        """Update beliefs from fresh percepts. carried_wastes appended once per step."""
        cur_pos = self.pos
        self.knowledge.robots_neighborhood.clear()
        self.knowledge.round += 1
        self.knowledge.positions.append(cur_pos)
        self.knowledge.visitable_cells.clear()
        self.knowledge.last_visited[cur_pos] = self.knowledge.round
        self.knowledge.must_explore = max(self.knowledge.must_explore - 1, 0)

        # Snapshot of carried wastes — exactly once per step (file-2 bug fix)
        self.knowledge.carried_wastes.append(self.carrying.copy())

        # # ── anchor zone borders to own-zone cells ────────────────────────────
        # cur_pos_data = percepts.get(cur_pos)
        # if cur_pos_data is not None and cur_pos_data.get("my_zone"):
        #     # Western border: smallest x ever observed while standing in own zone
        #     if self.knowledge.min_x_zone is None or cur_pos[0] < self.knowledge.min_x_zone:
        #         self.knowledge.min_x_zone = cur_pos[0]
        #     # Eastern border: largest x ever observed while standing in own zone
        #     if self.knowledge.max_x_zone is None or cur_pos[0] > self.knowledge.max_x_zone:
        #         self.knowledge.max_x_zone = cur_pos[0]



        for pos, data in percepts.items():
            if data is None:
                continue

            self.knowledge.in_grid_cells.add(pos)
            self.knowledge.last_seen[pos] = self.knowledge.round
            self.knowledge.cell_data[pos] = data

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
                if not cur_pos_data.get("is_higher_zone") and data.get("is_lower_zone") and cur_pos_data.get("my_zone"):
                    self.knowledge.min_x_zone = cur_pos[0]
                if not cur_pos_data.get("is_lower_zone") and data.get("is_higher_zone") and cur_pos_data.get("my_zone"):
                    self.knowledge.max_x_zone = cur_pos[0]

            for robot in data.get("robots", []):
                if robot is not self:
                    self.knowledge.robots_neighborhood.add(robot)

    # ── Communication helpers ─────────────────────────────────────────────

    def _build_knowledge_message(self) -> dict:
        """ Include the waste color in the payload. """
        
        return {
            "timestamp": self.knowledge.round,
            "sender_id": self.unique_id,
            "sender_color": self.color.value,   # NEW
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

    def _prepare_broadcast_knowledge(self):
        """
        Queue one INFORM_REF per same-color peer.
        Does NOT send — caller must return SendMessages(self.messages_to_send).
        Only queues if self.can_communicate.
        """
        if not self.can_communicate:
            return
        payload = self._build_knowledge_message()
        #same_color_robots = self.model.agents_by_type.get(type(self), [])
        all_robots = self.model.agents
        for agent in all_robots:
            if agent.unique_id != self.unique_id and isinstance(agent, Robot) :
                self.messages_to_send.append(
                    Message(
                        self.get_name(),
                        agent.get_name(),
                        MessagePerformative.INFORM_REF,
                        payload,
                    )
                )

    def _prepare_exchange_proposal(self, waste: Waste, receiver_name: str) -> Message:
        return Message(
            self.get_name(),
            receiver_name,
            MessagePerformative.PROPOSE_TO_GIVE,
            {"proposed_waste": waste, "sender_id": self.unique_id},
        )

    def _find_neighbour_of_color(self, color: Color) -> "Robot | None":
        """Return the first neighbouring robot of the given color, or None."""
        for robot in self.knowledge.robots_neighborhood:
            if robot is not self and robot.color == color:
                return robot
        return None

    def _process_incoming_messages(self):
        """
        Read all pending messages and update knowledge / queue replies.
        Reading messages does NOT consume a timestep.
        Handles: INFORM_REF, PROPOSE_TO_GIVE, ACCEPT_EXCHANGE, REJECT_EXCHANGE.
        """
        for message in self.get_new_messages():
            if message is None:
                continue

            performative = message.get_performative()

            # ── Knowledge broadcast ────────────────────────────────────────
            if performative == MessagePerformative.INFORM_REF:
                payload = message.get_content()
                if not isinstance(payload, dict):
                    continue
                sender_id = payload.get("sender_id")
                sender_color = payload.get("sender_color")  
                msg_timestamp: int = payload.get("timestamp", -1)
                known_wastes = payload.get("known_wastes")            

                # Only ingest same-color waste positions — other-color peers
                # track wastes that aren't targets for this robot.
                if isinstance(known_wastes, dict) and sender_color == self.color.value:
                    for pos_raw, round_seen in known_wastes.items():
                        pos = tuple(pos_raw) if not isinstance(pos_raw, tuple) else pos_raw
                        if round_seen is None:
                            continue
                        if round_seen > self.knowledge.last_seen.get(pos, -1):
                            self.knowledge.last_seen[pos] = round_seen
                            self.knowledge.known_wastes.add(pos)

                # Keep carried-waste tracking regardless of sender color
                if sender_id is not None:
                    carried = payload.get("carried_wastes")
                    self.knowledge.data[f"carried_by_{sender_id}"] = {
                        "wastes": carried if isinstance(carried, list) else [],
                        "timestamp": msg_timestamp,
                    }
            # ── Border drop announcement ───────────────────────────────────
            elif performative == MessagePerformative.INFORM_DROP:
                payload = message.get_content()
                if not isinstance(payload, dict):
                    continue
                waste_color = payload.get("waste_color")
                pos_raw = payload.get("pos")
                msg_timestamp: int = payload.get("timestamp", -1)
                if waste_color == self.color.value and pos_raw is not None:
                    pos = tuple(pos_raw) if not isinstance(pos_raw, tuple) else pos_raw
                    if msg_timestamp > self.knowledge.last_seen.get(pos, -1):
                        self.knowledge.last_seen[pos] = msg_timestamp
                        self.knowledge.known_wastes.add(pos)

            # ── Peer pickup announcement ───────────────────────────────────
            elif performative == MessagePerformative.INFORM_PICKUP:
                payload = message.get_content()
                if not isinstance(payload, dict):
                    continue
                sender_color = payload.get("sender_color")
                pos_raw = payload.get("pos")
                msg_timestamp: int = payload.get("timestamp", -1)
                if sender_color == self.color.value and pos_raw is not None:
                    pos = tuple(pos_raw) if not isinstance(pos_raw, tuple) else pos_raw
                    # >= so pickup wins ties vs same-timestamp sightings (deletion wins)
                    if msg_timestamp >= self.knowledge.last_seen.get(pos, -1):
                        self.knowledge.last_seen[pos] = msg_timestamp
                        self.knowledge.known_wastes.discard(pos)

            # ── Incoming exchange proposal ─────────────────────────────────
            elif performative == MessagePerformative.PROPOSE_TO_GIVE:
                payload = message.get_content()
                proposed_waste: Waste | None = (
                    payload.get("proposed_waste") if isinstance(payload, dict) else None
                )

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
                            {
                                "accepted_waste": proposed_waste.waste_type.value,
                                "sender_id": self.unique_id,
                            },
                        )
                    )
                else:
                    self.messages_to_send.append(
                        Message(
                            self.get_name(),
                            message.get_exp(),
                            MessagePerformative.REJECT_EXCHANGE,
                            {
                                "rejected_waste": proposed_waste,
                                "sender_id": self.unique_id,
                            },
                        )
                    )

            # ── Our proposal was accepted → drop the waste next action ─────
            elif performative == MessagePerformative.ACCEPT_EXCHANGE:
                self.drop_object = True
                self.wait_answer = False

            # ── Our proposal was rejected → stop waiting ───────────────────
            elif performative == MessagePerformative.REJECT_EXCHANGE:
                self.wait_answer = False

    def _queue_pickup_notification(self, pos: tuple[int, int] | Position):
        """Queue an INFORM_PICKUP for same-color peers.

        Called as a side-effect when this robot picks up a waste of its own color.
        Peers will remove `pos` from their known_wastes set on receipt.
        Does not consume a step: the queued messages are flushed by P4 next step.
        """
        if not self.can_communicate:
            return
        payload = {
            "sender_id": self.unique_id,
            "sender_color": self.color.value,
            "pos": pos,
            "timestamp": self.knowledge.round,
        }
        for agent in self.model.agents:
            if agent is self or not isinstance(agent, Robot):
                continue
            if agent.color != self.color:
                continue
            self.messages_to_send.append(
                Message(
                    self.get_name(),
                    agent.get_name(),
                    MessagePerformative.INFORM_PICKUP,
                    payload,
                )
            )

    def _queue_drop_notification(self, pos: tuple[int, int], waste: Waste):
        """Queue an INFORM_DROP for robots whose color matches the dropped waste.

        Called as a side-effect on border drops (P5) and emergency drops (P6).
        Does not consume a step: the queued messages are flushed by P4 next step.
        """
        if not self.can_communicate or waste is None:
            return
        waste_color = waste.waste_type
        payload = {
            "sender_id": self.unique_id,
            "sender_color": self.color.value,
            "waste_color": waste_color.value,
            "pos": pos,
            "timestamp": self.knowledge.round,
        }
        for agent in self.model.agents:
            if agent is self or not isinstance(agent, Robot):
                continue
            if agent.color != waste_color:
                continue
            self.messages_to_send.append(
                Message(
                    self.get_name(),
                    agent.get_name(),
                    MessagePerformative.INFORM_DROP,
                    payload,
                )
            )

    # ── Agent cycle ───────────────────────────────────────────────────────

    def step_agent(self):
        """Main agent step: perceive → update → deliberate → act."""
        self._process_incoming_messages()
        percepts = self.perceive()
        self.update_knowledge(percepts)
        action = self.deliberate(self.knowledge)
        self.model.do(self, action)

    @abstractmethod
    def deliberate(self, knowledge: Knowledge) -> Action:
        pass

    # ── Movement helpers ──────────────────────────────────────────────────

    def _move(self, action: Move) -> Move:
        """Wrap any Move action: resets must_move flag and last_dropped_pos when it got away"""
        self.must_move = False
        if self.last_dropped_pos is not None and self.knowledge.positions:
            cur = self.knowledge.positions[-1]
            dist = (
                abs(cur[0] - self.last_dropped_pos[0])
                + abs(cur[1] - self.last_dropped_pos[1])
            )
            if dist >= 2:
                self.last_dropped_pos = None
        return action

    def _discover_randomly(
        self,
        knowledge: Knowledge,
        axis: int | None = None,
        in_area: bool = False,
    ) -> Action:
        """
        Move towards a visitable, least-recently-visited cell.
        axis=0  → prefer horizontal moves (east/west).
        axis=1  → prefer vertical moves (north/south).
        axis=None → no preference.
        in_area=True → restrict to cells in the robot's own zone.
        """
        self.nb_exploring_steps += 1

        cur_pos = knowledge.positions[-1]
        available_moves = [
            (knowledge.last_visited.get(pos, -1), pos)
            for pos in knowledge.visitable_cells
            if not in_area or knowledge.cell_data[pos]["my_zone"]
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

        min_t = available_directions[0][0]
        candidates = [d[1] for d in available_directions if d[0] == min_t]
        if not candidates:
            return Wait()

        return self._move(Move(direction=self.model.random.choice(candidates)))

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
            return self._move(Move(direction=direction))

        if not self.is_locked(knowledge):
            return Wait()

        return self._discover_randomly(knowledge)

    def _move_randomly(self, knowledge: Knowledge) -> Action:
        self.nb_exploring_steps += 1
        if not knowledge.visitable_cells:
            return Wait()
        next_pos = self.model.random.choice(list(knowledge.visitable_cells))
        return self._move(Move(position=next_pos))

    def _move_towards(
        self, target_pos: tuple[int | None, int | None], knowledge: Knowledge
    ) -> Action:
        if not knowledge.positions or target_pos is None:
            return Wait()

        cur_pos = knowledge.positions[-1]
        tx, ty = target_pos
        if tx is None:
            tx = cur_pos[0]
        if ty is None:
            ty = cur_pos[1]

        next_candidates = [
            (abs(x - tx) + abs(y - ty), (x, y))
            for (x, y) in knowledge.visitable_cells
        ]
        if not next_candidates:
            return Wait()

        min_dist = min(next_candidates, key=lambda x: x[0])[0]
        best_next = [pos for dist, pos in next_candidates if dist == min_dist]
        return self._move(Move(position=self.model.random.choice(best_next)))

    def _go_to_closest_waste(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            return Wait()
        excluded = self.last_dropped_pos
        valid_wastes = [
            pos
            for pos in knowledge.known_wastes
            if pos is not None and pos != excluded
        ]
        cur_pos = knowledge.positions[-1]
        if not valid_wastes:
            return self._discover_randomly(knowledge)

        _, closest = min(
            (
                (abs(p[0] - cur_pos[0]) + abs(p[1] - cur_pos[1]), p)
                for p in valid_wastes
            ),
            key=lambda x: x[0],
        )
        return self._move_towards(closest, knowledge)

    # ── Broadcast helper used inside deliberate ───────────────────────────

    def _try_broadcast(self) -> Action | None:
        """
        With probability BROADCAST_EPSILON, queue an INFORM_REF to all peers
        and return a SendMessages action.
        Returns None if the roll fails, if the robot cannot communicate,
        or if there are no peers.
        """
        if not self.can_communicate:
            return None
        if randint(0, 99) >= int(BROADCAST_EPSILON * 100):
            return None
        self._prepare_broadcast_knowledge()
        if self.messages_to_send:
            msgs = list(self.messages_to_send)
            self.messages_to_send.clear()
            return SendMessages(msgs)
        return None

    def _flush_messages(self) -> Action | None:
        """
        If there are queued outgoing messages, return a SendMessages action.
        Returns None if the queue is empty.
        """
        if self.messages_to_send:
            msgs = list(self.messages_to_send)
            self.messages_to_send.clear()
            return SendMessages(msgs)
        return None

    def _handle_wait_answer(self) -> Action | None:
        """
        When waiting for a reply, broadcast knowledge and send the messages
        instead of idling. Clears wait_answer flag.
        Returns a SendMessages action if there is something to send, else None.
        """
        self.wait_answer = False
        self._prepare_broadcast_knowledge()
        return self._flush_messages()


# ══════════════════════════════════════════════════════════════════════════════
#  GreenRobot
# ══════════════════════════════════════════════════════════════════════════════

class GreenRobot(Robot):
    """
    Green robot — operates in zone 1.

    Deliberation priority order:
      P1   Transform 2 green → 1 yellow  (immediate, no movement cost)
      P2   Drop waste because peer accepted exchange  (drop_object flag)
      P3   Pick up green waste on current cell
      P4   Flush pending outgoing messages  (replies built in _process_incoming_messages)
      P5   Deposit yellow waste at z1/z2 boundary
      P6   Propose exchange if carrying too long  [can_communicate only]
      P6b  Handle wait_answer: send pending msgs
      P7   Navigate to nearest known green waste  [has_memory only]
      P8   Epsilon broadcast  [can_communicate only]
      P9   Random walk (is_random) or systematic exploration
    """

    def __init__(self, model: Model, robot_behavior: RobotBehavior):
        super().__init__(model, Color.GREEN, robot_behavior)

    def deliberate(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:  
            self._prepare_broadcast_knowledge()
            return self._flush_messages()

        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        current_cell_data = knowledge.cell_data.get(pos, {})
        waste_to_drop = next(
                (
                    w
                    for w in carried_wastes
                    if w is not None and w.waste_type == self.color
                ),
                None,
            )

        # Maintain carried_since counter
        if carried_wastes:
            self.carried_since += 1
        else:
            self.carried_since = 0

        # ── P1: Transform 2 green → 1 yellow ─────────────────────────────
        if len(carried_wastes) == 2 and all(
            w is not None and w.waste_type == Color.GREEN for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # ── P2: Drop waste because peer accepted our exchange proposal ────
        if self.drop_object and carried_wastes:
            
            if waste_to_drop is not None:
                self.drop_object = False
                self.carried_since = 0
                self.must_move = True
                self.last_dropped_pos = pos
                return PutDown(waste_to_drop)

        # ── P3: Pick up green waste on current cell ───────────────────────
        carry_green = True if not carried_wastes or carried_wastes[0].waste_type == Color.GREEN else False
        green_wastes = current_cell_data.get("wastes", [])
        if green_wastes and len(carried_wastes) < 2 and not self.must_move and not (pos==self.last_dropped_pos) and carry_green:
            return self.pick_up(green_wastes[0])

        # ── P4: Flush pending outgoing messages ───────────────────────────
        flush = self._flush_messages()
        if flush is not None:
            return flush

        # ── P5: Deposit yellow waste at z1/z2 boundary ───────────────────
        if (
            len(carried_wastes) == 1
            and carried_wastes[0] is not None
            and carried_wastes[0].waste_type == Color.YELLOW
        ):
            if knowledge.max_x_zone is not None and pos[0] == knowledge.max_x_zone:
                self._queue_drop_notification(pos, carried_wastes[0]) 
                self.carried_since = 0
                return PutDown(carried_wastes[0])
            return self._move_in_direction((1, 0), knowledge)

        # ── P6: Propose exchange if stuck carrying for too long ───────────
        if (
            self.can_communicate
            and carried_wastes
            and self.carried_since > 10
            and not self.wait_answer
            and not self.must_move
        ):
            neighbour = self._find_neighbour_of_color(Color.GREEN)
            if neighbour is not None:
                self.messages_to_send.append(
                    self._prepare_exchange_proposal(
                        carried_wastes[0], neighbour.get_name()
                    )
                )
                self.wait_answer = True
                return self._flush_messages()
            else:
                # No neighbour found: drop and flag to move away
                self.must_move = True
                self.carried_since = 0
                if waste_to_drop :
                    self._queue_drop_notification(pos, waste_to_drop)
                    self.last_dropped_pos = pos
                    return PutDown(waste_to_drop)

        # ── P6b: Handle wait_answer (send msgs instead of idling) ─────────
        if self.wait_answer:
            action = self._handle_wait_answer()
            if action is not None:
                return action
            # No peers — give up waiting and fall through




        # ── P7: Navigate to nearest known green waste ─────────────────────
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        # ── P8: Epsilon broadcast ─────────────────────────────────────────
        broadcast_action = self._try_broadcast()
        if broadcast_action is not None:
            return broadcast_action

        # ── P9: Explore ───────────────────────────────────────────────────
        if self.is_random:
            return self._move_randomly(knowledge)
        return self._discover_randomly(knowledge)


# ══════════════════════════════════════════════════════════════════════════════
#  YellowRobot
# ══════════════════════════════════════════════════════════════════════════════

class YellowRobot(Robot):
    """
    Yellow robot — operates in zones 1 and 2.

    Deliberation priority order:
      P1   Transform 2 yellow → 1 red
      P2   Drop waste because peer accepted exchange
      P3   Pick up yellow waste on current cell
      P4   Flush pending outgoing messages
      P5   Deposit red waste at z2/z3 boundary
      P6   Propose exchange if carrying too long  [can_communicate only]
      P6b  Handle wait_answer
      P7   Navigate to nearest known yellow waste  [has_memory only]
      P8   Epsilon broadcast  [can_communicate only]
      P9   Random walk (is_random) or boundary patrol / exploration
    """

    def __init__(self, model: Model, robot_behavior: RobotBehavior):
        super().__init__(model, Color.YELLOW, robot_behavior)

    def deliberate(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            self._prepare_broadcast_knowledge()
            return self._flush_messages()

        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        current_cell_data = knowledge.cell_data.get(pos, {})

        if carried_wastes:
            self.carried_since += 1
        else:
            self.carried_since = 0
        
        waste_to_drop = next(
                (
                    w
                    for w in carried_wastes
                    if w is not None and w.waste_type == self.color
                ),
                None,
            )

        # ── P1: Transform 2 yellow → 1 red ───────────────────────────────
        if len(carried_wastes) == 2 and all(
            w is not None and w.waste_type == Color.YELLOW for w in carried_wastes
        ):
            return Transform(carried_wastes)

        # ── P2: Drop waste because peer accepted our exchange proposal ────
        if self.drop_object and carried_wastes and waste_to_drop:  
                self.drop_object = False
                self.carried_since = 0
                self.last_dropped_pos = pos
                return PutDown(waste_to_drop) #only drop waste of the same color as the robot

        carry_yellow = True if not carried_wastes or carried_wastes[0].waste_type == Color.YELLOW else False
        # ── P3: Pick up yellow waste on current cell ──────────────────────
        yellow_wastes = current_cell_data.get("wastes", [])
        if yellow_wastes and len(carried_wastes) < 2 and pos != self.last_dropped_pos and carry_yellow:
            return self.pick_up(yellow_wastes[0])

        # ── P4: Flush pending outgoing messages ───────────────────────────
        flush = self._flush_messages()
        if flush is not None:
            return flush

        # ── P5: Deposit red waste at z2/z3 boundary ──────────────────────
        if (
            len(carried_wastes) == 1
            and carried_wastes[0] is not None
            and carried_wastes[0].waste_type == Color.RED
        ):
            if knowledge.max_x_zone is not None and pos[0] == knowledge.max_x_zone:
                self.carried_since = 0
                self._queue_drop_notification(pos, carried_wastes[0]) 
                self.knowledge.must_explore = Robot.EXPLORE_DURATION + 1
                return PutDown(carried_wastes[0])
            return self._move_in_direction((1, 0), knowledge)

        # ── P6: Propose exchange if stuck carrying for too long ───────────
        if (
            self.can_communicate
            and carried_wastes
            and self.carried_since > 10
            and not self.wait_answer
            and not self.must_move
        ):
            neighbour = self._find_neighbour_of_color(Color.YELLOW)
            if neighbour is not None:
                self.messages_to_send.append(
                    self._prepare_exchange_proposal(
                        carried_wastes[0], neighbour.get_name()
                    )
                )
                self.wait_answer = True
                return self._flush_messages()
            else: #emergency drop
                self.must_move = True
                self.carried_since = 0                
                if waste_to_drop:
                    self._queue_drop_notification(pos, waste_to_drop)
                    self.last_dropped_pos = pos
                    return PutDown(waste_to_drop)

        # ── P6b: Handle wait_answer ───────────────────────────────────────
        if self.wait_answer:
            action = self._handle_wait_answer()
            if action is not None:
                return action

        
        # ── P7: Navigate to nearest known yellow waste ────────────────────
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        # ── P8: Epsilon broadcast ─────────────────────────────────────────
        broadcast_action = self._try_broadcast()
        if broadcast_action is not None:
            return broadcast_action

        # ── P9: Boundary patrol or exploration ────────────────────────────
        if self.is_random:
            return self._move_randomly(knowledge)

        # Occasionally reset to random exploration to avoid boundary lock
        if self.random.random() < 1 / Robot.MAX_PATROL_DURATION:
            self.knowledge.must_explore = Robot.EXPLORE_DURATION

        # Move towards z1/z2 boundary to intercept dropped yellow wastes
        if not knowledge.must_explore and knowledge.min_x_zone is None:
            return self._move_in_direction((-1, 0), knowledge)

        if knowledge.must_explore:
            return self._discover_randomly(knowledge, in_area=True)
        # Stay on boundary and patrol vertically
        return self._discover_randomly(knowledge, axis=1)


# ══════════════════════════════════════════════════════════════════════════════
#  RedRobot
# ══════════════════════════════════════════════════════════════════════════════

class RedRobot(Robot):
    """
    Red robot — operates in zones 1, 2 and 3.

    Deliberation priority order:
      P1   Pick up red waste on current cell  (only if hands empty)
      P2   Drop waste because peer accepted exchange
      P3   Flush pending outgoing messages
      P3b  Handle wait_answer
      P4   Find disposal zone if unknown  (move east / explore)
      P5   Deposit at disposal zone if carrying and on it
      P6   Carry red waste towards disposal zone  [has_memory only]
      P6b  Propose exchange if carrying too long  [can_communicate only]
      P7   Navigate to nearest known red waste  [has_memory only]
      P8   Epsilon broadcast  [can_communicate only]
      P9   Random walk (is_random) or boundary patrol / exploration
    """

    def __init__(self, model: Model, robot_behavior: RobotBehavior):
        super().__init__(model, Color.RED, robot_behavior)

    def deliberate(self, knowledge: Knowledge) -> Action:
        if not knowledge.positions:
            self._prepare_broadcast_knowledge()
            return self._flush_messages()

        pos = knowledge.positions[-1]
        carried_wastes = knowledge.carried_wastes[-1]
        current_cell_data = knowledge.cell_data.get(pos, {})
        disposal_pos = knowledge.disposal_pos

        if carried_wastes:
            self.carried_since += 1
        else:
            self.carried_since = 0

        # ── P1: Pick up red waste on current cell (only if hands empty) ───
        red_wastes = current_cell_data.get("wastes", [])
        if red_wastes and not self.carrying:
            return self.pick_up(red_wastes[0])

        # ── P2: Drop waste because peer accepted our exchange proposal ────
        if self.drop_object and carried_wastes:
            waste_to_drop = next(
                (
                    w
                    for w in carried_wastes
                    if w is not None and w.waste_type == self.color
                ),
                None,
            )
            if waste_to_drop is not None:
                self.drop_object = False
                self.carried_since = 0
                self.last_dropped_pos = pos
                return PutDown(waste_to_drop)

        # ── P3: Flush pending outgoing messages ───────────────────────────
        flush = self._flush_messages()
        if flush is not None:
            return flush

        # ── P3b: Handle wait_answer ───────────────────────────────────────
        if self.wait_answer:
            action = self._handle_wait_answer()
            if action is not None:
                return action

        # ── P4: Find disposal zone if unknown ────────────────────────────
        if not self.is_random and disposal_pos is None:
            if (pos[0] + 1, pos[1]) in knowledge.in_grid_cells:
                return self._move_in_direction((1, 0), knowledge)
            return self._discover_randomly(knowledge, axis=1)

        # ── P5: Deposit at disposal zone ─────────────────────────────────
        if carried_wastes and pos == disposal_pos:
            self.carried_since = 0
            self.knowledge.must_explore = Robot.EXPLORE_DURATION + 1
            return PutDown(carried_wastes[0])

        # ── P6: Carry red waste towards disposal zone ─────────────────────
        if carried_wastes and self.has_memory and knowledge.disposal_pos is not None:
            return self._move_towards(knowledge.disposal_pos, knowledge)


        # ── P7: Navigate to nearest known red waste ───────────────────────
        if self.has_memory and knowledge.known_wastes:
            return self._go_to_closest_waste(knowledge)

        # ── P8: Epsilon broadcast ─────────────────────────────────────────
        broadcast_action = self._try_broadcast()
        if broadcast_action is not None:
            return broadcast_action



        # ── P9: Boundary patrol or exploration ────────────────────────────
        if self.is_random:
            return self._move_randomly(knowledge)

        # Occasionally reset to random exploration to avoid boundary lock
        if self.random.random() < 1 / Robot.MAX_PATROL_DURATION:
            self.knowledge.must_explore = Robot.EXPLORE_DURATION

        # Move towards z2/z3 boundary to intercept dropped red wastes
        if not knowledge.must_explore and knowledge.min_x_zone is None:
            return self._move_in_direction((-1, 0), knowledge)


        if knowledge.must_explore:
            return self._discover_randomly(knowledge, in_area=True)
        # Stay on boundary and patrol vertically
        return self._discover_randomly(knowledge, axis=1)

