import math
from Agents import ExpertAgent, NoviceAgent
class Minimax:
    def __init__(self, maximizingAgent, allAgents):
        self.maxAgent = maximizingAgent
        self.allAgents = allAgents
        
        # Capability Asymmetry Flags
        self.useTT = isinstance(maximizingAgent, ExpertAgent) 
        self.isNovice = isinstance(maximizingAgent, NoviceAgent)

    def getBestMove(self, board):
        bestVal = -math.inf
        bestMove = (None, None, None) # (action, unit, target)
        
        # Reset tracking for the Per-Move Node Report
        self.maxAgent.nodesVisited = 0
        self.maxAgent.nodesPruned = 0
        
        # Generate root moves for the maximizing agent
        validMoves = self.generateAllAgentMoves(self.maxAgent, board)
        
        for action, unit, target in validMoves:
            # TODO: Clone the board state here so we don't ruin the actual game board!
            # simulatedBoard, simulatedAgents = self.cloneState(board, self.allAgents)
            
            # Apply the move to the simulated board
            # ...
            
            # Call Expectiminimax for the next depth
            val = self.expectiminimax(board, depth=self.maxAgent.maxDepth - 1, 
                                      alpha=-math.inf, beta=math.inf, 
                                      isMax=False, currentAgentIdx=1)
            
            if val > bestVal:
                bestVal = val
                bestMove = (action, unit, target)
                
        return bestMove

    def expectiminimax(self, board, depth, alpha, beta, isMax, currentAgentIdx):
        self.maxAgent.nodesVisited += 1
        
        # Base Case: Depth limit reached or game over
        if depth == 0 or self.isGameOver(board):
            return self.maxAgent.evaluate(board, self.allAgents)
            
        currentAgent = self.allAgents[currentAgentIdx]
        
        # 1. CHANCE NODE LOGIC (Stochastic outcomes)[cite: 1]
        if self.isChanceNode(): 
            return self.evaluateChanceNode(board, depth, alpha, beta, currentAgentIdx)
            
        # 2. MAX NODE LOGIC
        if isMax:
            maxEval = -math.inf
            for move in self.generateAllAgentMoves(currentAgent, board):
                # TODO: Simulate move on copied board
                evalVal = self.expectiminimax(board, depth - 1, alpha, beta, False, (currentAgentIdx + 1) % len(self.allAgents))
                maxEval = max(maxEval, evalVal)
                alpha = max(alpha, evalVal)
                if beta <= alpha:
                    self.maxAgent.nodesPruned += 1 # Alpha-Beta Pruning[cite: 1]
                    break
            return maxEval
            
        # 3. MIN NODE LOGIC (Opponents)
        else:
            minEval = math.inf
            for move in self.generateAllAgentMoves(currentAgent, board):
                # TODO: Simulate move on copied board
                # Next agent; if we cycle back to the maxAgent, the next node is MAX
                nextIdx = (currentAgentIdx + 1) % len(self.allAgents)
                nextIsMax = (nextIdx == self.allAgents.index(self.maxAgent))
                
                evalVal = self.expectiminimax(board, depth - 1, alpha, beta, nextIsMax, nextIdx)
                minEval = min(minEval, evalVal)
                beta = min(beta, evalVal)
                if beta <= alpha:
                    self.maxAgent.nodesPruned += 1 # Alpha-Beta Pruning[cite: 1]
                    break
            return minEval

    def evaluateChanceNode(self, board, depth, alpha, beta, currentAgentIdx):
        """Evaluates probabilistic branches[cite: 1]"""
        expectedUtility = 0
        
        # Novice agent only looks at Top-2 probabilities (Faces 7,8 and Face 6)[cite: 1]
        if self.isNovice:
            # Probabilities need to be normalized so they sum to 1.0 for the expected utility calculation
            outcomes = [0.26, 0.12] # (Full Success, Partial+Advance)
            # Simulate only these branches...
        else:
            # Expert/Intermediate look at all 9 outcomes
            pass
            
        return expectedUtility

    def generateAllAgentMoves(self, agent, board):
        """Returns a list of tuples: (action, unit, targetCell)"""
        moves = []
        for unit in agent.units:
            validTargets = agent.generateValidMoves(unit, board)
            for target in validTargets:
                validActions = agent.generateValidActions(unit, target, board)
                for action in validActions:
                    moves.append((action, unit, target))
        return moves
        
    def isGameOver(self, board):
        # TODO: Implement check for 60% board control or no active units in simulation
        return False
        
    def isChanceNode(self):
        # TODO: Implement logic to determine if the next node requires a die roll
        return False