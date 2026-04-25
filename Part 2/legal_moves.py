import chess
from reconchess.utilities import without_opponent_pieces, is_illegal_castle

board_state = input()
board = chess.Board(fen=board_state)

moves = set()
moves.add('0000')
for move in board.pseudo_legal_moves:
    moves.add(move.uci())
    
for move in without_opponent_pieces(board).generate_castling_moves():
    if not is_illegal_castle(board, move):
        moves.add(move.uci())

for move in sorted(moves):
    print(move)
