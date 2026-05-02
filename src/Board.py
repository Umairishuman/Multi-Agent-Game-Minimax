CELL_DEFENSES = {"M": 1, "F": 2, "X": float('inf'), ".": 1}

class Cell:
    def __init__(self, type, owner):
        self.type = type
        self.owner = owner
        self.defenseValue = CELL_DEFENSES[type]


class Board:
    def __init__(self, board, rows, cols):
        self.board = self.parseBoard(board)
        self.rows = rows
        self.cols = cols
        

    def parseBoard(self, board):
        parsedBoard = []
        for row in board:
            parsedRow = []
            for cell in row:
                parsedRow.append(Cell(cell, None))
            parsedBoard.append(parsedRow)
        return parsedBoard
    
    
    def printBoard(self):
        for row in self.board:
            print(''.join([cell.type for cell in row]))
            
    