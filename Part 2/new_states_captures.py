import chess

board_state = input()
capture_block = input()
next_states = set()

board = chess.Board(fen=board_state)

for move in board.pseudo_legal_moves:
    if move.uci().endswith(capture_block) and board.is_capture(move):
        next_board = board.copy()
        next_board.push_uci(move.uci())
        next_states.add(next_board.fen())
    

for state in sorted(next_states):
    print(state)
