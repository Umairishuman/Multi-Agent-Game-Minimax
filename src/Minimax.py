"""
Minimax.py — Expectiminimax with Alpha-Beta Pruning

Architecture
------------
The tree has three kinds of nodes:

  MAX node   → the agent we're optimising for is choosing
  MIN node   → an opponent is choosing (adversarial)
  CHANCE node→ a stochastic action (Attack / Move-into-enemy / Minefield)
               is about to resolve; we branch over each die-face outcome
               and weight the child values by probability

Capability asymmetry
--------------------
  ExpertAgent       depth=7, uses Transposition Table, sees all 9 die outcomes
  IntermediateAgent depth=5, no TT,                   sees all 9 die outcomes
  NoviceAgent       depth=3, no TT, only considers top-2 outcomes (Full + Critical)

Board cloning
-------------
We deep-copy the board + agent states before every simulated move so the
real game state is never touched during search.
"""

import math
from Board import Board, Cell

# ---------------------------------------------------------------------------
# Probability table for the 9-sided combat die (mirrors Agents.py)
# ---------------------------------------------------------------------------
# Each entry: {"prob": float, "type": str, ...extra params}
COMBAT_OUTCOMES = [
    {"prob": 0.20, "type": "Fail",     "energy_loss": 1},   # faces 1-2
    {"prob": 0.15, "type": "Fail",     "energy_loss": 0},   # face  3
    {"prob": 0.16, "type": "Partial",  "capture": False},   # faces 4-5
    {"prob": 0.12, "type": "Partial",  "capture": True},    # face  6
    {"prob": 0.26, "type": "Full",     "dmg": 1},           # faces 7-8
    {"prob": 0.11, "type": "Critical", "dmg": 1, "bonus": 2},# face 9
]

# Novice only considers Full + Critical, normalised so probabilities sum to 1
_novice_raw   = [o for o in COMBAT_OUTCOMES if o["type"] in ("Full", "Critical")]
_novice_total = sum(o["prob"] for o in _novice_raw)
NOVICE_OUTCOMES = [{**o, "prob": o["prob"] / _novice_total} for o in _novice_raw]

# Minefield outcomes (used when a unit moves onto an 'M' cell)
MINE_OUTCOMES = [
    {"prob": 0.40, "type": "Safe"},
    {"prob": 0.30, "type": "EnergyDrain"},
    {"prob": 0.20, "type": "Disabled"},
    {"prob": 0.10, "type": "Detonation"},
]

# ---------------------------------------------------------------------------
# Lightweight state-cloning helpers
# ---------------------------------------------------------------------------

def _clone_cell(cell):
    c = Cell(cell.type, cell.owner)
    c.defenseValue = cell.defenseValue
    return c


def _clone_board(board: Board) -> Board:
    """Return an independent copy of the Board (cells only)."""
    nb        = Board.__new__(Board)   # skip __init__ — no re-parsing needed
    nb.rows   = board.rows
    nb.cols   = board.cols
    nb.board  = [
        [_clone_cell(board[r][c]) for c in range(board.cols)]
        for r in range(board.rows)
    ]
    return nb


def _clone_agent(agent):
    """Shallow-clone just the fields the search tree cares about."""
    a = object.__new__(type(agent))    # skip __init__ — no board side-effects
    a.name          = agent.name
    a.score         = agent.score
    a.energy        = agent.energy
    a.radius        = agent.radius
    a.defaultRadius = agent.defaultRadius
    a.maxDepth      = agent.maxDepth
    a.units         = list(agent.units)
    a.disabledUnits = dict(agent.disabledUnits)
    a.actions       = list(agent.actions)
    a.nodesVisited  = agent.nodesVisited
    a.nodesPruned   = agent.nodesPruned
    # ExpertAgent transposition table — share the reference (reads are fine)
    if hasattr(agent, "transpositionTable"):
        a.transpositionTable = agent.transpositionTable
    return a


def clone_state(board: Board, agents: list):
    """Return (new_board, new_agents) as fully independent copies."""
    return _clone_board(board), [_clone_agent(a) for a in agents]


