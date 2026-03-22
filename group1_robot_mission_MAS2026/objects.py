"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

"""Group 1: Sarah Lamik, Ylias Larbi, Alexandre Faure -- creation date: 16/03/2026"""

from mesa import Agent, Model
from utils import ZONE_TO_RADIO_LEVEL, Color, Zone


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

    def __init__(self, model: Model, waste_type: Color, step_created: int = 0):
    def __init__(self, model: Model, waste_type: Color, step_created: int = 0):
        super().__init__(model)

        self.waste_type = waste_type
        self.step_created = step_created
        self.processed = False
        self.lifespan: int | None = None

    def set_processed(self, step: int):
        """
        Marks the waste as processed and calculates its lifespan.
        """
        self.processed = True
        self.lifespan = step - self.step_created
        self.step_created = step_created
        self.processed = False
        self.lifespan: int | None = None

    def set_processed(self, step: int):
        """
        Marks the waste as processed and calculates its lifespan.
        """
        self.processed = True
        self.lifespan = step - self.step_created

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
