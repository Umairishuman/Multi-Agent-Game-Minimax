class Agent:
    def __init__(self, energy, maxDepth, x, y, name, radius):
        self.score = 0
        self.energy = energy
        self.nodesVisited = 0
        self.nodesPruned = 0
        self.maxDepth = maxDepth
        self.name = name
        self.x = x
        self.y = y
        self.radius = radius
    
    def __str__(self):
        return f"{self.name} (Energy: {self.energy}, Score: {self.score}, Nodes Visited: {self.nodesVisited}, Nodes Pruned: {self.nodesPruned})"


class ExpertAgent(Agent):
    def __init__(self, energy= 20, maxDepth=7, x=0, y=0, name="Expert", radius=float('inf')):
        super().__init__(energy, maxDepth, x, y, name, radius)


class IntermediateAgent(Agent):
    def __init__(self, energy= 20, maxDepth=5, x=0, y=0, name="Intermediate", radius=5):
        super().__init__(energy, maxDepth, x, y, name, radius)


class NoviceAgent(Agent):
    def __init__(self, energy= 20, maxDepth=3, x=0, y=0, name="Novice", radius=3):
        super().__init__(energy, maxDepth, x, y, name, radius)



