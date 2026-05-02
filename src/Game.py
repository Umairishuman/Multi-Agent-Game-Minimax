from Board import Board
from Agents import ExpertAgent, IntermediateAgent, NoviceAgent
from GUIController import GUI

class Game:
    def __init__(self, path):
        self.rows = 0
        self.cols = 0
        self.rounds = 0
        self.board = None
        self.agents = [ExpertAgent(), IntermediateAgent(), NoviceAgent()]
        
        self.parseInput(path)
        # self.printState()
    
    def parseInput(self, path):
        with open(path, 'r') as f:
            data = f.read()
        
        data = data.split('\n')
        self.rows, self.cols, self.rounds = map(int, data[0].split(' '))
        self.board = Board(data[1:1+self.rows], self.rows, self.cols)
        data = data[1+self.rows:]
        for i, row in enumerate(data):
            x, y = map(int, row.split(' '))
            self.agents[i].x = x
            self.agents[i].y = y
        
    
    def printState(self):
        print(f"Round: {self.rounds}")
        self.board.printBoard()
        for agent in self.agents:
            print(agent)
        

    def play(self):
        print("playing")