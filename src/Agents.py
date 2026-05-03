import random
from Minimax import Minimax
from Board import Board
# 9-sided die mapping
COMBAT_OUTCOMES = {
    (1, 2): {"prob": 0.10, "type": "Fail", "energy_loss": 1},
    (3,): {"prob": 0.15, "type": "Fail", "energy_loss": 0},
    (4, 5): {"prob": 0.08, "type": "Partial", "capture": False, "reset": True},
    (6,): {"prob": 0.12, "type": "Partial", "capture": True, "reset": True},
    (7, 8): {"prob": 0.13, "type": "Full", "dmg": 1},
    (9,): {"prob": 0.11, "type": "Critical", "dmg": 1, "bonus": 2}
}

class Agent:
    def __init__(self, energy, maxDepth, x, y, name, radius):
        self.score = 0
        self.energy = energy
        self.name = name
        self.units = [(x, y), (x, y)] 
        self.radius = radius
        self.maxDepth = maxDepth
        self.nodesVisited = 0
        self.nodesPruned = 0
        self.defaultRadius = radius
        self.actions = ["Move", "Fortify", "Wait", "Attack"]
        
    

    def perform_action(self, action_type, unit, targetCell, board):
        if self.energy <= 0:
            return 
        
        self.energy -= 1 
        
        if action_type == "Move":
            self.move(unit, targetCell, board)
        elif action_type == "Fortify":
            self.fortify(unit, targetCell, board)
        elif action_type == "Wait":
            self.wait()
        elif action_type == "Attack":
            self.attack(unit, targetCell, board)

    def resetRadius(self):
        self.radius = self.defaultRadius
    
    
    def move(self, unit, targetCell, board):
        pass
    def fortify(self, unit, targetCell, board):
        pass
    def wait(self):
        self.energy -= 1
    def attack(self, unit, targetCell, board):
        pass
    
    
    def playMove(self, board):
        # minimax = Minimax(self, board)
        print("Agent is thinking...")
        print("Agent has made a move!")

class ExpertAgent(Agent):
    def __init__(self, energy= 20, maxDepth=7, x=0, y=0, name="Expert", radius=float('inf')):
        super().__init__(energy, maxDepth, x, y, name, radius)


class IntermediateAgent(Agent):
    def __init__(self, energy= 20, maxDepth=5, x=0, y=0, name="Intermediate", radius=5):
        super().__init__(energy, maxDepth, x, y, name, radius)


class NoviceAgent(Agent):
    def __init__(self, energy= 20, maxDepth=3, x=0, y=0, name="Novice", radius=3):
        super().__init__(energy, maxDepth, x, y, name, radius)



