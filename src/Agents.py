import random

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
        self.units = [(x, y), (x, y)] # Every agent starts with 2 units
        self.radius = radius
        self.maxDepth = maxDepth
        self.nodesVisited = 0
        self.nodesPruned = 0
        self.defaultRadius = radius
        self.actions = ["Move", "Fortify", "Wait", "Attack"]

    def handle_combat(self, board, target_pos, attacker_agent, move_onto=False):
        roll = random.randint(1, 9)
        
        pass

    def perform_action(self, action_type, unit_idx, target_pos, board):
        if self.energy <= 0:
            return 
        
        self.energy -= 1 
        
        if action_type == "Move":
            
            pass
        elif action_type == "Fortify":
            cell = board[target_pos]
            if cell.owner == self.name and cell.defenseValue < 3:
                cell.defenseValue += 1
                
    def resetRadius(self):
        self.radius = self.defaultRadius

class ExpertAgent(Agent):
    def __init__(self, energy= 20, maxDepth=7, x=0, y=0, name="Expert", radius=float('inf')):
        super().__init__(energy, maxDepth, x, y, name, radius)


class IntermediateAgent(Agent):
    def __init__(self, energy= 20, maxDepth=5, x=0, y=0, name="Intermediate", radius=5):
        super().__init__(energy, maxDepth, x, y, name, radius)


class NoviceAgent(Agent):
    def __init__(self, energy= 20, maxDepth=3, x=0, y=0, name="Novice", radius=3):
        super().__init__(energy, maxDepth, x, y, name, radius)



