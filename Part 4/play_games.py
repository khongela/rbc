import os
import csv
from itertools import combinations

import chess
import matplotlib.pyplot as plt
from reconchess import play_local_game
from reconchess.bots.random_bot import RandomBot
from reconchess.bots.trout_bot import TroutBot

from random_sensing import RandomSensing
from improved_agent import ImprovedAgent


os.environ['STOCKFISH_EXECUTABLE'] = '../engine/stockfish-windows-x86-64-avx2.exe'


agents = {
    'RandomBot': RandomBot,
    'TroutBot': TroutBot,
    'RandomSensing': RandomSensing,
    'ImprovedAgent': ImprovedAgent,
}


def play_game(white_name, black_name):
    print()
    print(f'{white_name} (White) vs {black_name} (Black)', flush=True)

    white_bot = agents[white_name]()
    black_bot = agents[black_name]()

    winner_color, _, _ = play_local_game(white_bot, black_bot)

    if winner_color == chess.WHITE:
        winner_name = white_name
    elif winner_color == chess.BLACK:
        winner_name = black_name
    else:
        winner_name = None

    print(f'Winner: {winner_name}', flush=True)

    return winner_name


def make_table(stats):
    table_data = []

    for name in ['ImprovedAgent', 'TroutBot', 'RandomSensing', 'RandomBot']:
        wins = stats[name]['wins']
        losses = stats[name]['losses']
        total = wins + losses

        if total == 0:
            win_rate = 0
        else:
            win_rate = (wins / total) * 100

        table_data.append([
            name,
            wins,
            losses,
            f'{win_rate:.1f}%'
        ])

    return table_data


def save_matplotlib_table(table_data):
    columns = ['Agent', 'Wins', 'Losses', 'Win Rate']

    fig, ax = plt.subplots(figsize=(8, 2.5))
    ax.axis('off')

    table = ax.table(
        cellText=table_data,
        colLabels=columns,
        loc='center',
        cellLoc='center'
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    plt.savefig('tournament_table.png', bbox_inches='tight', dpi=300)
    plt.close()


def save_csv(table_data):
    with open('tournament_results.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Agent', 'Wins', 'Losses', 'Win Rate'])
        writer.writerows(table_data)


def print_latex_rows(table_data):
    print()
    print('LaTeX table rows:')
    print('-----------------')

    for row in table_data:
        print(f'{row[0]} & {row[1]} & {row[2]} & {row[3]} \\\\')


def run_tournament():
    stats = {}

    for name in agents:
        stats[name] = {
            'wins': 0,
            'losses': 0
        }

    for agent_one, agent_two in combinations(agents.keys(), 2):
        winner = play_game(agent_one, agent_two)

        if winner is not None:
            loser = agent_two

            if winner == agent_two:
                loser = agent_one

            stats[winner]['wins'] += 1
            stats[loser]['losses'] += 1

        winner = play_game(agent_two, agent_one)

        if winner is not None:
            loser = agent_one

            if winner == agent_one:
                loser = agent_two

            stats[winner]['wins'] += 1
            stats[loser]['losses'] += 1

    table_data = make_table(stats)

    save_csv(table_data)
    save_matplotlib_table(table_data)
    print_latex_rows(table_data)

    print()
    print('Saved tournament_results.csv')
    print('Saved tournament_table.png')


run_tournament()