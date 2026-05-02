CELL_DEFENSES = {"M": 1, "F": 2, "X": float('inf'), ".": 1}

class Cell:
    def __init__(self, type, owner, defenseValue):
        self.type = type
        self.owner = owner
        self.defenseValue = defenseValue


class Board:
    pass
    
    