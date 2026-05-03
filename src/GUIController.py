"""
GUIController.py — Dear PyGui interface for the Strategy Game (threaded)

Layout:
  Left : Board grid (coloured rectangles per cell)
  Right: Agent stats panel (score, energy, units, nodes)
  Bottom-left: Move log (last 20 lines)
  Bottom-right: Next / Run buttons + round label

The game runs automatically by default (auto-play ON at startup).
Press "Next" to step one round manually, or "Run/Pause" to toggle auto.

FIX: agent.playMove() is executed in a background daemon thread so the
     Dear PyGui render loop never blocks → no more "not responding" freeze.
"""

import io
import sys
import time
import threading
import types

import dearpygui.dearpygui as dpg

# ── Colours ──────────────────────────────────────────────────────────────────
CELL_COLORS = {
    ".": (50,  55,  75,  255),   # plain — dark blue-grey
    "F": (40,  90,  40,  255),   # fortress — dark green
    "M": (90,  70,  20,  255),   # minefield — dark gold
    "X": (25,  25,  25,  255),   # obstacle — near black
}

AGENT_COLORS = {                  # RGB used for owned-cell tint and text
    "Expert":       (70,  150, 255),
    "Intermediate": (255, 90,  90),
    "Novice":       (70,  210, 110),
}

WHITE  = (230, 230, 230, 255)
GREY   = (140, 140, 140, 255)
YELLOW = (240, 210, 60,  255)
ORANGE = (255, 160, 50,  255)

# ── Layout ───────────────────────────────────────────────────────────────────
WIN_W      = 1280
WIN_H      = 820
RPANEL_W   = 300        # right-side stats panel width
LOG_H      = 200        # move-log panel height
XOFF       = 10         # board left margin
YOFF       = 10         # board top margin
CELL_MAX   = 70
CELL_MIN   = 16


