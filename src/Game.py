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
        self.environment = Environmental()
        self.parseInput(path)
        self.agents = [ExpertAgent(board=self.board), IntermediateAgent(board=self.board), NoviceAgent(board=self.board)]
        
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
        print(f"Round: {self.currentRound + 1}/{self.rounds}")
        self.board.printBoard()
        for agent in self.agents:
            print(agent)
        

    def play(self):
        
        total_cells = self.rows * self.cols
        obstacle_cells = sum(1 for x in range(self.rows) for y in range(self.cols) if self.board[x][y].type == 'X')
        non_obstacle_cells = total_cells - obstacle_cells
        cells_to_win = 0.60 * non_obstacle_cells

        while self.currentRound < self.rounds:
            print("=============================================================================")
            print(f"Round {self.currentRound + 1} begins!")
            
            self.environment.applyEnvironmentalEffect(self.board, self.agents)
            
            for agent in self.agents:
                if agent.energy <= 0 and len(agent.units) == 0:
                    continue

                opponents_alive_before = sum(1 for a in self.agents if a != agent and (a.energy > 0 or len(a.units) > 0))

                agent.playMove(self.board, self.agents)
                
                opponents_alive_after = sum(1 for a in self.agents if a != agent and (a.energy > 0 or len(a.units) > 0))
                eliminated_count = opponents_alive_before - opponents_alive_after
                
                for _ in range(eliminated_count):
                    agent.awardEliminationBonus()

                owned_cells = sum(1 for x in range(self.rows) for y in range(self.cols) if self.board[x][y].owner == agent.name)
                if owned_cells > cells_to_win:
                    print(f"\n{agent.name} controls more than 60% of the territory! Instant Win!")
                    self.endGame()
                    return 

            for agent in self.agents:
                if len(agent.units) > 0 or agent.energy > 0:
                    agent.updateScore(self.board)
                
            self.printState()
            self.currentRound += 1
            
        self.endGame()

    def endGame(self):
        """Handles the game termination and determines the winner."""
        print("=============================================================================")
        print("Game Over!")
        
        # Determine the winner based on the highest score[cite: 1]
        winner = max(self.agents, key=lambda a: a.score)
        
        print(f"\nWinner: {winner.name} with {winner.score} points!")
        print("-" * 20)
        for agent in self.agents:
            print(f"{agent.name} final score: {agent.score} | Remaining Energy: {agent.energy}")