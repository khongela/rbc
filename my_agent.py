import chess
import chess.engine
import random
from reconchess import Player, Color, WinReason, GameHistory
from reconchess.utilities import without_opponent_pieces, is_illegal_castle
from typing import List, Tuple, Optional


# -----------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------

def generate_next_moves(board):
    moves = set()
    moves.add(chess.Move.null())
    for move in board.pseudo_legal_moves:
        moves.add(move)
    for move in without_opponent_pieces(board).generate_castling_moves():
        if not is_illegal_castle(board, move):
            moves.add(move)
    return sorted(moves, key=lambda m: m.uci())


def generate_next_states(board):
    states = []
    for move in generate_next_moves(board):
        updated_board = board.copy()
        updated_board.push(move)
        states.append(updated_board.fen())
    return sorted(states)


def generate_capture_states(board, capture_square):
    next_states = set()
    for move in board.pseudo_legal_moves:
        if move.uci().endswith(capture_square) and board.is_capture(move):
            next_board = board.copy()
            next_board.push_uci(move.uci())
            next_states.add(next_board.fen())
    return sorted(next_states)


def filter_sensing_states(board_states, window_description):
    window = {}
    for box in window_description.split(';'):
        location, piece = box.split(':', 1)
        window[location] = piece

    valid_states = []
    for board_state in board_states:
        board = chess.Board(fen=board_state)
        consistent = all(
            (board.piece_at(chess.parse_square(loc)).symbol() if board.piece_at(chess.parse_square(loc)) else '?') == piece
            for loc, piece in window.items()
        )
        if consistent:
            valid_states.append(board_state)
    return sorted(valid_states)


def best_move(board, engine, time_limit=0.5):
    opponent_king_square = board.king(not board.turn)
    if opponent_king_square:
        attackers = board.attackers(board.turn, opponent_king_square)
        if attackers:
            return chess.Move(attackers.pop(), opponent_king_square)
    try:
        simplified = without_opponent_pieces(board)
        simplified.clear_stack()
        result = engine.play(simplified, chess.engine.Limit(time=time_limit))
        return result.move
    except chess.engine.EngineTerminatedError:
        print('Stockfish Engine died')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state')


# -----------------------------------------------------------------------
# Baseline Agent — RandomSensing
# -----------------------------------------------------------------------

# class RandomSensing(Player):

#     def __init__(self):
#         self.board = None
#         self.color = None
#         self.possible_states = set()
#         self.engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)

#     def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
#         """
#         Called at the start of the game. The starting position is known perfectly.
#         Store it as the sole element of the belief state.
#         """
#         self.color = color
#         self.board = board
#         self.possible_states = {board.fen()}

#     def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[chess.Square]):
#         """
#         Called after the opponent moves. Use capture information to narrow down
#         the possible states by generating next states consistent with what happened.
#         """
#         next_states = set()

#         for fen in self.possible_states:
#             board = chess.Board(fen=fen)

#             if captured_my_piece:
#                 # only keep states where a capture occurred on capture_square
#                 capture_square_name = chess.square_name(capture_square)
#                 next_states.update(generate_capture_states(board, capture_square_name))
#             else:
#                 # keep all next states where no capture was made
#                 for next_fen in generate_next_states(board):
#                     next_board = chess.Board(fen=next_fen)
#                     # the last move pushed onto the board tells us if a capture happened
#                     if next_board.move_stack and not next_board.is_capture(next_board.peek()):
#                         next_states.add(next_fen)
#                     elif not next_board.move_stack:
#                         next_states.add(next_fen)

#         self.possible_states = next_states

#     def choose_sense(self, sense_actions: List[chess.Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Square]:
#         """
#         Choose a square to sense. Baseline: pick uniformly at random,
#         excluding edge squares where the 3x3 window would be clipped.
#         """
#         non_edge = [
#             sq for sq in sense_actions
#             if chess.square_rank(sq) not in (0, 7) and chess.square_file(sq) not in (0, 7)
#         ]
#         return random.choice(non_edge) if non_edge else random.choice(sense_actions)

#     def handle_sense_result(self, sense_result: List[Tuple[chess.Square, Optional[chess.Piece]]]):
#         """
#         Called with the 3x3 window observation after sensing.
#         Use it to filter the belief state.
#         """
#         # convert sense_result into "square:piece;square:piece;..." format
#         window_parts = []
#         for square, piece in sense_result:
#             square_name = chess.square_name(square)
#             piece_symbol = piece.symbol() if piece else '?'
#             window_parts.append(f'{square_name}:{piece_symbol}')
#         window_description = ';'.join(window_parts)

#         self.possible_states = set(filter_sensing_states(list(self.possible_states), window_description))

#     def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
#         """
#         Select a move using majority voting across all possible states.
#         Time limit for Stockfish is 10/N where N is number of boards.
#         Cap belief state at 10000 boards.
#         """
#         if not self.possible_states:
#             return None

#         states = self.possible_states
#         if len(states) > 10000:
#             states = set(random.sample(list(states), 10000))

#         time_limit = 10 / len(states)
#         votes = {}

#         for fen in states:
#             board = chess.Board(fen=fen)
#             move = best_move(board, self.engine, time_limit)
#             if move:
#                 key = str(move)
#                 votes[key] = votes.get(key, 0) + 1

#         if not votes:
#             return None

