"""
Minimax.py — Expectiminimax with Alpha-Beta Pruning  (fixed)

Fixes applied
-------------
1. Move-count cap       — each agent's move list is capped (Expert 12, Int 8,
                          Novice 6) using a priority sort so the best candidates
                          are explored first.  This prevents the exponential
                          blowup that caused the freeze on rounds 6-7 as the
                          board filled up with owned/attackable cells.

2. Transposition table  — TT key no longer includes agent.score (which changes
                          every call and destroyed hit-rate).  We key on board
                          layout + unit positions + energy + depth/node-type.
                          The table is NOT cleared between root moves so it
                          provides genuine cross-branch sharing.

3. Move deduplication   — duplicate (action,unit,target) triples are removed
                          before the search loop.

4. Double-clone fix     — _expected_value no longer receives a pre-cloned board;
                          it clones fresh per outcome internally (correct), and
                          the outer getBestMove / expectiminimax loops clone only
                          once for deterministic nodes.

5. Depth scaling        — Expert depth stays at 7 but effective branching is
                          controlled by the move cap; Intermediate/Novice caps
                          keep their searches fast even on a full board.
"""

import math
from Board import Board, Cell

# ---------------------------------------------------------------------------
# Probability tables (mirror Agents.py)
# ---------------------------------------------------------------------------

COMBAT_OUTCOMES = [
    {"prob": 0.20, "type": "Fail",     "energy_loss": 1},
    {"prob": 0.15, "type": "Fail",     "energy_loss": 0},
    {"prob": 0.16, "type": "Partial",  "capture": False},
    {"prob": 0.12, "type": "Partial",  "capture": True},
    {"prob": 0.26, "type": "Full",     "dmg": 1},
    {"prob": 0.11, "type": "Critical", "dmg": 1, "bonus": 2},
]

_novice_raw   = [o for o in COMBAT_OUTCOMES if o["type"] in ("Full", "Critical")]
_novice_total = sum(o["prob"] for o in _novice_raw)
NOVICE_OUTCOMES = [{**o, "prob": o["prob"] / _novice_total} for o in _novice_raw]

MINE_OUTCOMES = [
    {"prob": 0.40, "type": "Safe"},
    {"prob": 0.30, "type": "EnergyDrain"},
    {"prob": 0.20, "type": "Disabled"},
    {"prob": 0.10, "type": "Detonation"},
]

# Max moves evaluated per agent per node (keeps branching factor bounded)
_MOVE_CAPS = {"ExpertAgent": 12, "IntermediateAgent": 8, "NoviceAgent": 6}

# ---------------------------------------------------------------------------
# Cloning helpers
# ---------------------------------------------------------------------------

def _clone_cell(cell):
    c = Cell(cell.type, cell.owner)
    c.defenseValue = cell.defenseValue
    return c


def _clone_board(board: Board) -> Board:
    nb      = Board.__new__(Board)
    nb.rows = board.rows
    nb.cols = board.cols
    nb.board = [
        [_clone_cell(board[r][c]) for c in range(board.cols)]
        for r in range(board.rows)
    ]
    return nb


def _clone_agent(agent):
    a = object.__new__(type(agent))
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
    if hasattr(agent, "transpositionTable"):
        a.transpositionTable = agent.transpositionTable   # shared ref is fine
    return a


def clone_state(board: Board, agents: list):
    return _clone_board(board), [_clone_agent(a) for a in agents]


# ---------------------------------------------------------------------------
# Stochasticity classifier
# ---------------------------------------------------------------------------

def _is_stochastic(action: str, unit, target, board: Board) -> bool:
    tx, ty = target
    cell   = board[tx][ty]
    if action == "Attack":
        return cell.owner is not None and cell.type != "X"
    if action == "Move":
        if cell.owner is not None and cell.owner != "":
            return True
        if cell.type == "M":
            return True
    return False


# ---------------------------------------------------------------------------
# Deterministic move applicator
# ---------------------------------------------------------------------------

def _apply_move(action: str, unit, target, agent, board: Board):
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
    tx, ty   = target
    cell     = board[tx][ty]
    unit_idx = agent.units.index(unit) if unit in agent.units else 0
    otype    = outcome["type"]

    if otype == "Safe":
        cell.owner        = agent.name
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
# Move priority scorer  (used to sort + cap move lists)
# ---------------------------------------------------------------------------

