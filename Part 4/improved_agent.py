import os
import random
from typing import List, Optional, Tuple

import chess
import chess.engine
from reconchess import *


STOCKFISH_PATH = os.environ.get('STOCKFISH_EXECUTABLE', '../engine/stockfish-windows-x86-64-avx2.exe')

MAX_BOARD_COUNT = 2000
MAX_MOVE_BOARD_COUNT = 80
MAX_SENSE_BOARD_COUNT = 150
RECENT_SENSE_COUNT = 4


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


def get_sense_area(square):
    squares = []
    file = chess.square_file(square)
    rank = chess.square_rank(square)

    for rank_change in [-1, 0, 1]:
        for file_change in [-1, 0, 1]:
            new_file = file + file_change
            new_rank = rank + rank_change

            if 0 <= new_file <= 7 and 0 <= new_rank <= 7:
                squares.append(chess.square(new_file, new_rank))

    return squares


def get_king_capture_move(board):
    opponent_king_square = board.king(not board.turn)

    if opponent_king_square is None:
        return None

    attackers = board.attackers(board.turn, opponent_king_square)

    if not attackers:
        return None

    attacker_square = attackers.pop()

    return chess.Move(attacker_square, opponent_king_square)


def score_board(board, color):
    score = 0

    king_capture_move = get_king_capture_move(board)

    if king_capture_move is not None:
        score += 50

    opponent_king = board.king(not color)

    if opponent_king is not None:
        score += 20

    for square, piece in board.piece_map().items():
        if piece.color != color:
            score += 1

    return score


def trim_boards(boards, max_count, color=None):
    unique_boards = {}

    for board in boards:
        unique_boards[board.fen()] = board

    boards = list(unique_boards.values())

    if len(boards) <= max_count:
        return boards

    if color is not None:
        boards.sort(key=lambda board: score_board(board, color), reverse=True)
        return boards[:max_count]

    return random.sample(boards, max_count)


def get_possible_board_states(board, captured_my_piece, capture_square):
    next_boards = []

    if not captured_my_piece:
        next_board = board.copy()
        next_board.push(chess.Move.null())
        next_boards.append(next_board)

    for move in board.pseudo_legal_moves:
        if captured_my_piece:
            if not board.is_capture(move):
                continue

            if capture_square is not None and move.to_square != capture_square:
                continue
        else:
            if board.is_capture(move):
                continue

        next_board = board.copy()
        next_board.push(move)
        next_boards.append(next_board)

    return next_boards


def get_time_limit(board_count):
    if board_count <= 10:
        return 0.10

    if board_count <= 30:
        return 0.05

    return 0.02


def best_move(board, engine, time_limit):
    king_capture_move = get_king_capture_move(board)

    if king_capture_move is not None:
        return king_capture_move

    try:
        board.clear_stack()
        result = engine.play(board, chess.engine.Limit(time=time_limit))
        return result.move
    except chess.engine.EngineTerminatedError:
        print('Stockfish Engine died')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state')

    return None


def is_block_consistent(board, block: Tuple[Square, Optional[chess.Piece]]):
    square, piece = block

    if board.piece_at(square) != piece:
        return False

    return True


def get_sense_pattern(board, sense_square):
    pattern = ''

    for square in get_sense_area(sense_square):
        piece = board.piece_at(square)

        if piece:
            pattern += piece.symbol()
        else:
            pattern += '.'

    return pattern


def score_sense_square(sense_square, boards, color):
    patterns = {}
    opponent_piece_count = 0
    own_piece_count = 0
    king_count = 0

    sense_area = get_sense_area(sense_square)

    for board in boards:
        pattern = get_sense_pattern(board, sense_square)
        patterns[pattern] = True

        opponent_king = board.king(not color)

        if opponent_king in sense_area:
            king_count += 1

        for square in sense_area:
            piece = board.piece_at(square)

            if piece and piece.color == color:
                own_piece_count += 1

            if piece and piece.color != color:
                opponent_piece_count += 1

    score = len(patterns) * 10
    score += opponent_piece_count
    score += king_count * 15
    score -= own_piece_count

    file = chess.square_file(sense_square)
    rank = chess.square_rank(sense_square)

    if 2 <= file <= 5 and 2 <= rank <= 5:
        score += 5

    return score


