CELL_DEFENSES = {"M": 1, "F": 2, "X": float('inf'), ".": 1}

class Cell:
    def __init__(self, type, owner):
        self.type = type
        self.owner = owner
        self.defenseValue = CELL_DEFENSES[type]


class Board:
    def __init__(self, filepath):
        self.parseBoard(filepath)
    def parseBoard(self, filepath):
        with open(filepath) as f:
            data = f.read()
        
        print(data)

    
    