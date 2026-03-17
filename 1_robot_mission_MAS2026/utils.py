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

COLOR_TO_ZONE = {
    Color.GREEN: Zone.Z1,
    Color.YELLOW: Zone.Z2,
    Color.RED: Zone.Z3,
}


class ActionType(Enum):
    MOVE = "move"
    PICK_UP = "pick_up"
    PUT_DOWN = "put_down"
    TRANSFORM = "transform"


class Action:
    """Class representing an action to be executed by a robot."""

    def __init__(self, action_type: ActionType):
        self.action_type = action_type


class Move(Action):
    def __init__(self, direction: tuple[int, int]):
        super().__init__(ActionType.MOVE)
        self.direction = direction
