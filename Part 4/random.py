from typing import List, Optional

import chess
import chess.engine
import random
from reconchess import *

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

def isBlockConsistent(board, block : Tuple[Square, Optional[chess.Piece]]):
    if board.piece_at(block.square) != block.piece:
        return False
    return True

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

    engine.quit()


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

# Implement sensing randomly
# TO DO: Improve this based on the paper suggested in Assigment Doc: The Second NeurIPS Tournament of Reconnaissance Blind Chess
    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        for square, piece in self.board.piece_map().items():
            if piece.color == self.color:
                sense_actions.remove(square)
        return random.choice(sense_actions)
    
    def handle_sense_result(self, sense_result):
    # This is where the sensing result returns feedback
        next_boards = set()

        for board in self.boards:
            consistent = True
            for block in sense_result:
                if not isBlockConsistent(board, block):
                    consistent = False
                    break
            if consistent:
                next_boards.add(board)

        self.boards = next_boards


    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
    # execute a chess move
        if not self.boards:
            return random.choice(move_actions)

        if len(self.boards) > 10000:
            self.boards = set(random.sample(list(self.boards), 10000))
        
        votes = {}
        N = len(self.boards)
        time_limit = 10/N if N > 0 else 1
        
        for board in self.boards:
            move = best_move(board, self.engine, time_limit)
            if move:
                key = str(move)
                votes[key] = votes.get(key, 0) + 1
            
        # Find max votes first, then get min (alphabetically first) among ties
        if not votes:
            return random.choice(move_actions)
        max_votes = max(votes.values())
        result = min(move for move, count in votes.items() if count == max_votes)
        return chess.Move.from_uci(result)
            

    def handle_move_result(self, requested_move, taken_move, captured_opponent_piece, capture_square):
    # this function is called after your move is executed.
    #  Note that the move requested and the move actually executed may differ 

    # Possible outcomes for the move: 1. Move is legal and executed - simple move or a capture 2. Move is illegal and no move executed
        next_boards = set()

        for board in self.boards:
            if taken_move is None:
                if taken_move in board.legal_moves:
                    continue
                next_boards.add(board)
            else:
                if taken_move not in board.legal_moves: # Was executed thus is a legal move, but not in this board's possibilities thus this board is not possible
                    continue
                if captured_opponent_piece and not board.is_capture(taken_move): # Move was capture, but this board doesn't reflect that move as a capture
                    continue
                if not captured_opponent_piece and board.is_capture(taken_move): # Move was not a capture, but this board reflects it as a capture
                    continue

                next_board = board.copy()
                next_board.push(taken_move)
                next_boards.add(next_board)
        self.boards = next_boards

    def handle_game_end(self, winner_color, win_reason, game_history):
        # shut down everything at the end of the game
        try:
            # if the engine is already terminated then this call will throw an exception
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass