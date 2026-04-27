import chess
from reconchess.utilities import without_opponent_pieces, is_illegal_castle

board_state = input()
moves = set()
next_states = set()

board = chess.Board(fen=board_state)
moves.add('0000')

for move in board.pseudo_legal_moves:
    moves.add(move.uci())
    
for move in without_opponent_pieces(board).generate_castling_moves():
    if not is_illegal_castle(board, move):
        moves.add(move.uci())

for move in moves:
    next_board = board.copy()
    if move != '0000':
        next_board.push(move)
    next_states.add(next_board.fen())

for state in sorted(next_states):
    print(state)
