#!/usr/bin/env python3

import sys
import config
from common import flatten


def get_boards() -> list:
    """
    Get a list of "supported" boards from the Zephyr project.
    By supported we understand:
    - Not a virtual or posix platform
    - Supported CPU architecture

    Returns:
        list: A filtered list of Zephyr's board objects.
    """
    # the Zephyr utility has its own argument parsing, so avoid args clash
    sys.path.append(f"{config.project_path}/scripts")
    from list_boards import find_arch2boards
    from pathlib import Path

    class Args:
        arch_roots = [Path(config.project_path)]
        board_roots = [Path(config.project_path)]

    zephyr_boards = find_arch2boards(Args())
    flat_boards = flatten(zephyr_boards)

    # Filter QEMU and ARM Fixed Virtual Platforms
    flat_boards = dict(filter(lambda b: "qemu" not in b[0] and "native" not in b[0], flat_boards.items()))
    flat_boards = dict(filter(lambda b: not b[0].startswith("fvp_"), flat_boards.items()))

    boards_to_run = flat_boards.values()

    # Filter unsupported architectures
    omit_arch = ("arc", "posix")
    boards_to_run = filter(lambda x: all(map(lambda y: y != x.arch, omit_arch)), boards_to_run)

    # Filter out remaining boards that match the keywords
    omit_board = ("acrn", "qemu", "native", "nsim", "xenvm", "xt-sim")
    boards_to_run = list(filter(lambda x: all(map(lambda y: y not in x.name, omit_board)), boards_to_run))

    return [board.name for board in boards_to_run]


def generate_samples() -> None:
    """
    Generate combinations of boards and samples based on configuration file

    If sample has defined 'boards' key, only generate the samples for given boards,
    otherwise generate the sample for all boards
    """
    all_boards = get_boards()
    for board in all_boards:
        for sample, sample_data in config.samples.items():
            sample_boards = sample_data.get("boards", [board])
            if board in sample_boards:
                print(f"{board} {sample}")

if __name__ == "__main__":
    config.load()
    generate_samples()
