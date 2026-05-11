import random
import collections
import chess
import chess.engine
from typing import List, Optional, Tuple
from reconchess import Player, Color, Square, WinReason, GameHistory

STOCKFISH_PATH = '../engine/stockfish-windows-x86-64-avx2.exe'
MAX_BOARD_COUNT = 10000
MIN_TIME_LIMIT = 0.001 

class RandomSensing(Player):
    def __init__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH, setpgrp=True)
        self.board_set = set()
        self.color = None
        self.first_turn = True

    def _restart_engine(self):
        """Attempt to cleanly restart Stockfish after a crash."""
        try:
            self.engine.quit()
        except Exception:
            pass
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH, setpgrp=True)
            print('Stockfish Engine restarted successfully')
        except Exception as e:
            print(f'Stockfish Engine failed to restart: {e}')

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.color = color
        self.board_set = {board.fen()}
        self.first_turn = True

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
        if self.color == chess.WHITE and self.first_turn:
            self.first_turn = False
            return

        self.first_turn = False
        new_boards = set()

        for fen in self.board_set:
            board = chess.Board(fen)
            for move in board.legal_moves:
                if captured_my_piece:
                    if move.to_square == capture_square:
                        b = board.copy()
                        b.push(move)
                        new_boards.add(b.fen())
                else:
                    if not board.is_capture(move):
                        b = board.copy()
                        b.push(move)
                        new_boards.add(b.fen())

        if new_boards:
            self.board_set = new_boards

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        valid_squares = []
        for r in range(1, 7):
            for f in range(1, 7):
                valid_squares.append(chess.square(f, r))

        return random.choice(valid_squares)

    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        sense_dict = {sq: piece for sq, piece in sense_result}
        new_boards = set()

        for fen in self.board_set:
            board = chess.Board(fen)
            match = True
            for sq, piece in sense_dict.items():
                if board.piece_at(sq) != piece:
                    match = False
                    break
            if match:
                new_boards.add(fen)

        if new_boards:
            self.board_set = new_boards

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        if len(self.board_set) > MAX_BOARD_COUNT:
            self.board_set = set(random.sample(list(self.board_set), MAX_BOARD_COUNT))

        N = len(self.board_set)
        if N == 0:
            return random.choice(move_actions + [None])
        
        time_limit = max(10.0 / N, MIN_TIME_LIMIT)
        votes = {}

        for fen in self.board_set:
            board = chess.Board(fen)
            move = None

            opponent_king_square = board.king(not board.turn)
            if opponent_king_square:
                attackers = board.attackers(board.turn, opponent_king_square)
                if attackers:
                    attacker_square = attackers.pop()
                    move = chess.Move(attacker_square, opponent_king_square)

            if not move:
                try:
                    board.clear_stack()
                    result = self.engine.play(board, chess.engine.Limit(time=time_limit))
                    move = result.move
                except chess.engine.EngineTerminatedError:
                    print('Stockfish Engine died — attempting restart')
                    self._restart_engine()
                    continue  # skip this board; engine is being restarted
                except chess.engine.EngineError:
                    print('Stockfish Engine bad state — skipping board')
                    continue  # bad state on one board shouldn't halt all remaining boards

            if move and move in move_actions:
                key = str(move)
                votes[key] = votes.get(key, 0) + 1

        if not votes:
            return random.choice(move_actions + [None])

        max_votes = max(votes.values())
        result_str = min(m for m, count in votes.items() if count == max_votes)

        return chess.Move.from_uci(result_str)

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        new_boards = set()

        for fen in self.board_set:
            board = chess.Board(fen)

            if taken_move is not None:
                is_capture = board.is_capture(taken_move)

                if captured_opponent_piece and not is_capture:
                    continue
                if not captured_opponent_piece and is_capture:
                    continue

                if taken_move in board.pseudo_legal_moves:
                    board.push(taken_move)
                    new_boards.add(board.fen())
            else:
                board.push(chess.Move.null())
                new_boards.add(board.fen())

        if new_boards:
            self.board_set = new_boards

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
