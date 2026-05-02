from Board import Board

class Game:
    def __init__(self, path):
        self.board = Board(path)
    
    def play(self):
        print("playing")