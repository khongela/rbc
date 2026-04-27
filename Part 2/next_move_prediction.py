import chess
from reconchess.utilities import without_opponent_pieces, is_illegal_castle

"""
https://reconchess.readthedocs.io/en/latest/reconchess.html
"""

board_state = input()
board = chess.Board(fen=board_state)

moves = set()
moves.add(chess.Move.null())
for move in board.pseudo_legal_moves:
    moves.add(move.uci())
    
for move in without_opponent_pieces(board).generate_castling_moves():
    if not is_illegal_castle(board, move):
        moves.add(move.uci())

for move in sorted(moves):
    print(move)
