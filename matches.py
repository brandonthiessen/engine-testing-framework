import subprocess
import yaml
import shutil
import chess
import chess.engine
import time
import os
import random
import argparse
from pathlib import Path
from collections import defaultdict

WORKDIR = Path("./engine_workdir")


# -----------------------------
# utils
# -----------------------------

def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_and_build(engine, no_clone=False, no_build=False):
    name = engine["name"]
    repo = engine["repo"]
    commit = engine["commit"]
    dir_path = engine["dir"]
    build_cmd = engine["build"]

    engine_path = WORKDIR / name

    if not no_clone:
        if engine_path.exists():
            shutil.rmtree(engine_path)

        run(["git", "clone", repo, str(engine_path)])
        run(["git", "checkout", commit], cwd=engine_path)

    src_path = engine_path / dir_path

    if not no_build:
        run(build_cmd.split(), cwd=src_path)

    return str(src_path / engine["exec"])


# -----------------------------
# position loading
# -----------------------------

def load_positions(positions_file, num_positions=500):
    with open(positions_file, "r") as f:
        all_positions = [line.strip() for line in f if line.strip()]

    if len(all_positions) < num_positions:
        print(f"Warning: requested {num_positions} positions but only {len(all_positions)} available")
        return all_positions

    return random.sample(all_positions, num_positions)


# -----------------------------
# rendering
# -----------------------------

def clear():
    print("\033[H\033[J", end="")


def render(board, move_num, white_name, black_name, clocks, results, game_num, total_games):
    total = sum(results.values()) or 1

    clear()

    print("=== ENGINE MATCH ===\n")
    print(f"Game: {game_num}/{total_games}")
    print(f"Move: {move_num}\n")

    print(f"Black: {black_name}\n")
    print(board)
    print(f"\nWhite: {white_name}\n")

    print(f"{white_name}: {results[white_name]} wins")
    print(f"{black_name}: {results[black_name]} wins")
    print(f"draws: {results['draw']}")
    print()


# -----------------------------
# result helper (IMPORTANT FIX)
# -----------------------------

def get_result_from_board(board, white_name, black_name):
    """
    Always derive result from actual board state.
    """
    outcome = board.outcome(claim_draw=True)

    if outcome is None:
        return "draw"

    if outcome.winner is None:
        return "draw"

    return "white" if outcome.winner == chess.WHITE else "black"


# -----------------------------
# game
# -----------------------------

def play_game(engine_a_path, engine_b_path, time_limit, max_plies, results,
              fen, swap_colors=False, names=("A", "B"),
              game_num=1, total_games=1):

    engine_a = chess.engine.SimpleEngine.popen_uci(engine_a_path)
    engine_b = chess.engine.SimpleEngine.popen_uci(engine_b_path)

    engines = [engine_a, engine_b]
    engine_names = list(names)

    if swap_colors:
        engines = [engine_b, engine_a]
        engine_names = [names[1], names[0]]

    clocks = {
        chess.WHITE: time_limit,
        chess.BLACK: time_limit
    }

    board = chess.Board(fen)

    try:
        while not board.is_game_over(claim_draw=True) and board.fullmove_number <= max_plies:

            render(board, board.fullmove_number,
                   engine_names[0], engine_names[1],
                   clocks, results,
                   game_num, total_games)

            engine = engines[board.turn == chess.BLACK]
            color = board.turn

            start = time.time()

            try:
                result = engine.play(
                    board,
                    chess.engine.Limit(
                        white_clock=clocks[chess.WHITE],
                        black_clock=clocks[chess.BLACK],
                    )
                )

                move = result.move

                if move not in board.legal_moves:
                    raise chess.engine.EngineError(f"Illegal move: {move}")

            except Exception:
                # illegal move or crash => loss for side to move
                outcome = "black" if board.turn == chess.WHITE else "white"
                return outcome

            elapsed = time.time() - start
            clocks[color] -= elapsed
            clocks[color] = max(0.0, clocks[color])

            board.push(move)

        # FINAL RESULT FROM BOARD STATE ONLY
        result = get_result_from_board(board, *engine_names)

        render(board, board.fullmove_number,
               engine_names[0], engine_names[1],
               clocks, results,
               game_num, total_games)

        return result

    finally:
        try:
            engine_a.quit()
        except:
            pass
        try:
            engine_b.quit()
        except:
            pass


# -----------------------------
# main
# -----------------------------

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--no-clone", action="store_true")
    parser.add_argument("--no-build", action="store_true")

    args = parser.parse_args()

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    positions_file = config.get("positions_file", "positions/positions.txt")
    num_positions = config.get("num_positions", 500)
    time_per_game = config["time_per_game_seconds"]
    max_plies = config["max_plies"]
    engines_cfg = config["engines"]

    WORKDIR.mkdir(exist_ok=True)

    positions = load_positions(positions_file, num_positions)
    total_games = len(positions) * 2

    engine_paths = [
        clone_and_build(e, no_clone=args.no_clone, no_build=args.no_build)
        for e in engines_cfg
    ]

    a_name = engines_cfg[0]["name"]
    b_name = engines_cfg[1]["name"]

    results = defaultdict(int)
    results[a_name] = 0
    results[b_name] = 0
    results["draw"] = 0

    game_counter = 0

    for fen in positions:
        for swap in [False, True]:
            game_counter += 1

            result = play_game(
                engine_paths[0],
                engine_paths[1],
                time_per_game,
                max_plies,
                results,
                fen=fen,
                swap_colors=swap,
                names=(a_name, b_name),
                game_num=game_counter,
                total_games=total_games
            )

            if result == "white":
                winner = b_name if swap else a_name
            elif result == "black":
                winner = a_name if swap else b_name
            else:
                winner = "draw"

            results[winner] += 1

    print("\n=== FINAL RESULTS ===")
    total = sum(results.values())

    print(f"{a_name}: {results[a_name]} ({results[a_name]/total:.1%})")
    print(f"{b_name}: {results[b_name]} ({results[b_name]/total:.1%})")
    print(f"draws: {results['draw']} ({results['draw']/total:.1%})")


if __name__ == "__main__":
    main()