class GUI:
    def __init__(self, game):
        self.game         = game
        self.rounds       = game.rounds
        self.auto_play    = True        # start running immediately
        self.auto_speed   = 1.0        # seconds between rounds
        self._last_t      = 0.0
        self._log_lines   = []         # list of (color, str) for the move log

        # ── Threading state ──────────────────────────────────────────────
        self._thinking        = False   # True while background thread runs
        self._pending_result  = None    # result dict handed back to main thread

        # ── Compute cell size ────────────────────────────────────────────
        board_area_w = WIN_W - RPANEL_W - 20
        board_area_h = WIN_H - LOG_H  - 20
        cs_by_w = (board_area_w - 2 * XOFF) // game.cols
        cs_by_h = (board_area_h - 2 * YOFF) // game.rows
        self.cs  = max(CELL_MIN, min(CELL_MAX, min(cs_by_w, cs_by_h)))
        self.cp  = max(1, self.cs // 20)   # gap between cells

        bpw = game.cols * (self.cs + self.cp) + 2 * XOFF
        bph = game.rows * (self.cs + self.cp) + 2 * YOFF
        self._bpw = bpw
        self._bph = bph

        # DPG tag constants
        self._CANVAS    = "canvas"
        self._RND_LBL   = "lbl_round"
        self._RUN_BTN   = "btn_run"
        self._NEXT_BTN  = "btn_next"
        self._LOG_GROUP = "log_group"
        self._THINK_LBL = "lbl_thinking"

        # Per-agent text-widget tags built in _build_right_panel
        self._atags = {}   # name -> {"score": tag, "energy": tag, ...}

    # =========================================================================
    # Entry point
    # =========================================================================

    def run(self):
        dpg.create_context()
        self._build_ui()
        dpg.create_viewport(title="Stochastic Battlefield",
                            width=WIN_W, height=WIN_H)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_win", True)

        self._draw_board()
        self._refresh_stats()

        while dpg.is_dearpygui_running():
            self._tick()
            dpg.render_dearpygui_frame()

        dpg.destroy_context()

    # =========================================================================
    # UI construction
    # =========================================================================

    def _build_ui(self):
        with dpg.window(tag="main_win", no_title_bar=True,
                        no_move=True, no_resize=True,
                        width=WIN_W, height=WIN_H, pos=(0, 0)):

            # Top row: board canvas (left) + stats panel (right)
            with dpg.group(horizontal=True):

                # ── LEFT: board + control bar ─────────────────────────
                with dpg.group():
                    with dpg.child_window(tag="board_win",
                                          width=self._bpw + 4,
                                          height=self._bph + 4,
                                          border=True, no_scrollbar=True):
                        with dpg.drawlist(tag=self._CANVAS,
                                          width=self._bpw,
                                          height=self._bph):
                            pass

                    # Control bar below the board
                    dpg.add_spacer(height=4)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Next",  width=80,
                                       tag=self._NEXT_BTN,
                                       callback=self._cb_next)
                        dpg.add_button(label="Pause", width=80,
                                       tag=self._RUN_BTN,
                                       callback=self._cb_toggle_run)
                        dpg.add_spacer(width=10)
                        dpg.add_text("Speed (s):", color=GREY)
                        dpg.add_slider_float(tag="speed_slider",
                                             default_value=1.0,
                                             min_value=0.2, max_value=5.0,
                                             width=120, format="%.1f",
                                             callback=lambda s, d:
                                                 setattr(self, "auto_speed", d))
                        dpg.add_spacer(width=16)
                        dpg.add_text("", tag=self._RND_LBL, color=YELLOW)
                        dpg.add_spacer(width=8)
                        # Thinking indicator — hidden by default
                        dpg.add_text("⏳ Agent thinking...",
                                     tag=self._THINK_LBL,
                                     color=ORANGE, show=False)

                # ── RIGHT: agent stats ────────────────────────────────
                with dpg.child_window(tag="stats_win",
                                      width=RPANEL_W - 10,
                                      height=self._bph + 50,
                                      border=True):
                    dpg.add_text("AGENT STATS", color=YELLOW)
                    dpg.add_separator()
                    self._build_right_panel()

            # Bottom: move log
            dpg.add_spacer(height=4)
            with dpg.child_window(tag="log_win",
                                  width=WIN_W - 10,
                                  height=LOG_H,
                                  border=True):
                dpg.add_text("MOVE LOG", color=YELLOW)
                dpg.add_separator()
                dpg.add_group(tag=self._LOG_GROUP)

        # ── Legend (floating, small) ──────────────────────────────────
        with dpg.window(tag="legend_win", label="Legend",
                        width=180, height=170,
                        pos=(WIN_W - 195, WIN_H - 180),
                        no_resize=True, no_collapse=True):
            for ctype, col in CELL_COLORS.items():
                names = {".": "Plain", "F": "Fortress",
                         "M": "Minefield", "X": "Obstacle"}
                with dpg.group(horizontal=True):
                    dpg.add_color_button(default_value=(*col[:3], 255),
                                         width=14, height=14,
                                         no_tooltip=True, no_border=False)
                    dpg.add_text(f"{ctype}  {names[ctype]}", color=GREY)
            dpg.add_separator()
            for name, col in AGENT_COLORS.items():
                with dpg.group(horizontal=True):
                    dpg.add_color_button(default_value=(*col, 255),
                                         width=14, height=14,
                                         no_tooltip=True, no_border=False)
                    dpg.add_text(name[:3], color=(*col, 255))

    def _build_right_panel(self):
        """Create labelled text widgets for each agent's live stats."""
        for agent in self.game.agents:
            name  = agent.name
            col   = (*AGENT_COLORS[name], 255)

            dpg.add_text(f"[ {name} ]", color=col)

            with dpg.group(horizontal=True):
                dpg.add_text("  Score   :", color=GREY)
                t_score = dpg.add_text(str(agent.score), color=WHITE)

            with dpg.group(horizontal=True):
                dpg.add_text("  Energy  :", color=GREY)
                t_energy = dpg.add_text(str(agent.energy), color=WHITE)

            with dpg.group(horizontal=True):
                dpg.add_text("  Units   :", color=GREY)
                t_units = dpg.add_text(str(len(set(agent.units))), color=WHITE)

            with dpg.group(horizontal=True):
                dpg.add_text("  Owned   :", color=GREY)
                t_owned = dpg.add_text("0", color=WHITE)

            with dpg.group(horizontal=True):
                dpg.add_text("  Nodes   :", color=GREY)
                t_nodes = dpg.add_text("--", color=GREY)

            with dpg.group(horizontal=True):
                dpg.add_text("  Disabled:", color=GREY)
                t_dis = dpg.add_text("none", color=GREY)

            dpg.add_separator()

            self._atags[name] = {
                "score":  t_score,
                "energy": t_energy,
                "units":  t_units,
                "owned":  t_owned,
                "nodes":  t_nodes,
                "dis":    t_dis,
            }

    # =========================================================================
    # Board drawing
    # =========================================================================

    def _draw_board(self):
        dpg.delete_item(self._CANVAS, children_only=True)
        board  = self.game.board
        agents = self.game.agents
        cs, cp = self.cs, self.cp

        unit_pos = {}
        for a in agents:
            for pos in a.units:
                unit_pos[pos] = (*AGENT_COLORS[a.name], 255)

        for r in range(board.rows):
            for c in range(board.cols):
                cell = board[r][c]
                x0 = XOFF + c * (cs + cp)
                y0 = YOFF + r * (cs + cp)
                x1, y1 = x0 + cs, y0 + cs

                base = CELL_COLORS.get(cell.type, CELL_COLORS["."])
                if cell.owner and cell.owner in AGENT_COLORS:
                    oc   = AGENT_COLORS[cell.owner]
                    fill = tuple(int(base[i] * 0.6 + oc[i] * 0.4) for i in range(3))
                    fill = (*fill, 255)
                else:
                    fill = base

                dpg.draw_rectangle((x0, y0), (x1, y1),
                                   fill=fill, color=(0, 0, 0, 0),
                                   parent=self._CANVAS)

                if cell.owner and cell.owner in AGENT_COLORS:
                    oc = (*AGENT_COLORS[cell.owner], 255)
                    dpg.draw_rectangle((x0 + 1, y0 + 1), (x1 - 1, y1 - 1),
                                       fill=(0, 0, 0, 0), color=oc,
                                       thickness=2, parent=self._CANVAS)

                if cell.type in ("F", "M", "X") and cs >= 20:
                    dpg.draw_text((x0 + cs // 2 - 4, y0 + cs // 2 - 6),
                                  cell.type, color=WHITE, size=12,
                                  parent=self._CANVAS)

                if cell.type != "X" and cell.defenseValue not in (float("inf"),) and cs >= 24:
                    dv = int(cell.defenseValue)
                    dpg.draw_text((x1 - 9, y1 - 13),
                                  str(dv), color=YELLOW, size=10,
                                  parent=self._CANVAS)

                if (r, c) in unit_pos and cs >= 16:
                    uc = unit_pos[(r, c)]
                    cx, cy = x0 + cs // 2, y0 + cs // 2
                    rad = max(3, cs // 6)
                    dpg.draw_circle((cx, cy), rad,
                                    fill=uc, color=WHITE,
                                    thickness=1, parent=self._CANVAS)

        gc = (60, 60, 80, 180)
        for row in range(board.rows + 1):
            y = YOFF + row * (cs + cp)
            dpg.draw_line((XOFF, y),
                          (XOFF + board.cols * (cs + cp), y),
                          color=gc, thickness=1, parent=self._CANVAS)
        for col in range(board.cols + 1):
            x = XOFF + col * (cs + cp)
            dpg.draw_line((x, YOFF),
                          (x, YOFF + board.rows * (cs + cp)),
                          color=gc, thickness=1, parent=self._CANVAS)

    # =========================================================================
    # Stats panel refresh
    # =========================================================================

    def _refresh_stats(self):
        board  = self.game.board
        agents = self.game.agents

        for a in agents:
            tags = self._atags.get(a.name)
            if not tags:
                continue

            owned = sum(1 for r in range(board.rows)
                        for c in range(board.cols)
                        if board[r][c].owner == a.name)

            dpg.set_value(tags["score"],  str(a.score))
            dpg.set_value(tags["energy"], str(a.energy))
            dpg.set_value(tags["units"],  str(len(set(a.units))))
            dpg.set_value(tags["owned"],  str(owned))

            nv  = getattr(a, "nodesVisited", 0)
            np_ = getattr(a, "nodesPruned",  0)
            dpg.set_value(tags["nodes"],
                          f"{nv} vis / {np_} prn" if nv > 0 else "--")

            dis = ", ".join(f"U{i}({v}t)"
                            for i, v in a.disabledUnits.items() if v > 0) or "none"
            dpg.set_value(tags["dis"], dis)

        cur = self.game.currentRound
        dpg.set_value(self._RND_LBL,
                      f"Round {cur}/{self.rounds}" +
                      ("  [GAME OVER]" if cur >= self.rounds else ""))

    # =========================================================================
    # Move log
    # =========================================================================

    def _log(self, text: str, color=None):
        self._log_lines.append((color or WHITE, text))
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-200:]
        if dpg.does_item_exist(self._LOG_GROUP):
            dpg.delete_item(self._LOG_GROUP, children_only=True)
            for col, line in self._log_lines[-20:]:
                dpg.add_text(line, color=col,
                             parent=self._LOG_GROUP,
                             wrap=WIN_W - 30)

    # =========================================================================
    # Game stepping  —  THREADED
    # =========================================================================

    def _step(self):
        """
        Kick off one game round in a background thread.
        The main render loop stays alive (no freeze / not-responding dialog).
        """
        if self.game.currentRound >= self.rounds:
            self.auto_play = False
            dpg.configure_item(self._RUN_BTN, label="Run")
            return

        if self._thinking:
            return   # already computing — ignore duplicate calls

        self._thinking = True
        self._pending_result = None

        # Show thinking indicator, disable buttons
        dpg.configure_item(self._THINK_LBL, show=True)
        dpg.configure_item(self._NEXT_BTN,  enabled=False)
        dpg.configure_item(self._RUN_BTN,   enabled=False)

        def _worker():
            result = self.game.play_round()
            self._pending_result = result   # hand off to main thread

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_step(self, result):
        """
        Called on the MAIN thread once the background thread has finished.
        Safe to update all DPG widgets here.
        """
        # Hide thinking indicator, re-enable buttons
        dpg.configure_item(self._THINK_LBL, show=False)
        dpg.configure_item(self._NEXT_BTN,  enabled=True)
        dpg.configure_item(self._RUN_BTN,   enabled=True)

        if result.get("effect"):
            self._log(f"[ENV] {result['effect']}", (160, 210, 80, 255))

        for entry in result.get("actions", []):
            name = entry.get("agent", "")
            col  = (*AGENT_COLORS.get(name, (200, 200, 200)), 255)
            self._log(f"  {entry['text']}", col)

        _write_results(result, self.game)

        self._draw_board()
        self._refresh_stats()

        if result.get("winner"):
            w = result["winner"]
            self._log(f"*** WINNER: {w.name} with {w.score} pts ***", YELLOW)
            self.auto_play = False
            dpg.configure_item(self._RUN_BTN, label="Run")

    # =========================================================================
    # Auto-play tick — called every frame from the render loop
    # =========================================================================

    def _tick(self):
        # ── Poll for completed background round ──────────────────────────
        if self._thinking:
            result = self._pending_result
            if result is not None:
                # Reset state BEFORE calling _finish_step so re-entrant
                # auto-play triggers work correctly.
                self._thinking       = False
                self._pending_result = None
                self._finish_step(result)
                # Restore button label after thinking
                dpg.configure_item(
                    self._RUN_BTN,
                    label="Pause" if self.auto_play else "Run"
                )
            # Either way, don't start another round while thinking/finishing
            return

        if not self.auto_play:
            return
        if time.time() - self._last_t >= self.auto_speed:
            self._last_t = time.time()
            self._step()

    # =========================================================================
    # Button callbacks
    # =========================================================================

    def _cb_next(self, *_):
        if not self._thinking:
            self._step()

    def _cb_toggle_run(self, *_):
        if self._thinking:
            return   # ignore while computing
        self.auto_play = not self.auto_play
        dpg.configure_item(self._RUN_BTN,
                           label="Pause" if self.auto_play else "Run")
        if self.auto_play:
            self._last_t = time.time()


# =============================================================================
# results.txt writer
# =============================================================================

_results_file   = "results.txt"
_move_counter   = 0
_agent_totals   = {}   # name -> {"nodes": int, "pruned": int, "moves": int}


def _write_results(result, game):
    """Append per-move node reports to results.txt; write summary at game end."""
    global _move_counter

    with open(_results_file, "a") as f:
        for entry in result.get("actions", []):
            name = entry.get("agent", "?")
            text = entry.get("text", "")
            _move_counter += 1

            agent = next((a for a in game.agents if a.name == name), None)
            nv  = getattr(agent, "nodesVisited", 0) if agent else 0
            np_ = getattr(agent, "nodesPruned",  0) if agent else 0
            pct = f"{100*np_/nv:.1f}%" if nv > 0 else "N/A"

            f.write(f"Move {_move_counter} | Agent {name}\n")
            f.write(f"  Action text               : {text}\n")
            f.write(f"  Nodes explored            : {nv}\n")
            f.write(f"  Nodes pruned (Alpha-Beta) : {np_} ({pct})\n")
            f.write("\n")

            if name not in _agent_totals:
                _agent_totals[name] = {"nodes": 0, "pruned": 0, "moves": 0}
            _agent_totals[name]["nodes"]  += nv
            _agent_totals[name]["pruned"] += np_
            _agent_totals[name]["moves"]  += 1

        if result.get("winner") or game.currentRound >= game.rounds:
            f.write("=" * 60 + "\n")
            f.write("FINAL SUMMARY\n")
            f.write("=" * 60 + "\n")
            for a in game.agents:
                f.write(f"  {a.name:15s}  Final Score: {a.score}  "
                        f"Energy Left: {a.energy}\n")
            winner = result.get("winner") or max(game.agents, key=lambda a: a.score)
            f.write(f"\nWINNER: {winner.name} ({winner.score} pts)\n\n")

            f.write(f"{'Agent':<16} {'Total Moves':>12} {'Nodes Explored':>15} "
                    f"{'Nodes Pruned':>13} {'Pruning %':>10}\n")
            f.write("-" * 70 + "\n")
            for name, d in _agent_totals.items():
                pct = (f"{100*d['pruned']/d['nodes']:.1f}%"
                       if d["nodes"] > 0 else "N/A")
                f.write(f"{name:<16} {d['moves']:>12} {d['nodes']:>15} "
                        f"{d['pruned']:>13} {pct:>10}\n")
            f.write("=" * 60 + "\n")


def _init_results_file():
    """Clear / create results.txt with a header at startup."""
    with open(_results_file, "w") as f:
        f.write("STOCHASTIC BATTLEFIELD — Per-Move Node Report\n")
        f.write("=" * 60 + "\n\n")


# =============================================================================
# patch_game_for_gui  — adds play_round() to the Game instance
# =============================================================================

def patch_game_for_gui(game):
    """
    Attach game.play_round() so the GUI can advance one round at a time.
    play_round() returns:
        { "actions": [{"agent": name, "text": str}, ...],
          "effect":  str,
          "winner":  Agent | None }

    NOTE: play_round() is called from a background thread, so it must NOT
    touch any DPG widgets directly. All UI updates happen in _finish_step()
    on the main thread.
    """
    _init_results_file()

    def play_round(self):
        if self.currentRound >= self.rounds:
            return {"actions": [], "effect": "", "winner": None}

        total_cells  = self.rows * self.cols
        obs_cells    = sum(1 for x in range(self.rows)
                           for y in range(self.cols)
                           if self.board[x][y].type == "X")
        cells_to_win = 0.60 * (total_cells - obs_cells)

        actions = []

        old = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            self.environment.applyEnvironmentalEffect(self.board, self.agents)
        finally:
            sys.stdout = old
        effect_str = buf.getvalue().strip()

        winner = None
        for agent in self.agents:
            if agent.energy <= 0 and len(agent.units) == 0:
                continue

            before  = agent.score
            buf2    = io.StringIO()
            sys.stdout = buf2
            try:
                agent.playMove(self.board, self.agents)
            finally:
                sys.stdout = old
            raw = buf2.getvalue().strip()

            delta = agent.score - before
            text  = raw or f"{agent.name}: (no output)"
            if delta > 0:
                text += f"  [+{delta} pts]"
            actions.append({"agent": agent.name, "text": text})

            owned = sum(1 for x in range(self.rows)
                        for y in range(self.cols)
                        if self.board[x][y].owner == agent.name)
            if owned > cells_to_win:
                actions.append({"agent": agent.name,
                                "text": f"*** {agent.name} owns >60% — INSTANT WIN ***"})
                for a in self.agents:
                    if a.units or a.energy > 0:
                        a.updateScore(self.board)
                self.currentRound += 1
                return {"actions": actions, "effect": effect_str, "winner": agent}

        for a in self.agents:
            if a.units or a.energy > 0:
                a.updateScore(self.board)

        self.currentRound += 1

        if self.currentRound >= self.rounds:
            winner = max(self.agents, key=lambda a: a.score)

        return {"actions": actions, "effect": effect_str, "winner": winner}

    import types as _types
    game.play_round = _types.MethodType(play_round, game)
    return game