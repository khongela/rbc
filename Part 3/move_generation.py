import chess
import chess.engine

board = chess.Board(fen=input())

# engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)
engine = chess.engine.SimpleEngine.popen_uci('/opt/stockfish/stockfish', setpgrp=True)
opponent_king_square = board.king(not board.turn)
if opponent_king_square:
    attackers = board.attackers(board.turn, opponent_king_square)
    if attackers:
        attacker_square = attackers.pop()
        print(chess.Move(attacker_square, opponent_king_square))
        engine.quit()
        exit()

#Stockfish
try:
    board.clear_stack()
    result = engine.play(board, chess.engine.Limit(time=0.5))
    print(result.move)
except chess.engine.EngineTerminatedError:
    print('Stockfish Engine died')
except chess.engine.EngineError:
    print('Stockfish Engine bad state')

engine.quit()