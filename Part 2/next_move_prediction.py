import chess
from reconchess.utilities import without_opponent_pieces, is_illegal_castle

"""
https://reconchess.readthedocs.io/en/latest/reconchess.html
"""

board_state = input()
moves = set()
<<<<<<< HEAD:Part 2/next_move_prediction.py
moves.add(chess.Move.null())
=======

board = chess.Board(fen=board_state)
moves.add('0000')

>>>>>>> cbb586ee359c0f3ebf0331508f3ad2d8db7d41c2:Part 2/legal_moves.py
for move in board.pseudo_legal_moves:
    moves.add(move.uci())
    
for move in without_opponent_pieces(board).generate_castling_moves():
    if not is_illegal_castle(board, move):
        moves.add(move.uci())

for move in sorted(moves):
    print(move)