class ImprovedAgent(Player):

    def __init__(self):
        self.engine = start_engine()
        self.boards = []
        self.color = None
        self.first_turn = True
        self.my_piece_captured_square = None
        self.recent_senses = []

    def handle_game_start(self, color: chess.Color, board: chess.Board, opponent_name: str):
        # function that is run when the game starts
        self.boards = [board.copy()]
        self.color = color
        self.first_turn = True
        self.my_piece_captured_square = None
        self.recent_senses = []

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: chess.Square):
        # feedback on whether the opponent captured a piece
        self.my_piece_captured_square = capture_square

        if self.color == chess.WHITE and self.first_turn:
            self.first_turn = False
            return

        self.first_turn = False
        next_boards = []

        for board in self.boards:
            new_boards = get_possible_board_states(board, captured_my_piece, capture_square)
            next_boards.extend(new_boards)

        if next_boards:
            self.boards = trim_boards(next_boards, MAX_BOARD_COUNT, self.color)

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        # choose the sense square that gives the most useful board patterns
        if not sense_actions:
            return None

        if self.my_piece_captured_square in sense_actions:
            self.recent_senses.append(self.my_piece_captured_square)
            self.recent_senses = self.recent_senses[-RECENT_SENSE_COUNT:]
            return self.my_piece_captured_square

        if not self.boards:
            return random.choice(sense_actions)

        boards_to_check = trim_boards(self.boards, MAX_SENSE_BOARD_COUNT, self.color)

        possible_sense_actions = list(sense_actions)
        first_board = boards_to_check[0]

        for square, piece in first_board.piece_map().items():
            if piece.color == self.color and square in possible_sense_actions:
                possible_sense_actions.remove(square)

        if not possible_sense_actions:
            possible_sense_actions = list(sense_actions)

        best_square = random.choice(possible_sense_actions)
        best_score = -1

        for sense_square in possible_sense_actions:
            score = score_sense_square(sense_square, boards_to_check, self.color)

            if sense_square in self.recent_senses:
                score -= 10

            if score > best_score:
                best_score = score
                best_square = sense_square

        self.recent_senses.append(best_square)
        self.recent_senses = self.recent_senses[-RECENT_SENSE_COUNT:]

        return best_square

    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        # this is where the sensing result returns feedback
        next_boards = []

        for board in self.boards:
            consistent = True

            for block in sense_result:
                if not is_block_consistent(board, block):
                    consistent = False
                    break

            if consistent:
                next_boards.append(board)

        if next_boards:
            self.boards = trim_boards(next_boards, MAX_BOARD_COUNT, self.color)

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        # execute a chess move
        if not self.boards:
            return get_random_move(move_actions)

        if self.engine is None:
            return get_random_move(move_actions)

        boards_to_check = trim_boards(self.boards, MAX_MOVE_BOARD_COUNT, self.color)
        time_limit = get_time_limit(len(boards_to_check))

        king_votes = {}

        for board in boards_to_check:
            move = get_king_capture_move(board)

            if move and move in move_actions:
                key = str(move)
                king_votes[key] = king_votes.get(key, 0) + 1

        if king_votes:
            max_votes = max(king_votes.values())
            result = min(move for move, count in king_votes.items() if count == max_votes)
            return chess.Move.from_uci(result)

        votes = {}

        for board in boards_to_check:
            move = best_move(board, self.engine, time_limit)

            if move and move in move_actions:
                key = str(move)
                votes[key] = votes.get(key, 0) + 1

        if not votes:
            return get_random_move(move_actions)

        max_votes = max(votes.values())
        result = min(move for move, count in votes.items() if count == max_votes)

        return chess.Move.from_uci(result)

    def handle_move_result(self, requested_move, taken_move, captured_opponent_piece, capture_square):
        # this function is called after your move is executed
        next_boards = []

        for board in self.boards:
            if taken_move is None:
                if requested_move is not None and requested_move in board.pseudo_legal_moves:
                    continue

                next_board = board.copy()
                next_board.push(chess.Move.null())
                next_boards.append(next_board)
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

                next_board = board.copy()
                next_board.push(taken_move)
                next_boards.append(next_board)

        if next_boards:
            self.boards = trim_boards(next_boards, MAX_BOARD_COUNT, self.color)

    def handle_game_end(self, winner_color, win_reason, game_history):
        # shut down everything at the end of the game
        if self.engine is None:
            return

        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
