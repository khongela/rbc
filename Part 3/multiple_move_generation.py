import chess
import chess.engine
def best_move(board, engine):
    opponent_king_square = board.king(not board.turn)
    if opponent_king_square:
        attackers = board.attackers(board.turn, opponent_king_square)
        if attackers:
            attacker_square = attackers.pop()
            return chess.Move(attacker_square, opponent_king_square)
    #Stockfish
    try:
        board.clear_stack()
        result = engine.play(board, chess.engine.Limit(time=0.5))
        return result.move
    except chess.engine.EngineTerminatedError:
        print('Stockfish Engine died')
    except chess.engine.EngineError:
        print('Stockfish Engine bad state')

    engine.quit()
    
# engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True) # FOR LOCAL
engine = chess.engine.SimpleEngine.popen_uci('/opt/stockfish/stockfish', setpgrp=True)
n = int(input())
votes = {}

for _ in range(n):
    board = chess.Board(fen=input())
    move = best_move(board, engine)
    if move:
        key = str(move)
        votes[key] = votes.get(key, 0) + 1

# Find max votes first, then get min (alphabetically first) among ties
max_votes = max(votes.values())
result = min(move for move, count in votes.items() if count == max_votes)
print(result)

engine.quit()