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

# Completed 4-sided Minefield outcomes
MINE_FIELD_OUTCOMES = {
    "Safe": 0.40,
    "EnergyDrain": 0.30,
    "Disabled": 0.20,
    "Detonation": 0.10
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
        
        self.disabledUnits = {0: 0, 1: 0}

    def perform_action(self, action_type, unit, targetCell, board):
        if self.energy <= 0:
            return 
        
        unitIndex = self.units.index(unit)
        
        if self.disabledUnits.get(unitIndex, 0) > 0:
            self.disabledUnits[unitIndex] -= 1
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
        targetX, targetY = targetCell
        cell = board[targetX][targetY]
        unitIndex = self.units.index(unit)

        # deewar lag gayi
        if cell.type == 'X':
            return 

        if cell.owner != self.name and cell.owner is not None:
            moveIn = self.resolveCombat(targetCell, board, isMoveAction=True)
            if moveIn:
                self.units[unitIndex] = targetCell
        else:
            if cell.type == 'M':
                self.triggerMinefield(unitIndex, targetCell, board)
                if board[targetX][targetY].type == 'X':
                    return 

            if cell.owner is None:
                cell.owner = self.name
                cell.defenseValue = 2 if cell.type == 'F' else 1
            
            self.units[unitIndex] = targetCell

    def fortify(self, unit, targetCell, board):
        targetX, targetY = targetCell
        cell = board[targetX][targetY]
        
        if cell.owner == self.name and cell.defenseValue < 3:
            cell.defenseValue += 1

    def wait(self):
        pass

    def attack(self, unit, targetCell, board):
        targetX, targetY = targetCell
        cell = board[targetX][targetY]
        
        if cell.owner != self.name and cell.owner is not None and cell.type != 'X':
            moveIn = self.resolveCombat(targetCell, board, isMoveAction=False)
            if moveIn:
                unitIndex = self.units.index(unit)
                self.units[unitIndex] = targetCell
                
    def resolveCombat(self, targetCell, board, isMoveAction):
        targetX, targetY = targetCell
        cell = board[targetX][targetY]
        
        faces = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        weights = [0.10, 0.10, 0.15, 0.08, 0.08, 0.12, 0.13, 0.13, 0.11]
        roll = random.choices(faces, weights=weights, k=1)[0]
        
        outcome = None
        for keys, val in COMBAT_OUTCOMES.items():
            if roll in keys:
                outcome = val
                break
        
        moveIn = False
        
        if outcome["type"] == "Fail":
            self.energy -= outcome["energy_loss"]
            
        elif outcome["type"] == "Partial":
            cell.owner = None
            cell.defenseValue = 1 
            if outcome.get("capture") == True: 
                moveIn = True
                
        elif outcome["type"] in ["Full", "Critical"]:
            cell.defenseValue -= outcome["dmg"]
            if cell.defenseValue <= 0:
                cell.owner = self.name
                cell.defenseValue = 2 if cell.type == 'F' else 1
                if isMoveAction: 
                    moveIn = True
            if outcome["type"] == "Critical" and cell.owner == self.name:
                self.score += outcome.get("bonus", 2)
                
        return moveIn

    def triggerMinefield(self, unitIndex, targetCell, board):
        targetX, targetY = targetCell
        cell = board[targetX][targetY]
        
        outcomes = list(MINE_FIELD_OUTCOMES.keys())
        weights = list(MINE_FIELD_OUTCOMES.values())
        roll = random.choices(outcomes, weights=weights, k=1)[0]
        
        if roll == "EnergyDrain":
            self.energy -= 3
        elif roll == "Disabled":
            self.disabledUnits[unitIndex] = 2 # Unit cannot act for 2 turns
        elif roll == "Detonation":
            cell.type = 'X' # Permanently becomes an obstacle
            cell.defenseValue = float('inf')
            cell.owner = None
            self.energy -= 5
    
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



