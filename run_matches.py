import subprocess
import yaml
import shutil
import chess
import chess.engine
import time
import os
from pathlib import Path
from collections import defaultdict

WORKDIR = Path("./engine_workdir")


# -----------------------------
# utils
# -----------------------------

def run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def clone_and_build(engine):
    name = engine["name"]
    repo = engine["repo"]
    commit = engine["commit"]
    dir_path = engine["dir"]
    build_cmd = engine["build"]

    engine_path = WORKDIR / name

    if engine_path.exists():
        shutil.rmtree(engine_path)

    run(["git", "clone", repo, str(engine_path)])
    run(["git", "checkout", commit], cwd=engine_path)

    src_path = engine_path / dir_path
    run(build_cmd.split(), cwd=src_path)

    return str(src_path / engine["exec"])


# -----------------------------
# rendering
# -----------------------------

def clear():
    print("\033[H\033[J", end="")


def render(board, move_num, white_name, black_name, clocks, results):
    total = sum(results.values()) or 1

    clear()

    print("=== ENGINE MATCH ===\n")
    print(f"Move: {move_num}")
    print(f"White: {white_name} ({clocks[chess.WHITE]:.2f}s)")
    print(f"Black: {black_name} ({clocks[chess.BLACK]:.2f}s)\n")

    print(board)
    print("\n--- LIVE STATS ---")
    print(f"{white_name} wins: {results[white_name]} ({results[white_name]/total:.1%})")
    print(f"{black_name} wins: {results[black_name]} ({results[black_name]/total:.1%})")
    print(f"draws: {results['draw']} ({results['draw']/total:.1%})")


# -----------------------------
# game
# -----------------------------

def play_game(engine_a_path, engine_b_path, time_limit, max_plies, results, swap_colors=False, names=("A", "B")):

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

    board = chess.Board()
    move_num = 1

    try:
        while not board.is_game_over() and board.fullmove_number <= max_plies:

            render(board, board.fullmove_number, engine_names[0], engine_names[1], clocks, results)

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
                engine_a.quit()
                engine_b.quit()
                return "0-1" if board.turn == chess.WHITE else "1-0"

            elapsed = time.time() - start
            clocks[color] -= elapsed
            clocks[color] = max(0.0, clocks[color])

            board.push(move)

            if board.turn == chess.WHITE:
                move_num += 1

        render(board, board.fullmove_number, engine_names[0], engine_names[1], clocks, results)

        return board.result()

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
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    games = config["games"]
    time_per_game = config["time_per_game_seconds"]
    max_plies = config["max_plies"]
    engines_cfg = config["engines"]

    WORKDIR.mkdir(exist_ok=True)

    engine_paths = [clone_and_build(e) for e in engines_cfg]

    a_name = engines_cfg[0]["name"]
    b_name = engines_cfg[1]["name"]

    results = defaultdict(int)
    results[a_name] = 0
    results[b_name] = 0
    results["draw"] = 0

    for i in range(games):
        swap = (i % 2 == 1)

        result = play_game(
            engine_paths[0],
            engine_paths[1],
            time_per_game,
            max_plies,
            results,
            swap_colors=swap,
            names=(a_name, b_name)
        )

        if result == "1-0":
            winner = b_name if swap else a_name
        elif result == "0-1":
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