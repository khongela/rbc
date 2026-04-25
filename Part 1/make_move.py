import chess
"""
https://python-chess.readthedocs.io/en/latest/
"""
board_state = input()
move = input()

board = chess.Board(board_state)
move = chess.Move.from_uci(move)
board.push(move)

print(board.fen())