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
            tokens = row.split() if ' ' in row else list(row)
            for cell in tokens:
                parsedRow.append(Cell(cell, None))
            parsedBoard.append(parsedRow)
        return parsedBoard
    
    
    def printBoard(self):
        # change color to blue, red, green for Expert, Intermediate, Novice respectively
        for row in self.board:
            for cell in row:
                if cell.owner == 'Expert':
                    print(f"\033[94m{cell.type}\033[0m", end=' ')
                elif cell.owner == 'Intermediate':
                    print(f"\033[91m{cell.type}\033[0m", end=' ')
                elif cell.owner == 'Novice':
                    print(f"\033[92m{cell.type}\033[0m", end=' ')
                else:
                    print(cell.type, end=' ')
            print()
    
    def __getitem__(self, key):
        # Support board[x] -> row and board[x, y] -> cell
        if isinstance(key, tuple):
            x, y = key
            return self.board[x][y]
        return self.board[key]

    def __setitem__(self, key, value):
        # Support setting via board[x] = row or board[x, y] = cell
        if isinstance(key, tuple):
            x, y = key
            self.board[x][y] = value
            return
        self.board[key] = value