#         best = max(sorted(votes.keys()), key=lambda m: votes[m])
#         return chess.Move.from_uci(best)

#     def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
#                            captured_opponent_piece: bool, capture_square: Optional[chess.Square]):
#         """
#         Called after your move is executed. Update belief state based on
#         the move that was actually taken.
#         """
#         if taken_move is not None:
#             next_states = set()
#             for fen in self.possible_states:
#                 board = chess.Board(fen=fen)
#                 try:
#                     board.push(taken_move)
#                     next_states.add(board.fen())
#                 except Exception:
#                     pass
#             self.possible_states = next_states if next_states else self.possible_states

#     def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
#                         game_history: GameHistory):
#         """
#         Called at the end of the game. Close the Stockfish connection.
#         """
#         try:
#             self.engine.quit()
#         except chess.engine.EngineTerminatedError:
#             pass




# -----------------------------------------------------------------------
# Improved Agent — Entropy Minimisation Sensing
# -----------------------------------------------------------------------

class ImprovedAgent(Player):
    def __init__(self):
        self.board = None
        self.color = None
        self.possible_states = set()
        self.engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        """
        Called at the start of the game. The starting position is known perfectly.
        Store it as the sole element of the belief state.
        """
        self.color = color
        self.board = board
        self.possible_states = {board.fen()}

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[chess.Square]):
        """
        Called after the opponent moves. Use capture information to narrow down
        the possible states by generating next states consistent with what happened.
        """
        next_states = set()

        for fen in self.possible_states:
            board = chess.Board(fen=fen)

            if captured_my_piece:
                # only keep states where a capture occurred on capture_square
                capture_square_name = chess.square_name(capture_square)
                next_states.update(generate_capture_states(board, capture_square_name))
            else:
                # keep all next states where no capture was made
                for next_fen in generate_next_states(board):
                    next_board = chess.Board(fen=next_fen)
                    # the last move pushed onto the board tells us if a capture happened
                    if next_board.move_stack and not next_board.is_capture(next_board.peek()):
                        next_states.add(next_fen)
                    elif not next_board.move_stack:
                        next_states.add(next_fen)

        self.possible_states = next_states

    def choose_sense(self, sense_actions: List[chess.Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Square]:
        non_edge = [
            sq for sq in sense_actions
            if chess.square_rank(sq) not in (0, 7) and chess.square_file(sq) not in (0, 7)
        ]
        if not non_edge:
            return random.choice(sense_actions)

        if not self.possible_states:
            return random.choice(non_edge)

        # sample at most 200 boards to keep computation fast
        sample = list(self.possible_states)
        if len(sample) > 200:
            sample = random.sample(sample, 200)

        best_square = None
        best_score = -1

        for sq in non_edge:
            # for each board in the sample, compute what the 3x3 window
            # around sq would look like — this is the observation signature
            observations = {}
            for fen in sample:
                board = chess.Board(fen=fen)
                window_sig = []
                for rank_offset in (-1, 0, 1):
                    for file_offset in (-1, 0, 1):
                        r = chess.square_rank(sq) + rank_offset
                        f = chess.square_file(sq) + file_offset
                        if 0 <= r <= 7 and 0 <= f <= 7:
                            piece = board.piece_at(chess.square(f, r))
                            window_sig.append(piece.symbol() if piece else '?')
                        else:
                            window_sig.append('-')
                sig = tuple(window_sig)
                observations[sig] = observations.get(sig, 0) + 1

            # more distinct observations = more informative sense square
            score = len(observations)
            if score > best_score:
                best_score = score
                best_square = sq

        return best_square
    
    def handle_sense_result(self, sense_result: List[Tuple[chess.Square, Optional[chess.Piece]]]):
        """
        Called with the 3x3 window observation after sensing.
        Use it to filter the belief state.
        """
        # convert sense_result into "square:piece;square:piece;..." format
        window_parts = []
        for square, piece in sense_result:
            square_name = chess.square_name(square)
            piece_symbol = piece.symbol() if piece else '?'
            window_parts.append(f'{square_name}:{piece_symbol}')
        window_description = ';'.join(window_parts)

        self.possible_states = set(filter_sensing_states(list(self.possible_states), window_description))

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        """
        Select a move using majority voting across all possible states.
        Time limit for Stockfish is 10/N where N is number of boards.
        Cap belief state at 10000 boards.
        """
        if not self.possible_states:
            return None

        states = self.possible_states
        if len(states) > 10000:
            states = set(random.sample(list(states), 10000))

        time_limit = 10 / len(states)
        votes = {}

        for fen in states:
            board = chess.Board(fen=fen)
            move = best_move(board, self.engine, time_limit)
            if move:
                key = str(move)
                votes[key] = votes.get(key, 0) + 1

        if not votes:
            return None

        best = max(sorted(votes.keys()), key=lambda m: votes[m])
        return chess.Move.from_uci(best)

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[chess.Square]):
        """
        Called after your move is executed. Update belief state based on
        the move that was actually taken.
        """
        if taken_move is not None:
            next_states = set()
            for fen in self.possible_states:
                board = chess.Board(fen=fen)
                try:
                    board.push(taken_move)
                    next_states.add(board.fen())
                except Exception:
                    pass
            self.possible_states = next_states if next_states else self.possible_states

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        """
        Called at the end of the game. Close the Stockfish connection.
        """
        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass