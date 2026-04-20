"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from enum import Enum


class Zone(Enum):
    Z1 = 1
    Z2 = 2
    Z3 = 3


class RadioactivityLevel(Enum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


class Color(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


ZONE_TO_RADIO_LEVEL = {
    Zone.Z1: RadioactivityLevel.LOW,
    Zone.Z2: RadioactivityLevel.MEDIUM,
    Zone.Z3: RadioactivityLevel.HIGH,
}

COLORS = [Color.GREEN, Color.YELLOW, Color.RED]

COLOR_TO_ZONE = {
    Color.GREEN: Zone.Z1,
    Color.YELLOW: Zone.Z2,
    Color.RED: Zone.Z3,
}


class RobotBehavior(Enum):
    RANDOM = "random"
    MEMORY = "memory"
    COMMUNICATION = "communication"

    @staticmethod
    def from_string(s: str) -> "RobotBehavior":
        s = s.lower()
        if s == "random" or s == "aléatoire":
            return RobotBehavior.RANDOM
        elif s == "memory" or s == "mémoire":
            return RobotBehavior.MEMORY
        elif s == "communication":
            return RobotBehavior.COMMUNICATION
        else:
            raise ValueError(f"Unknown behavior: {s}")


class ActionType(Enum):
    WAIT = "wait"
    MOVE = "move"
    PICK_UP = "pick_up"
    PUT_DOWN = "put_down"
    TRANSFORM = "transform"
    SEND_MESSAGES = "send_messages"


class Action:
    """Class representing an action to be executed by a robot."""

    def __init__(self, action_type: ActionType):
        self.action_type = action_type


class Move(Action):
    def __init__(
        self,
        direction: tuple[int, int] | None = None,
        position: tuple[int, int] | None = None,
    ):
        super().__init__(ActionType.MOVE)
        assert (direction is not None) ^ (
            position is not None
        ), "Either direction or position must be provided, but not both."

        self.direction = direction
        self.position = position


class Wait(Action):
    def __init__(self):
        super().__init__(ActionType.WAIT)


class PickUp(Action):
    def __init__(self, waste):
        super().__init__(ActionType.PICK_UP)
        self.waste = waste


class PutDown(Action):
    def __init__(self, waste):
        super().__init__(ActionType.PUT_DOWN)
        self.waste = waste


class Transform(Action):
    def __init__(self, wastes: list):
        super().__init__(ActionType.TRANSFORM)
        self.wastes = wastes



class SendMessages(Action):
    def __init__(self, messages: list):
        super().__init__(ActionType.SEND_MESSAGES)
        self.messages = messages