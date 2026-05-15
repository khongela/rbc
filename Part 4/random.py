import chess
import chess.engine

def getPossibleBoardStates(board, captured_my_piece, capture_square):
    next_boards = set()
    for move in board.legal_moves:
        next_board = board.copy()
        next_board.push(move)

        #If a capture happened, we only want to keep boards where that capture is possible
        #Illegal move, don't add to next boards
        if captured_my_piece and not (board.is_capture(move) and move.to_square == capture_square):
            continue
        next_boards.add(next_board)
    return next_boards

class RandomSensing(Player):
    def __init__(self):
    # setup agent as you see fit
        self.engine = chess.engine.SimpleEngine.popen_uci('/opt/stockfish/stockfish', setpgrp=True)
        self.boards = set()
        self.color = None

    def handle_game_start(self, color: chess.Color, board: chess.Board, opponent_name: str):
    # function that is run when the game starts
        self.boards = {board.copy()}
        self.color = color

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: chess.Square):
    # feedback on whether the opponent captured a piece

    # Generate a set of possible boards after opponent's move for each possible board under considering
        next_boards = set()

        for board in self.boards:
            new_boards = getPossibleBoardStates(board, captured_my_piece, capture_square)
            next_boards.update(new_boards)

        if not next_boards:
            self.boards = self.boards
        else:
            self.boards = next_boards

# Implement sensing how Trout bot chooses to sense
# TO DO: Improve this based on the paper suggested in Assigment Doc: The Second NeurIPS Tournament of Reconnaissance Blind Chess
    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
            Optional[Square]:
        # if our piece was just captured, sense where it was captured
        if self.my_piece_captured_square:
            return self.my_piece_captured_square

        # if we might capture a piece when we move, sense where the capture will occur
        future_move = self.choose_move(move_actions, seconds_left)
        if future_move is not None and self.board.piece_at(future_move.to_square) is not None:
            return future_move.to_square

        # otherwise, just randomly choose a sense action, but don't sense on a square where our pieces are located
        for square, piece in self.board.piece_map().items():
            if piece.color == self.color:
                sense_actions.remove(square)
        return random.choice(sense_actions)
    
    def handle_sense_result(self, sense_result):
    # This is where the sensing result returns feedback
        pass
    def choose_move(self, move_actions, seconds_left):
    # execute a chess move
        pass
    def handle_move_result(self, requested_move, taken_move, captured_opponent_piece, capture_square):
    # this function is called after your move is executed.
        pass
    def handle_game_end(self, winner_color, win_reason, game_history):
        # shut down everything at the end of the game
        pass