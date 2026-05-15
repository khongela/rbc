import chess
import chess.engine

def getPossibleMoves(board, captured_my_piece, capture_square):
    next_boards = set()
    for move in board.legal_moves:
        next_board = board.copy()
        next_board.push(move)

        #If a capture happened, we only want to keep boards where that capture is possible
        #Illegal move, don't add to next boards
        if captured_my_piece and board.is_capture(move) and move.to_square == capture_square :
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
        pass
    def choose_sense(self, sense_actions, move_actions, seconds_left):
    # write code here to select a sensing move
        pass
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