import chess

#White pieces in UpperCase, Black in LowerCase, Empty Square ?
num_states = int(input())
board_states = []
for n in range(num_states):
    board_state = input()
    board_states.append(board_state)
window_discription = input()

window= {}
for box in window_discription.split(';'):
    location, piece = box.split(':', 1)
    window[location] = piece

valid_states = []

for board_state in board_states:
    # Check if the window description is consistent with the board state
    board = chess.Board(fen=board_state)

    consistent = True
    for location, observed_piece in window.items():
        #Find the piece at the given location according to the board state
        piece = board.piece_at(chess.parse_square(location))
        piece = piece.symbol() if piece else '?'
        if piece != observed_piece:
            consistent = False
            break
    if consistent:
        valid_states.append(board_state)

for state in sorted(valid_states):
    print(state)
    