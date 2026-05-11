from reconchess import play_local_game
from reconchess.bots.random_bot import RandomBot
from reconchess.bots.trout_bot import TroutBot
from random_sensing import RandomSensing
import os
def run_tournament():
    os.environ['STOCKFISH_EXECUTABLE'] = '../engine/stockfish-windows-x86-64-avx2.exe'
    my_bot = RandomSensing()
    random_bot = RandomBot()
    trout_bot = TroutBot()

    print("Game 1: RandomSensing (White) vs RandomBot (Black)")
    winner, _, _ = play_local_game(my_bot, random_bot)
    print(f"Winner: {winner}")

    print("Game 2: TroutBot (White) vs RandomSensing (Black)")
    winner, _, _ = play_local_game(trout_bot, my_bot)
    print(f"Winner: {winner}")

run_tournament()