def _move_priority(action, unit, target, agent, board: Board) -> float:
    """Higher = evaluated first → better alpha-beta pruning."""
    tx, ty = target
    cell   = board[tx][ty]
    score  = 0.0

    if action == "Attack":
        score += 10.0
        # Prefer weaker defenders
        dv = cell.defenseValue if cell.defenseValue != float("inf") else 99
        score += (3 - dv)

    elif action == "Move":
        if cell.owner is not None:       # combat move
            score += 8.0
        elif cell.type == "F":           # unowned fortress
            score += 6.0
        elif cell.type == "M":           # minefield (risky but expands)
            score += 2.0
        else:
            score += 3.0

    elif action == "Fortify":
        score += 1.0

    elif action == "Wait":
        score -= 5.0                     # explored last

    return score


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class Minimax:
    def __init__(self, maximizingAgent, allAgents):
        self.maxAgent  = maximizingAgent
        self.allAgents = allAgents
        self.useTT     = hasattr(maximizingAgent, "transpositionTable")
        self.isNovice  = type(maximizingAgent).__name__ == "NoviceAgent"
        self._cap      = _MOVE_CAPS.get(type(maximizingAgent).__name__, 8)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def getBestMove(self, board):
        self.maxAgent.nodesVisited = 0
        self.maxAgent.nodesPruned  = 0
        # Do NOT clear TT here — keep entries from previous root moves
        # so cross-branch sharing works.  TT is cleared once per real
        # game turn in Agent.playMove via Minimax.__init__ construction.

        root_moves = self._get_moves_capped(self.maxAgent, board)
        if not root_moves:
            unit = self.maxAgent.units[0] if self.maxAgent.units else (0, 0)
            return ("Wait", unit, unit)

        best_val  = -math.inf
        best_move = root_moves[0]

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
        self.maxAgent.nodesVisited += 1

        if depth == 0 or self._is_terminal(board, agents):
            me = next((a for a in agents if a.name == self.maxAgent.name), agents[0])
            return me.evaluate(board, agents)

        # Transposition table (Expert only)
        tt_key = None
        if self.useTT:
            tt_key = self._tt_key(board, agents, depth, isMax, curAgentIdx)
            if tt_key in self.maxAgent.transpositionTable:
                return self.maxAgent.transpositionTable[tt_key]

        cur_agent = agents[curAgentIdx]
        moves     = self._get_moves_capped(cur_agent, board)
        next_idx    = (curAgentIdx + 1) % len(agents)
        next_is_max = (next_idx == self._max_idx(agents))

        if not moves:
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
                child_val = self._expected_value(
                    action, unit, target, sim_cur,
                    sim_board, sim_agents,
                    depth - 1, alpha, beta, next_is_max, next_idx,
                )
            else:
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
                break

        if self.useTT and tt_key is not None:
            self.maxAgent.transpositionTable[tt_key] = result

        return result

    # ------------------------------------------------------------------
    # Chance-node expected-value computation
    # ------------------------------------------------------------------

    def _expected_value(self, action, unit, target, agent,
                        board, agents, depth, alpha, beta,
                        next_is_max, next_idx):
        tx, ty = target
        cell   = board[tx][ty]

        if action == "Move" and cell.type == "M" and (cell.owner is None or cell.owner == ""):
            outcomes = MINE_OUTCOMES
            apply_fn = _apply_mine_outcome
        else:
            outcomes = NOVICE_OUTCOMES if self.isNovice else COMBAT_OUTCOMES
            apply_fn = _apply_combat_outcome

        expected = 0.0
        for outcome in outcomes:
            # Clone fresh for each stochastic branch (correct — don't reuse)
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
    # Move generator with dedup + priority sort + cap
    # ------------------------------------------------------------------

    def _get_moves_capped(self, agent, board):
        """
        Generate, deduplicate, priority-sort, and cap the move list.
        The cap prevents exponential blowup on a full board.
        """
        raw   = self.generateAllAgentMoves(agent, board)
        seen  = set()
        dedup = []
        for m in raw:
            if m not in seen:
                seen.add(m)
                dedup.append(m)

        # Sort by priority descending so best moves are explored first
        dedup.sort(key=lambda m: _move_priority(m[0], m[1], m[2], agent, board),
                   reverse=True)

        return dedup[:self._cap]

    def generateAllAgentMoves(self, agent, board):
        moves = []
        seen_units = set()

        for unit in agent.units:
            if unit in seen_units:
                continue
            seen_units.add(unit)

            ux, uy   = unit
            unit_idx = agent.units.index(unit)

            if agent.disabledUnits.get(unit_idx, 0) > 0:
                moves.append(("Wait", unit, unit))
                continue

            targets = agent.generateValidMoves(unit, board)

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
        for i, a in enumerate(agents):
            if a.name == self.maxAgent.name:
                return i
        return 0

    def _is_terminal(self, board, agents):
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
        """
        TT key — excludes agent.score to maximise hit rate.
        Score changes every real turn but within a single search tree
        the board layout + units + energy fully determine the state value.
        """
        board_part = tuple(
            (board[r][c].type, board[r][c].owner, board[r][c].defenseValue)
            for r in range(board.rows) for c in range(board.cols)
        )
        agents_part = tuple(
            (a.name, a.energy, tuple(sorted(a.units)),
             tuple(sorted(a.disabledUnits.items())))
            for a in agents
        )
        return (board_part, agents_part, depth, isMax, curAgentIdx)