import random
from reconchess import *
from reconchess.utilities import without_opponent_pieces, is_illegal_castle


class BoardFunctions:
    def generate_valid_boards(board: chess.Board) -> set:
        """
        Generate all possible next boards after opponent move.
        """
        next_boards = set()

        for move in board.legal_moves:
            new_board = board.copy()
            new_board.push(move)
            next_boards.add(new_board)

        return next_boards


class RandomBot(Player):

    def __init__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci('../engine/stockfish-windows-x86-64-avx2.exe')
        self.boards = [] 
        self.color = None
        self.opponent_name = None

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.boards = []
        board_copy = board.copy(stack=True)
        self.boards.append(board_copy)
        self.color = color
        self.opponent_name = opponent_name

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
        """
        We update our possible game states after the opponent moves.
        For each board we think could be correct, we simulate all legal opponent moves
        and generate the resulting boards.
        We remove any possibilities that don’t match what actually happened
        (for example whether a capture occurred or not).
        Finally, we replace our old set of boards with this updated set.
        """
        
        new_boards = set()

        for board in self.boards:
            possible_moves = BoardFunctions.generate_valid_moves(board)
            for move in possible_moves:
                if captured_my_piece:
                    if move.to_square != capture_square:
                        continue

            if not captured_my_piece:
                if board.is_capture(move):
                    continue

            new_board = board.copy()
            new_board.push(move)

            new_boards.add(new_board)

        self.boards = new_boards

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
            Optional[Square]:
        return random.choice(sense_actions)

    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        pass

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        return random.choice(move_actions + [None])

    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                           captured_opponent_piece: bool, capture_square: Optional[Square]):
        pass

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        pass