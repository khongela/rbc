import os
import math
import random
from collections import Counter
from typing import List, Optional, Tuple, Dict

import chess
import chess.engine
from reconchess import *


# STOCKFISH_PATH = './stockfish.exe' # Local
STOCKFISH_PATH = './opt/stockfish/stockfish' # For Submission

# ── Board-pool limits ────────────────────────────────────────────────────────
MAX_BOARD_COUNT       = 2000
MAX_MOVE_BOARD_COUNT  = 80
MAX_SENSE_BOARD_COUNT = 150
RECENT_SENSE_COUNT    = 4

# ── Piece values (for board scoring) ─────────────────────────────────────────
PIECE_VALUES = {
    chess.PAWN:   1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK:   5,
    chess.QUEEN:  9,
    chess.KING:   100,
}

# ── Castling geometry ─────────────────────────────────────────────────────────
KINGSIDE_CASTLE_SQUARES = {
    chess.WHITE: [chess.F1, chess.G1],
    chess.BLACK: [chess.F8, chess.G8],
}
QUEENSIDE_CASTLE_SQUARES = {
    chess.WHITE: [chess.D1, chess.C1, chess.B1],
    chess.BLACK: [chess.D8, chess.C8, chess.B8],
}

# Opponent pawn squares whose movement disrupts castling
OPP_CASTLING_BLOCKER_PAWNS = {
    chess.WHITE: [chess.F7, chess.G7, chess.C7, chess.D7],
    chess.BLACK: [chess.F2, chess.G2, chess.C2, chess.D2],
}


def start_engine() -> Optional[chess.engine.SimpleEngine]:
    try:
        return chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH, setpgrp=True)
    except OSError:
        print('Stockfish not found')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state on start')
    return None


def restart_engine(engine: Optional[chess.engine.SimpleEngine]) -> Optional[chess.engine.SimpleEngine]:
    """Quit the old engine safely and open a fresh one."""
    if engine is not None:
        try:
            engine.quit()
        except Exception:
            pass
    return start_engine()


def get_random_move(move_actions: List[chess.Move]) -> Optional[chess.Move]:
    return random.choice(move_actions) if move_actions else None


def get_sense_area(square: chess.Square) -> List[chess.Square]:
    """Return the 3×3 grid of squares centred on *square* (clipped to board edges)."""
    squares = []
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    for rf in [-1, 0, 1]:
        for ff in [-1, 0, 1]:
            nf, nr = file + ff, rank + rf
            if 0 <= nf <= 7 and 0 <= nr <= 7:
                squares.append(chess.square(nf, nr))
    return squares


def get_king_capture_move(board: chess.Board) -> Optional[chess.Move]:
    """Return a legal move that captures the opponent king, if one exists."""
    opp_king = board.king(not board.turn)
    if opp_king is None:
        return None
    attackers = board.attackers(board.turn, opp_king)
    if not attackers:
        return None
    return chess.Move(attackers.pop(), opp_king)


def score_board(board: chess.Board, color: chess.Color) -> int:
    """Heuristic score for a board state from *color*'s perspective."""
    score = 0
    if get_king_capture_move(board) is not None:
        score += 50
    if board.king(not color) is not None:
        score += 20
    for square, piece in board.piece_map().items():
        if piece.color != color:
            score += PIECE_VALUES.get(piece.piece_type, 1)
    return score


def trim_boards(
    boards: List[chess.Board],
    max_count: int,
    color: Optional[chess.Color] = None,
) -> List[chess.Board]:
    """Deduplicate by FEN, then keep the best-scoring boards (or random sample)."""
    unique: Dict[str, chess.Board] = {}
    for b in boards:
        unique[b.fen()] = b
    boards = list(unique.values())

    if len(boards) <= max_count:
        return boards

    if color is not None:
        boards.sort(key=lambda b: score_board(b, color), reverse=True)
        return boards[:max_count]

    return random.sample(boards, max_count)


def get_possible_board_states(
    board: chess.Board,
    captured_my_piece: bool,
    capture_square: Optional[chess.Square],
) -> List[chess.Board]:
    """
    Expand a single board into all boards consistent with the opponent-move
    feedback (captured / not captured, and where).
    """
    next_boards = []

    if not captured_my_piece:
        nb = board.copy()
        nb.push(chess.Move.null())
        next_boards.append(nb)

    for move in board.pseudo_legal_moves:
        if captured_my_piece:
            if not board.is_capture(move):
                continue
            if capture_square is not None and move.to_square != capture_square:
                continue
        else:
            if board.is_capture(move):
                continue

        nb = board.copy()
        nb.push(move)
        next_boards.append(nb)

    return next_boards


def get_time_limit(board_count: int) -> float:
    if board_count <= 10:
        return 0.10
    if board_count <= 30:
        return 0.05
    return 0.02


def best_move_for_board(
    board: chess.Board,
    engine: chess.engine.SimpleEngine,
    time_limit: float,
) -> Optional[chess.Move]:
    king_cap = get_king_capture_move(board)
    if king_cap is not None:
        return king_cap
    try:
        board.clear_stack()
        result = engine.play(board, chess.engine.Limit(time=time_limit))
        return result.move
    except chess.engine.EngineTerminatedError:
        print('Stockfish Engine died')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state')
    return None


def is_block_consistent(board: chess.Board, block: Tuple[chess.Square, Optional[chess.Piece]]) -> bool:
    square, piece = block
    return board.piece_at(square) == piece


# ── Sensing helpers ────────────────────────────────────────────────────────────

def get_sense_pattern(board: chess.Board, sense_square: chess.Square) -> str:
    """Compact string describing the 3×3 pattern around *sense_square* on *board*."""
    return ''.join(
        (p.symbol() if (p := board.piece_at(sq)) else '.')
        for sq in get_sense_area(sense_square)
    )


def score_sense_square_multiboard(
    sense_square: chess.Square,
    boards: List[chess.Board],
    color: chess.Color,
    recent_senses: List[chess.Square],
    opp_piece_history: Dict[chess.Square, Dict[str, chess.Piece]],
) -> float:
    """
    Hybrid sense score combining:

    A) Pattern diversity across the board pool (Jack): more unique patterns →
       higher information; immediately penalises redundancy in our belief state.

    B) Shannon entropy per square (Karabo): how uncertain are we about what
       occupies this square, based on observed history.

    C) Structural bonuses (both): king proximity, centre, own-piece penalty,
       adjacency to known opponent pieces.
    """
    sense_area = get_sense_area(sense_square)

    # ── A: multi-board pattern diversity ──────────────────────────────────────
    patterns: Dict[str, bool] = {}
    opponent_piece_count = 0
    own_piece_count = 0
    king_count = 0

    for board in boards:
        pattern = get_sense_pattern(board, sense_square)
        patterns[pattern] = True

        opp_king = board.king(not color)
        if opp_king in sense_area:
            king_count += 1

        for sq in sense_area:
            piece = board.piece_at(sq)
            if piece:
                if piece.color == color:
                    own_piece_count += 1
                else:
                    opponent_piece_count += 1

    diversity_score = len(patterns) * 10.0
    diversity_score += opponent_piece_count
    diversity_score += king_count * 15
    diversity_score -= own_piece_count

    # ── B: per-square Shannon entropy ────────────────────────────────────────
    def square_entropy(sq: chess.Square) -> float:
        if sq not in opp_piece_history:
            return math.log2(13)          # never seen → maximum uncertainty
        n = len(opp_piece_history[sq])
        if n == 0:
            return math.log2(13)
        if n == 1:
            return 0.0
        prob = 1.0 / n
        return -n * prob * math.log2(prob)

    entropy_score = sum(square_entropy(sq) for sq in sense_area)

    # ── C: structural bonuses ─────────────────────────────────────────────────
    structural = 0.0

    # centre bonus
    f = chess.square_file(sense_square)
    r = chess.square_rank(sense_square)
    if 2 <= f <= 5 and 2 <= r <= 5:
        structural += 5.0

    # adjacency to known opponent pieces
    for known_sq in opp_piece_history:
        dist = chess.square_distance(sense_square, known_sq)
        if dist == 1:
            structural += 0.5
        elif dist == 2:
            structural += 0.2

    # recent-sense penalty (Jack's anti-redundancy)
    if sense_square in recent_senses:
        structural -= 10.0

    # Combine — normalise entropy to a comparable scale
    return diversity_score + (entropy_score * 0.5) + structural


