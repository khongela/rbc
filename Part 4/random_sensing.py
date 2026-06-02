import os
import random
import chess
import chess.engine
from typing import List, Optional, Tuple
from reconchess import Player, Color, Square, WinReason, GameHistory


STOCKFISH_PATH = os.environ.get('STOCKFISH_EXECUTABLE', '../engine/stockfish-windows-x86-64-avx2.exe')

MAX_BOARD_COUNT = 1000
MAX_MOVE_BOARD_COUNT = 80
STOCKFISH_TIME_LIMIT = 0.02


def start_engine():
    try:
        return chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    except OSError:
        print('Stockfish not found')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state')

    return None


def get_random_move(move_actions):
    if move_actions:
        return random.choice(move_actions)

    return None


def trim_board_set(board_set, max_count):
    if len(board_set) > max_count:
        return set(random.sample(list(board_set), max_count))

    return board_set


class RandomSensing(Player):

    def __init__(self):
        self.engine = start_engine()
        self.board_set = set()
        self.color = None
        self.first_turn = True

    def _restart_engine(self):
        # attempt to cleanly restart Stockfish after a crash
        try:
            if self.engine is not None:
                self.engine.quit()
        except Exception:
            pass

        self.engine = start_engine()

        if self.engine is not None:
            print('Stockfish Engine restarted successfully')
        else:
            print('Stockfish Engine failed to restart')

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

            if not captured_my_piece:
                b = board.copy()
                b.push(chess.Move.null())
                new_boards.add(b.fen())

            for move in board.legal_moves:
                if captured_my_piece:
                    if not board.is_capture(move):
                        continue

                    if capture_square is not None and move.to_square != capture_square:
                        continue
                else:
                    if board.is_capture(move):
                        continue

                b = board.copy()
                b.push(move)
                new_boards.add(b.fen())

        if new_boards:
            self.board_set = trim_board_set(new_boards, MAX_BOARD_COUNT)

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        valid_squares = []

        for rank in range(1, 7):
            for file in range(1, 7):
                square = chess.square(file, rank)

                if square in sense_actions:
                    valid_squares.append(square)

        if valid_squares:
            return random.choice(valid_squares)

        if sense_actions:
            return random.choice(sense_actions)

        return None

    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        sense_dict = {sq: piece for sq, piece in sense_result}
        new_boards = set()

        for fen in self.board_set:
            board = chess.Board(fen)
            match = True

            for square, piece in sense_dict.items():
                if board.piece_at(square) != piece:
                    match = False
                    break

            if match:
                new_boards.add(fen)

        if new_boards:
            self.board_set = trim_board_set(new_boards, MAX_BOARD_COUNT)

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        if not self.board_set:
            return get_random_move(move_actions)

        if self.engine is None:
            return get_random_move(move_actions)

        self.board_set = trim_board_set(self.board_set, MAX_BOARD_COUNT)
        boards_to_check = list(self.board_set)

        if len(boards_to_check) > MAX_MOVE_BOARD_COUNT:
            boards_to_check = random.sample(boards_to_check, MAX_MOVE_BOARD_COUNT)

        votes = {}

        for fen in boards_to_check:
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
                    result = self.engine.play(board, chess.engine.Limit(time=STOCKFISH_TIME_LIMIT))
                    move = result.move
                except chess.engine.EngineTerminatedError:
                    print('Stockfish Engine died - attempting restart')
                    self._restart_engine()
                    continue
                except chess.engine.EngineError:
                    print('Stockfish Engine bad state - skipping board')
                    continue

            if move and move in move_actions:
                key = str(move)
                votes[key] = votes.get(key, 0) + 1

        if not votes:
            return get_random_move(move_actions)

        max_votes = max(votes.values())
        result_str = min(move for move, count in votes.items() if count == max_votes)

        return chess.Move.from_uci(result_str)

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        new_boards = set()

        for fen in self.board_set:
            board = chess.Board(fen)

            if taken_move is None:
                if requested_move is not None and requested_move in board.legal_moves:
                    continue

                board.push(chess.Move.null())
                new_boards.add(board.fen())
            else:
                if taken_move not in board.pseudo_legal_moves:
                    continue

                is_capture = board.is_capture(taken_move)

                if captured_opponent_piece and not is_capture:
                    continue

                if not captured_opponent_piece and is_capture:
                    continue

                if captured_opponent_piece and capture_square is not None and taken_move.to_square != capture_square:
                    continue

                board.push(taken_move)
                new_boards.add(board.fen())

        if new_boards:
            self.board_set = trim_board_set(new_boards, MAX_BOARD_COUNT)

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        if self.engine is None:
            return

        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