# ---------------------------------------------------------------------------
# Stochasticity classifier
# ---------------------------------------------------------------------------

def _is_stochastic(action: str, unit, target, board: Board) -> bool:
    """
    True when the move outcome is determined by a die roll:
      • Any Attack on an occupied cell
      • Move into an enemy-owned cell (combat)
      • Move into a Minefield cell ('M')
    """
    tx, ty = target
    cell   = board[tx][ty]
    if action == "Attack":
        return cell.owner is not None and cell.type != "X"
    if action == "Move":
        if cell.owner is not None:   # enemy occupant → combat
            return True
        if cell.type == "M":         # minefield → random outcome
            return True
    return False


# ---------------------------------------------------------------------------
# Deterministic move applicator
# ---------------------------------------------------------------------------

def _apply_move(action: str, unit, target, agent, board: Board):
    """
    Apply a *deterministic* action to (agent, board) in-place.
    Stochastic moves (Attack into enemy, Move into M) are handled
    separately via _apply_combat_outcome / _apply_mine_outcome.
    """
    if agent.energy <= 0:
        return

    unit_idx = agent.units.index(unit) if unit in agent.units else 0
    if agent.disabledUnits.get(unit_idx, 0) > 0:
        agent.disabledUnits[unit_idx] -= 1
        return

    agent.energy -= 1
    tx, ty = target
    cell   = board[tx][ty]

    if action == "Wait":
        return

    if action == "Fortify":
        if cell.owner == agent.name and cell.defenseValue < 3:
            cell.defenseValue += 1
        return

    if action == "Move":
        # Only the deterministic sub-case: unowned / friendly cell
        if cell.owner is None or cell.owner == agent.name:
            if cell.owner is None:
                cell.owner        = agent.name
                cell.defenseValue = 2 if cell.type == "F" else 1
            agent.units[unit_idx] = target
        return


# ---------------------------------------------------------------------------
# Stochastic outcome applicators
# ---------------------------------------------------------------------------

def _apply_combat_outcome(outcome: dict, unit, target, agent, board: Board):
    """Apply one sampled combat die outcome to (agent, board)."""
    tx, ty   = target
    cell     = board[tx][ty]
    unit_idx = agent.units.index(unit) if unit in agent.units else 0
    otype    = outcome["type"]

    if otype == "Fail":
        agent.energy -= outcome.get("energy_loss", 0)

    elif otype == "Partial":
        cell.owner        = None
        cell.defenseValue = 1
        if outcome.get("capture"):
            agent.units[unit_idx] = target
            cell.owner = agent.name

    elif otype in ("Full", "Critical"):
        cell.defenseValue -= outcome.get("dmg", 1)
        if cell.defenseValue <= 0:
            cell.owner        = agent.name
            cell.defenseValue = 2 if cell.type == "F" else 1
            agent.units[unit_idx] = target
        if otype == "Critical" and cell.owner == agent.name:
            agent.score += outcome.get("bonus", 2)


