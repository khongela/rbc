import chess
import chess.engine
import random
from reconchess import *
from typing import List, Optional, Tuple

import os; STOCKFISH_PATH = os.environ.get('STOCKFISH_EXECUTABLE', r'./stockfish')
MAX_BOARD_COUNT = 10000
MIN_TIME_LIMIT = 0.001 


def getPossibleBoardStates(board, captured_my_piece, capture_square):
    next_boards = set()
    for move in board.legal_moves:
        if captured_my_piece:
            if not board.is_capture(move):
                continue
            
            #TODO: Consider en passant capture case where the capture square is different from the move to square - chess is weird
            expected_capture_square = move.to_square
            if capture_square is not None and expected_capture_square != capture_square:
                continue
        else:
            if board.is_capture(move):
                continue

        next_board = board.copy()
        next_board.push(move)
        next_boards.add(next_board.fen())
    return next_boards

#Part 3 Move Generation Karabo
def best_move(board, engine, time_limit=0.1):
    opponent_king_square = board.king(not board.turn)
    if opponent_king_square:
        attackers = board.attackers(board.turn, opponent_king_square)
        if attackers:
            attacker_square = attackers.pop()
            return chess.Move(attacker_square, opponent_king_square)
    #Stockfish
    try:
        board.clear_stack()
        result = engine.play(board, chess.engine.Limit(time=time_limit))
        return result.move
    except chess.engine.EngineTerminatedError:
        print('Stockfish Engine died')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state')
    return None

def isBlockConsistent(board, block : Tuple[Square, Optional[chess.Piece]]):
    square, piece = block
    if board.piece_at(square) != piece:
        return False
    return True

class ImprovedAgent(Player):

    def __init__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH, setpgrp=True)
        self.boards = set() #Use FEN string representation for hashing and deduplication - performance improvement. 
        self.color = None

    def handle_game_start(self, color: chess.Color, board: chess.Board, opponent_name: str):
    # function that is run when the game starts
        self.boards = {board.fen()}
        self.color = color

    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: chess.Square):
    # feedback on whether the opponent captured a piece
        next_boards = set()

        for board in self.boards:
            new_boards = getPossibleBoardStates(chess.Board(board), captured_my_piece, capture_square)
            next_boards.update(new_boards)

        if next_boards:
            self.boards = next_boards

#TODO: Improvements
    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        if not self.boards:
            return random.choice(sense_actions)

        board = next(iter(self.boards))
        available_sense_actions = list(sense_actions)

        for square, piece in chess.Board(board).piece_map().items():
            if piece.color == self.color:
                if square in available_sense_actions:
                    available_sense_actions.remove(square)

        return random.choice(available_sense_actions or sense_actions)
    
    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
    # This is where the sensing result returns feedback
        next_boards = set()

        for board in self.boards:
            b = chess.Board(board)
            consistent = True
            for block in sense_result:
                if not isBlockConsistent(b, block):
                    consistent = False
                    break
            if consistent:
                next_boards.add(board)

        if next_boards:
            self.boards = next_boards

    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
    # execute a chess move
        if not self.boards:
            return random.choice(move_actions)

        if self.engine is None:
            return random.choice(move_actions)

        N = len(self.boards)
        if N > MAX_BOARD_COUNT:
            self.boards = set(random.sample(list(self.boards), MAX_BOARD_COUNT))
            N = MAX_BOARD_COUNT
        
        votes = {}
        # TODO: Use seconds_left to dynamically adjust time limit
        time_limit = max(10.0/N if N > 0 else 1, MIN_TIME_LIMIT)
        
        for board in self.boards:
            move = best_move(chess.Board(board), self.engine, time_limit) # Turned into separate function for readability(Consistent with Jack's code as well)
            if move and move in move_actions: # Adapted form Jack's code for random_sensing agent
                key = str(move)
                votes[key] = votes.get(key, 0) + 1
            
        if not votes:
            return random.choice(move_actions + [chess.Move.null()])
        
        max_votes = max(votes.values())
        result = min(move for move, count in votes.items() if count == max_votes)

        return chess.Move.from_uci(result)

    def handle_move_result(self, requested_move, taken_move, captured_opponent_piece, capture_square):
    # this function is called after your move is executed.
    #  Note that the move requested and the move actually executed may differ 
        next_boards = set()

        for board in self.boards:
            b = chess.Board(board)

            if taken_move is None:
                if requested_move in b.legal_moves:
                    continue
                else:
                    b.push(chess.Move.null())
                    next_boards.add(b.fen())
            else:
                if taken_move not in b.legal_moves:
                    continue

                if captured_opponent_piece:
                    if not b.is_capture(taken_move) or capture_square is None:
                        continue

                    #TODO: en passant capture case to be considered - capture square is different from move to square - chess is weird
                    # if b.is_en_passant(taken_move):
                    #     expected_capture_square = chess.square(chess.square_file(taken_move.to_square), chess.square_rank(taken_move.from_square))

                    expected_capture_square = taken_move.to_square
                    if expected_capture_square != capture_square:
                        continue
                else:
                    if b.is_capture(taken_move):
                        continue


                next_b = b.copy()
                next_b.push(taken_move)
                next_boards.add(next_b.fen())

                
                ##### SANITY CHECK - I AM LOSING MY TRAIN OF THOUGHT - PLEASE REVIEW THIS LOGIC CAREFULLY
                # If taken move IS NOT none - Check boards under consideration for consistency with the taken move and capture feedback, and update boards accordingly.
                
                ### Case 1: Requested move is the taken move (simple)
                    ### Keep it only if it was in boards legal moves
                    ### And if we captured an opponent piece, then it should be a capture in the board's legal moves, and if we didn't capture an opponent piece, then it should not be a capture in the board's legal moves.
                    ### Apply either_requested or taken_move (same in this case) to that board
                ### Case 2: Requested move is NOT taken move (Adjusted since it is not none)
                    ### Keep it if in the pseudo legal moves
                    ### apply the taken_move to that board


                # If taken move IS none
                ### Case 1: Requested move is null move
                    ### Apply null move to that board and keep it

                ### Case 2: Requested move is not null move but was legal in that board 
                    ### Discard that board since we know the requested move was not executed, meaning it was actually an illegal move in the real board

              ### My thinking says check that the move taken and capture feedback is consistent with requested_move on the board under consideration

        if next_boards:
            self.boards = next_boards
    
    def handle_game_end(self, winner_color, win_reason, game_history):
        # shut down everything at the end of the game
        if self.engine is None:
            return

        try:
            # if the engine is already terminated then this call will throw an exception
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass
