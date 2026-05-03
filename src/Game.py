from Board import Board
from Agents import ExpertAgent, IntermediateAgent, NoviceAgent
from GUIController import GUI
from Enviromental import Environmental
from Minimax import Minimax
class Game:
    def __init__(self, path):
        self.rows = 0
        self.cols = 0
        self.rounds = 0
        self.currentRound = 0
        self.board = None
        self.agents = [ExpertAgent(), IntermediateAgent(), NoviceAgent()]
        self.environment = Environmental()
        self.parseInput(path)
        # self.printState()
        
        self.turn = 0
    
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
        print(f"Round: {self.currentRound}/{self.rounds}")
        self.board.printBoard()
        for agent in self.agents:
            print(agent)
        

    def play(self):
        # gui = GUI(self.board, self.agents, self.environment)
        # gui.start()
        
        while self.currentRound < self.rounds:
            for agent in self.agents:
                self.environment.applyEnvironmentalEffect(self.board, self.agents)
        
        