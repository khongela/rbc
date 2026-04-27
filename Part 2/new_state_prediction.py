import chess
from reconchess.utilities import without_opponent_pieces, is_illegal_castle
"""
The goal here is to make the new states using the make move function from earlier
"""
def generate_moves(board):
    moves = set()
    moves.add(chess.Move.null())
    for move in board.pseudo_legal_moves:
        moves.add(move)
    for move in without_opponent_pieces(board).generate_castling_moves():
        if not is_illegal_castle(board, move):
            moves.add(move.uci())
    return moves

def make_move(board, move):
    updated_board = board.copy()
    updated_board.push(move)
    updated_board = updated_board.fen()
    return updated_board

board = input()
board = chess.Board(fen=board)

for move in generate_moves(board):
    print(make_move(board,move))




