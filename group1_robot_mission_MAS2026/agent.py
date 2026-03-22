"""
Group 1 - Robot Mission MAS2026
created on 2025-03-16

"""

from mesa import Model, Agent


class greenAgent(Agent):
    
    def __init__(self, name, position):
        self.name = name
        self.position = position
        self.possible_actions = {} #TODO define possible actions for the agent


    def percepts(self, environment):
        #TODO define percepts for the agent based on the environment
        pass

    def do(self, action):
        #TODO define how the agent performs an action
        
        #check if possible : 
        # if an agent is in the tile the agent wants to move to, the agent cannot move there
        # check zone radioactivity
        
        pass

    def deliberate(self, percepts):
        #TODO define how the agent deliberates based on the percepts
        pass

class yellowAgent(Agent):

    def __init__(self) -> None:
        pass

    def percepts(self, environment):
        #TODO define percepts for the agent based on the environment
        pass
    
    def do(self, action):
        #TODO define how the agent performs an action
        pass
    
    def deliberate(self, percepts):
        #TODO define how the agent deliberates based on the percepts
        pass
        

class redAgent(Agent):

    def __init__(self) -> None:
        pass

    def percepts(self, environment):
        #TODO define percepts for the agent based on the environment
        pass

    def do(self, action):
        #TODO define how the agent performs an action
        pass

    def deliberate(self, percepts):
        #TODO define how the agent deliberates based on the percepts
        pass