def _apply_mine_outcome(outcome: dict, unit, target, agent, board: Board):
    """Apply one sampled minefield outcome to (agent, board)."""
    tx, ty   = target
    cell     = board[tx][ty]
    unit_idx = agent.units.index(unit) if unit in agent.units else 0
    otype    = outcome["type"]

    if otype == "Safe":
        cell.owner = agent.name
        cell.defenseValue = 1
        agent.units[unit_idx] = target

    elif otype == "EnergyDrain":
        agent.energy -= 3
        cell.owner = agent.name
        agent.units[unit_idx] = target

    elif otype == "Disabled":
        agent.disabledUnits[unit_idx] = 2

    elif otype == "Detonation":
        cell.type         = "X"
        cell.defenseValue = float("inf")
        cell.owner        = None
        agent.energy     -= 5


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class Minimax:
    def __init__(self, maximizingAgent, allAgents):
        self.maxAgent  = maximizingAgent
        self.allAgents = allAgents

        # Capability asymmetry flags
        self.useTT    = hasattr(maximizingAgent, "transpositionTable")
        self.isNovice = type(maximizingAgent).__name__ == "NoviceAgent"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def getBestMove(self, board):
        """
        Search the game tree and return the best (action, unit, target).
        Falls back to ('Wait', first_unit, first_unit) if no moves exist.
        """
        self.maxAgent.nodesVisited = 0
        self.maxAgent.nodesPruned  = 0
        # Clear stale TT entries from previous turns (Expert only)
        if self.useTT:
            self.maxAgent.transpositionTable.clear()

        root_moves = self.generateAllAgentMoves(self.maxAgent, board)
        if not root_moves:
            unit = self.maxAgent.units[0] if self.maxAgent.units else (0, 0)
            return ("Wait", unit, unit)

        best_val  = -math.inf
        best_move = root_moves[0][:3]  # safe default

        for action, unit, target in root_moves:
            sim_board, sim_agents = clone_state(board, self.allAgents)
            sim_me = next(a for a in sim_agents if a.name == self.maxAgent.name)

            if _is_stochastic(action, unit, target, sim_board):
                val = self._expected_value(
                    action, unit, target, sim_me,
                    sim_board, sim_agents,
                    depth       = self.maxAgent.maxDepth - 1,
                    alpha       = -math.inf,
                    beta        =  math.inf,
                    next_is_max = False,
                    next_idx    = 1,
                )
            else:
                _apply_move(action, unit, target, sim_me, sim_board)
                val = self.expectiminimax(
                    sim_board, sim_agents,
                    depth       = self.maxAgent.maxDepth - 1,
                    alpha       = -math.inf,
                    beta        =  math.inf,
                    isMax       = False,
                    curAgentIdx = 1,
                )

            if val > best_val:
                best_val  = val
                best_move = (action, unit, target)

        print(
            f"  [{self.maxAgent.name}] nodes visited={self.maxAgent.nodesVisited}, "
            f"pruned={self.maxAgent.nodesPruned}, bestVal={best_val:.2f}"
        )
        return best_move

    # ------------------------------------------------------------------
    # Core recursive search
    # ------------------------------------------------------------------

    def expectiminimax(self, board, agents, depth, alpha, beta, isMax, curAgentIdx):
        """
        Expectiminimax with Alpha-Beta pruning on deterministic nodes.

        Pruning is applied only at MAX and MIN nodes — never across the
        branches of a CHANCE node, because all branches contribute to the
        expected value and skipping any would corrupt the calculation.
        """
        self.maxAgent.nodesVisited += 1

        # ---- Leaf / terminal ----------------------------------------
        if depth == 0 or self._is_terminal(board, agents):
            me = next((a for a in agents if a.name == self.maxAgent.name), agents[0])
            return me.evaluate(board, agents)

        # ---- Transposition table (Expert only) ----------------------
        tt_key = None
        if self.useTT:
            tt_key = self._tt_key(board, agents, depth, isMax, curAgentIdx)
            if tt_key in self.maxAgent.transpositionTable:
                return self.maxAgent.transpositionTable[tt_key]

        cur_agent = agents[curAgentIdx]
        moves     = self.generateAllAgentMoves(cur_agent, board)
        next_idx    = (curAgentIdx + 1) % len(agents)
        next_is_max = (next_idx == self._max_idx(agents))

        if not moves:
            # Agent skips turn
            result = self.expectiminimax(
                board, agents, depth - 1, alpha, beta, next_is_max, next_idx
            )
            if self.useTT and tt_key is not None:
                self.maxAgent.transpositionTable[tt_key] = result
            return result

        result = -math.inf if isMax else math.inf

        for action, unit, target in moves:
            sim_board, sim_agents = clone_state(board, agents)
            sim_cur = sim_agents[curAgentIdx]

            if _is_stochastic(action, unit, target, sim_board):
                # ---- CHANCE node ------------------------------------
                # No pruning across probability branches
                child_val = self._expected_value(
                    action, unit, target, sim_cur,
                    sim_board, sim_agents,
                    depth - 1, alpha, beta, next_is_max, next_idx,
                )
            else:
                # ---- Deterministic MAX / MIN node -------------------
                _apply_move(action, unit, target, sim_cur, sim_board)
                child_val = self.expectiminimax(
                    sim_board, sim_agents,
                    depth - 1, alpha, beta, next_is_max, next_idx,
                )

            if isMax:
                if child_val > result:
                    result = child_val
                alpha = max(alpha, result)
            else:
                if child_val < result:
                    result = child_val
                beta = min(beta, result)

            if beta <= alpha:
                self.maxAgent.nodesPruned += 1
                break   # Alpha-Beta cut

        if self.useTT and tt_key is not None:
            self.maxAgent.transpositionTable[tt_key] = result

        return result

    # ------------------------------------------------------------------
    # Chance-node expected-value computation
    # ------------------------------------------------------------------

    def _expected_value(self, action, unit, target, agent,
                        board, agents, depth, alpha, beta,
                        next_is_max, next_idx):
        """
        Compute E[value] over all stochastic outcomes for one move.
        Decides whether this is a combat roll or a minefield roll.
        """
        tx, ty = target
        cell   = board[tx][ty]

        # Choose the correct outcome table
        if action == "Move" and cell.type == "M" and cell.owner is None:
            outcomes   = MINE_OUTCOMES
            apply_fn   = _apply_mine_outcome
        else:
            outcomes   = NOVICE_OUTCOMES if self.isNovice else COMBAT_OUTCOMES
            apply_fn   = _apply_combat_outcome

        expected = 0.0
        for outcome in outcomes:
            sim_board2, sim_agents2 = clone_state(board, agents)
            sim_agent2 = next(a for a in sim_agents2 if a.name == agent.name)

            apply_fn(outcome, unit, target, sim_agent2, sim_board2)

            val = self.expectiminimax(
                sim_board2, sim_agents2,
                depth, alpha, beta, next_is_max, next_idx,
            )
            expected += outcome["prob"] * val

        return expected

    # ------------------------------------------------------------------
    # Move generator
    # ------------------------------------------------------------------

    def generateAllAgentMoves(self, agent, board):
        """
        Returns a list of (action, unit, targetCell) triples.
        Respects disabled units and the agent's vision radius.
        """
        moves = []
        for unit in agent.units:
            ux, uy   = unit
            unit_idx = agent.units.index(unit)

            if agent.disabledUnits.get(unit_idx, 0) > 0:
                moves.append(("Wait", unit, unit))
                continue

            targets = agent.generateValidMoves(unit, board)

            # Apply radius constraint (Manhattan distance)
            if agent.radius != float("inf"):
                targets = [
                    t for t in targets
                    if abs(t[0] - ux) + abs(t[1] - uy) <= agent.radius
                ]

            for target in targets:
                for action in agent.generateValidActions(unit, target, board):
                    moves.append((action, unit, target))

        if not moves:
            unit = agent.units[0] if agent.units else (0, 0)
            moves.append(("Wait", unit, unit))

        return moves

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _max_idx(self, agents):
        """Index of the maximising agent in *this* agents list."""
        for i, a in enumerate(agents):
            if a.name == self.maxAgent.name:
                return i
        return 0

    def _is_terminal(self, board, agents):
        """
        Terminal when any agent owns ≥ 60% of non-obstacle cells,
        or only one agent still has units / energy.
        """
        total     = board.rows * board.cols
        obstacles = sum(
            1 for r in range(board.rows) for c in range(board.cols)
            if board[r][c].type == "X"
        )
        threshold = 0.60 * (total - obstacles)

        for agent in agents:
            owned = sum(
                1 for r in range(board.rows) for c in range(board.cols)
                if board[r][c].owner == agent.name
            )
            if owned >= threshold:
                return True

        return sum(1 for a in agents if a.units or a.energy > 0) <= 1

    def _tt_key(self, board, agents, depth, isMax, curAgentIdx):
        """Hashable key for the transposition table."""
        board_part = tuple(
            (board[r][c].type, board[r][c].owner, board[r][c].defenseValue)
            for r in range(board.rows) for c in range(board.cols)
        )
        agents_part = tuple(
            (a.name, a.score, a.energy, tuple(sorted(a.units)))
            for a in agents
        )
        return (board_part, agents_part, depth, isMax, curAgentIdx)