def get_safe_moves(board: chess.Board, move_actions: List[chess.Move]) -> List[chess.Move]:
    """
    From Karabo: filter move_actions to avoid moves that hang material or
    give check (relevant on our single-board model as a sanity filter).
    """
    safe = []
    for move in move_actions:
        temp = board.copy()
        try:
            temp.push(move)
            if temp.is_check():
                continue
            if board.is_capture(move):
                captured = board.piece_at(move.to_square)
                moving   = board.piece_at(move.from_square)
                if captured and moving:
                    if PIECE_VALUES.get(captured.piece_type, 0) >= PIECE_VALUES.get(moving.piece_type, 0):
                        safe.append(move)
                else:
                    safe.append(move)
            else:
                safe.append(move)
        except Exception:
            continue
    return safe if safe else move_actions


# ═══════════════════════════════════════════════════════════════════════════════
#  Merged Agent
# ═══════════════════════════════════════════════════════════════════════════════

class ImprovedAgent(Player):
    """
    Combines the strongest ideas from ImprovedAgent_Jack and ImprovedAgent_Karabo:

    Belief-state management  → Jack   (multi-board pool, FEN dedup, scored trimming)
    Sense scoring            → Hybrid (Jack's pattern diversity + Karabo's Shannon entropy)
    Move selection           → Jack   (voting across board pool with king-capture priority)
    Castling strategy        → Karabo (corridor pre-sense, castle-ASAP, corridor tracking)
    Anti-castling disruption → Karabo (attack f7/g7/c7/d7 in opening)
    Safe-move fallback       → Karabo (material-aware filter)
    Engine resilience        → Karabo (restart on crash)
    Time management          → Jack   (dynamic limit based on board count)
    """

    def __init__(self):
        self.engine: Optional[chess.engine.SimpleEngine] = start_engine()
        self.boards: List[chess.Board] = []
        self.color: Optional[chess.Color] = None
        self.first_turn: bool = True
        self.my_piece_captured_square: Optional[chess.Square] = None
        self.recent_senses: List[chess.Square] = []

        # Castling State
        self.i_have_castled: bool = False
        self.castling_sensed_corridor: bool = False

        # Opponent Piece History for Entropy
        self.opp_piece_history: Dict[chess.Square, Dict[str, chess.Piece]] = {}

    def handle_game_start(
        self,
        color: chess.Color,
        board: chess.Board,
        opponent_name: str,
    ):
        self.boards = [board.copy()]
        self.color = color
        self.first_turn = True
        self.my_piece_captured_square = None
        self.recent_senses = []
        self.i_have_castled = False
        self.castling_sensed_corridor = False
        self.opp_piece_history = {}


    def handle_opponent_move_result(
        self,
        captured_my_piece: bool,
        capture_square: Optional[chess.Square],
    ):
        self.my_piece_captured_square = capture_square

        # White skips first call (no opponent move precedes white's first turn)
        if self.color == chess.WHITE and self.first_turn:
            self.first_turn = False
            return

        self.first_turn = False
        next_boards: List[chess.Board] = []

        for board in self.boards:
            next_boards.extend(
                get_possible_board_states(board, captured_my_piece, capture_square)
            )

        if next_boards:
            self.boards = trim_boards(next_boards, MAX_BOARD_COUNT, self.color)


    def choose_sense(
        self,
        sense_actions: List[chess.Square],
        move_actions: List[chess.Move],
        seconds_left: float,
    ) -> Optional[chess.Square]:
        """
        Priority order:
        1. Square where our piece was just captured            (Jack + Karabo agree)
        2. Own castling corridor, once, before castling        (Karabo)
        3. Hybrid entropy + diversity scoring                  (merged)
        """
        if not sense_actions:
            return None

        # Where was our piece taken?
        if self.my_piece_captured_square in sense_actions:
            sq = self.my_piece_captured_square
            self._record_sense(sq)
            return sq

        # Sense our castling corridor
        if not self.i_have_castled and not self.castling_sensed_corridor:
            corridor_sq = self._sense_our_castle_corridor(sense_actions)
            if corridor_sq is not None:
                self.castling_sensed_corridor = True
                self._record_sense(corridor_sq)
                return corridor_sq

        if not self.boards:
            return random.choice(sense_actions)

        # Build candidate list — exclude squares occupied by own pieces on the most likely board (avoids wasting the sense window on known-own pieces)
        boards_to_check = trim_boards(self.boards, MAX_SENSE_BOARD_COUNT, self.color)
        own_squares = {
            sq for sq, piece in boards_to_check[0].piece_map().items()
            if piece.color == self.color
        }
        candidates = [sq for sq in sense_actions if sq not in own_squares] or list(sense_actions)

        best_sq = random.choice(candidates)
        best_score = -float('inf')

        for sq in candidates:
            score = score_sense_square_multiboard(
                sq,
                boards_to_check,
                self.color,
                self.recent_senses,
                self.opp_piece_history,
            )
            if score > best_score:
                best_score = score
                best_sq = sq

        self._record_sense(best_sq)
        return best_sq

    def _sense_our_castle_corridor(
        self,
        sense_actions: List[chess.Square],
    ) -> Optional[chess.Square]:
        """From Karabo: pick a corridor square to confirm before castling."""
        if self.boards and self.boards[0].has_kingside_castling_rights(self.color):
            for sq in KINGSIDE_CASTLE_SQUARES[self.color]:
                if sq in sense_actions:
                    return sq
        if self.boards and self.boards[0].has_queenside_castling_rights(self.color):
            for sq in QUEENSIDE_CASTLE_SQUARES[self.color]:
                if sq in sense_actions:
                    return sq
        return None

    def _record_sense(self, sq: chess.Square):
        self.recent_senses.append(sq)
        self.recent_senses = self.recent_senses[-RECENT_SENSE_COUNT:]


    def handle_sense_result(
        self,
        sense_result: List[Tuple[chess.Square, Optional[chess.Piece]]],
    ):
        """
        Jack: filter board pool to only boards consistent with the sense result.
        Karabo: update opponent-piece history for entropy calculation.
        """
        # Update entropy history
        for square, piece in sense_result:
            if piece and piece.color != self.color:
                if square not in self.opp_piece_history:
                    self.opp_piece_history[square] = {}
                self.opp_piece_history[square][piece.symbol()] = piece

        # Filter board pool
        next_boards = [
            board for board in self.boards
            if all(is_block_consistent(board, block) for block in sense_result)
        ]
        if next_boards:
            self.boards = trim_boards(next_boards, MAX_BOARD_COUNT, self.color)

    # ── Move selection ────────────────────────────────────────────────────────

    def choose_move(
        self,
        move_actions: List[chess.Move],
        seconds_left: float,
    ) -> Optional[chess.Move]:
        """
        1. King-capture vote across board pool
        2. Castle ASAP if corridor confirmed clear
        3. Anti-castling disruption in opening
        4. Stockfish vote across board pool
        5. Safe-move fallback
        6. Random
        """
        if not move_actions:
            return None

        if not self.boards:
            return get_random_move(move_actions)

        if self.engine is None:
            return get_random_move(move_actions)

        boards_to_check = trim_boards(self.boards, MAX_MOVE_BOARD_COUNT, self.color)

        # ── 1: King capture vote ───────────────────────────────────────────────
        king_votes: Dict[str, int] = {}
        for board in boards_to_check:
            move = get_king_capture_move(board)
            if move and move in move_actions:
                king_votes[str(move)] = king_votes.get(str(move), 0) + 1

        if king_votes:
            max_v = max(king_votes.values())
            return chess.Move.from_uci(
                min(m for m, c in king_votes.items() if c == max_v)
            )

        # Castle ASAP
        if not self.i_have_castled:
            castle_move = self._try_castle(move_actions)
            if castle_move:
                return castle_move

        # Anti-castling disruption (opening only)
        total_half_moves = sum(len(b.move_stack) for b in boards_to_check) // max(len(boards_to_check), 1)
        if total_half_moves < 20:
            disruption = self._attack_castling_blocker_pawns(move_actions)
            if disruption:
                return disruption

        # Stockfish vote
        time_limit = get_time_limit(len(boards_to_check))
        # Adaptive: more time early (Karabo's insight)
        total_moves = len(self.boards[0].move_stack) if self.boards else 0
        if total_moves < 10:
            time_limit = max(time_limit, 0.10)
        elif total_moves < 20:
            time_limit = max(time_limit, 0.05)

        votes: Dict[str, int] = {}
        for board in boards_to_check:
            move = best_move_for_board(board, self.engine, time_limit)
            if move is None:
                # Engine may have crashed — attempt restart
                self.engine = restart_engine(self.engine)
                break
            if move in move_actions:
                votes[str(move)] = votes.get(str(move), 0) + 1

        if votes:
            max_v = max(votes.values())
            return chess.Move.from_uci(
                min(m for m, c in votes.items() if c == max_v)
            )

        # Safe-move fallback
        if self.boards:
            safe = get_safe_moves(self.boards[0], move_actions)
            if safe:
                return random.choice(safe)

        # Random
        return get_random_move(move_actions)

    def _try_castle(self, move_actions: List[chess.Move]) -> Optional[chess.Move]:
        """Castle if rights exist and corridor is clear on the top board."""
        if not self.boards:
            return None
        board = self.boards[0]
        rank = 1 if self.color == chess.WHITE else 8
        ks_move = chess.Move.from_uci(f"e{rank}g{rank}")
        qs_move = chess.Move.from_uci(f"e{rank}c{rank}")

        if (ks_move in move_actions
                and board.has_kingside_castling_rights(self.color)
                and all(board.piece_at(sq) is None for sq in KINGSIDE_CASTLE_SQUARES[self.color])):
            return ks_move

        if (qs_move in move_actions
                and board.has_queenside_castling_rights(self.color)
                and all(board.piece_at(sq) is None for sq in QUEENSIDE_CASTLE_SQUARES[self.color])):
            return qs_move

        return None

    def _attack_castling_blocker_pawns(
        self, move_actions: List[chess.Move]
    ) -> Optional[chess.Move]:
        """Develop bishop/knight to threaten opponent castling-shield pawns."""
        if not self.boards:
            return None
        board = self.boards[0]
        target_pawns = set(OPP_CASTLING_BLOCKER_PAWNS[self.color])
        best_move_found = None
        best_targets_hit = 0

        for move in move_actions:
            piece = board.piece_at(move.from_square)
            if piece is None or piece.piece_type not in (chess.BISHOP, chess.KNIGHT):
                continue
            temp = board.copy()
            try:
                temp.push(move)
                hits = sum(1 for sq in target_pawns if temp.is_attacked_by(self.color, sq))
                if hits > best_targets_hit:
                    best_targets_hit = hits
                    best_move_found = move
            except Exception:
                continue

        return best_move_found if best_targets_hit > 0 else None

    def handle_move_result(
        self,
        requested_move: Optional[chess.Move],
        taken_move: Optional[chess.Move],
        captured_opponent_piece: bool,
        capture_square: Optional[chess.Square],
    ):
        
        # Detect castling
        if taken_move is not None and not self.i_have_castled:
            rank = 1 if self.color == chess.WHITE else 8
            if taken_move in [
                chess.Move.from_uci(f"e{rank}g{rank}"),
                chess.Move.from_uci(f"e{rank}c{rank}"),
            ]:
                self.i_have_castled = True

        # Filter board pool
        next_boards: List[chess.Board] = []
        for board in self.boards:
            if taken_move is None:
                if requested_move is not None and requested_move in board.pseudo_legal_moves:
                    continue
                nb = board.copy()
                nb.push(chess.Move.null())
                next_boards.append(nb)
            else:
                if taken_move not in board.pseudo_legal_moves:
                    continue
                if captured_opponent_piece:
                    if not board.is_capture(taken_move):
                        continue
                    if capture_square is not None and taken_move.to_square != capture_square:
                        continue
                else:
                    if board.is_capture(taken_move):
                        continue

                nb = board.copy()
                nb.push(taken_move)
                next_boards.append(nb)

        if next_boards:
            self.boards = trim_boards(next_boards, MAX_BOARD_COUNT, self.color)

    # ── Game end ──────────────────────────────────────────────────────────────

    def handle_game_end(
        self,
        winner_color: Optional[chess.Color],
        win_reason,
        game_history,
    ):
        if self.engine is None:
            return
        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
