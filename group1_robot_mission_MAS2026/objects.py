from mesa import Agent, Model
from utils import ZONE_TO_RADIO_LEVEL, Action, ActionType, Color, Zone


class Radioactivity(Agent):
    """Agent representing the radioactivity of a cell"""

    def __init__(self, model: Model, zone: Zone):
        super().__init__(model)

        self.zone = zone
        self.radioactivity_level = ZONE_TO_RADIO_LEVEL[zone]
        self.radioactivity = (self.radioactivity_level.value + self.random.random()) / 3

    def get_name(self):
        return f"Radioactivity_{self.unique_id}"


class WasteDisposalZone(Agent):
    """Agent representing that a cell is a waste disposal zone."""
    def get_name(self):
        return f"WasteDisposalZone_{self.unique_id}"

class Waste(Agent):
    """Agent representing a waste."""

    def __init__(self, model: Model, waste_type: Color):
        super().__init__(model)

        self.waste_type = waste_type

    def get_name(self):
        return f"Waste_{self.unique_id}"

### Actions related to objects
class PickUp(Action):
    def __init__(self, waste: Waste):
        super().__init__(ActionType.PICK_UP)
        self.waste = waste


class PutDown(Action):
    def __init__(self, waste: Waste):
        super().__init__(ActionType.PUT_DOWN)
        self.waste = waste


class Transform(Action):
    def __init__(self, wastes: list[Waste]):
        super().__init__(ActionType.TRANSFORM)
        self.wastes = wastes
