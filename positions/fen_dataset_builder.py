# positions/fen_dataset_builder.py

import chess
import chess.pgn
import chess.engine
import random
import sys

"""
Searches through the PGN_DATABASE, filtering for positions that are *roughly equal*.

We define a position p with evaluation e to be *roughly equal* if -0.5 <= e <= 0.5.
"""

PGN_DATABASE = "./lichess_db_standard_rated_2013-01.pgn"
NUM_POS_TO_SCAN = 100000

stockfish = chess.engine.SimpleEngine.popen_uci("./stockfish/src/stockfish")

pgn_db = open(PGN_DATABASE)

roughly_equal = []

for i in range(NUM_POS_TO_SCAN):
    sys.stdout.write(f"\rProgress: {i + 1} / {NUM_POS_TO_SCAN}")

    game = chess.pgn.read_game(pgn_db)

    if game == None:
        print("Game is empty")
        continue

    moves = game.mainline_moves()
    board = game.board()

    random_ply_count = random.randint(10, 20) & ~1

    fen = None
    for i, move in enumerate(moves):
        board.push(move)
        if i == random_ply_count:
            fen = board.fen()

    if not fen:
        continue

    eval = stockfish.analyse(chess.Board(fen), chess.engine.Limit(depth=10)).get('score')

    if not eval:
        continue

    eval_score = eval.relative.score()

    if eval_score and abs(eval_score) <= 50:
        roughly_equal.append(fen.split())

stockfish.quit()

pgn_db.close()

seen = {}

for l in roughly_equal:
    if l[0] not in seen:
        seen[l[0]] = " ".join(l) + "\n"

with open("./output.txt", "w") as out:
    out.writelines(list(seen.values()))

print(f"\nTotal no. of roughly equal positions: {len(seen.values())}")
