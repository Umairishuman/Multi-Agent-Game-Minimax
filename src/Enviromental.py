import random
from Agents import ExpertAgent, IntermediateAgent, NoviceAgent
class Environmental:
    def __init__(self):
        self.fortifiedCells = {}
        self.fogofwarapplied = False
        self.reinforcement_turns = 0
        self.reinforcement_agent = None

    def supplyDrop(self, board):
        empty_cells = [(x, y) for x in range(board.rows) for y in range(board.cols) if board[x][y].type == '.']
        if empty_cells:
            cell = random.choice(empty_cells)
            self.fortifiedCells[cell] = 3 
            board[cell[0]][cell[1]].type = 'F'
            board[cell[0]][cell[1]].defenseValue = 2

    def earthquake(self, board):
        # Select any cell owned by any agent (A, B, or C)
        owned_cells = [(x, y) for x in range(board.rows) for y in range(board.cols) 
                       if board[x][y].owner is not None]
        if owned_cells:
            x, y = random.choice(owned_cells)
            board[x][y].defenseValue -= 1
            if board[x][y].defenseValue <= 0:
                board[x][y].type = '.'
                board[x][y].owner = None
                board[x][y].defenseValue = 1

    def reinforcement(self, agents, board):
        target_agent = min(agents, key=lambda a: a.score)
        self.reinforcement_agent = target_agent
        self.reinforcement_turns = 2
        
        placed = False
        adj = [(0,1), (0,-1), (1,0), (-1,0)]
        
        # 1. Check adjacent to existing units
        for unit_pos in target_agent.units:
            for dx, dy in adj:
                nx, ny = unit_pos[0]+dx, unit_pos[1]+dy
                if 0 <= nx < board.rows and 0 <= ny < board.cols and board[nx][ny].type == '.':
                    target_agent.units.append((nx, ny))
                    placed = True; break
            if placed: break
        
        if not placed:
            owned = [(x, y) for x in range(board.rows) for y in range(board.cols) if board[x][y].owner == target_agent.name]
            if owned:
                target_agent.units.append(owned[0])

    def fogOfWar(self, agents):
        for agent in agents:
            agent.radius = agent.radius // 2

    def removeFogOfWar(self, agents):
        for agent in agents:
            agent.resetRadius()

    def applyEnvironmentalEffect(self, board, agents):
        if self.fogofwarapplied:
            self.removeFogOfWar(agents)
            self.fogofwarapplied = False
            
        if self.reinforcement_turns > 0:
            self.reinforcement_turns -= 1
            if self.reinforcement_turns == 0 and self.reinforcement_agent:
                if len(self.reinforcement_agent.units) > 2:
                    self.reinforcement_agent.units.pop() 

        self.checkFortifiedCells(board)
        
        effect = random.choices(['supplyDrop', 'earthquake', 'reinforcement', 'fogOfWar'], k=1)[0]
        if effect == 'supplyDrop': self.supplyDrop(board)
        elif effect == 'earthquake': self.earthquake(board)
        elif effect == 'reinforcement': self.reinforcement(agents, board)
        elif effect == 'fogOfWar':
            self.fogOfWar(agents)
            self.fogofwarapplied = True