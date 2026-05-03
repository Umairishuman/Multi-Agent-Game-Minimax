import random

class Environmental:
    def __init__(self):
        self.fortifiedCells = {}
        self.fogofwarapplided = False
    
    
    
    

# Supply Drop: A randomly selected empty cell becomes a Fortress (defense value 2) for 3 rounds, after which it
# reverts to Empty.
# Earthquake: One randomly selected owned cell (any agent) has its defense value reduced by 1. If the defense value
# reaches 0, the cell reverts to Empty.
# Reinforcement: The agent with the lowest current score gains one extra unit for 2 turns. The extra unit is placed on
# any empty cell adjacent to that agent's existing unit (or starting position if no unit is on the board). If no adjacent
# empty cell exists, the extra unit is placed on the agent's nearest owned cell.
# Fog of War: For this turn only, each agent's observable range is halved (rounded down). Agents cannot search cells
# outside their range
    
    def supplyDrop(self, board):
        
            empty_cells = [(x, y) for x in range(board.rows) for y in range(board.cols) if board[x][y].type == '.']
            if empty_cells:
                cell = random.choice(empty_cells)
                self.fortifiedCells[cell] = 3  # Fortress lasts for 3 rounds
                board[cell[0]][cell[1]].type = 'F'
                
    def earthquake(self, board):
        
        pass
    def reinforcement(self, agents):
        pass
    def fogOfWar(self, agents):
        pass
    
    def removeFogOfWar(self, agents):
        pass
    def checkFortifiedCells(self, board):
        for cell, rounds in list(self.fortifiedCells.items()):
            if rounds > 1:
                self.fortifiedCells[cell] = rounds - 1
            else:
                del self.fortifiedCells[cell]
                board[cell[0]][cell[1]].type = '.'

    def applyEnvironmentalEffect(self, board, agents):
        #0.25 chance for supply drop, 0.25 chance for earthquake, 0.25 chance for reinforcement, 0.25 chance for fog of war
        # if previous turn had for of war then remove it before applying new effect
        if self.fogofwarapplided:
            self.removeFogOfWar(agents)
            self.fogofwarapplided = False
        if len(self.fortifiedCells) > 0:
            self.checkFortifiedCells(board)
        
        effect = random.choices(['supplyDrop', 'earthquake', 'reinforcement', 'fogOfWar'], k=1)[0]
        if effect == 'supplyDrop':
            self.supplyDrop(board)
        elif effect == 'earthquake':
            self.earthquake(board)
        elif effect == 'reinforcement':
            self.reinforcement(agents)
        elif effect == 'fogOfWar':
            self.fogOfWar(agents)
            self.fogofwarapplided = True

    