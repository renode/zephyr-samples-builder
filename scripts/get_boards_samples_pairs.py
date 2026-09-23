#!/usr/bin/env python3

import os
import sys
import yaml
import config
from argparse import ArgumentParser


def get_yaml_identifiers(directory: str, filter_archs: list | None = None, filter_targets: list | None = None, suppress_output=True) -> dict:
    def dprint(*a, **k):
        if not suppress_output:
            print(*a, **k)

    all_boards = {}
    for root, dirs, files in os.walk(directory):
        # Reject bindings and configuration files
        if 'dts/bindings' in root or 'support' in root:
            continue
        for file in files:
            if file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    try:
                        data = yaml.safe_load(f)
                        if filter_archs and data['arch'] in filter_archs:
                            continue
                        if not os.path.isfile(os.path.join(root, "board.yml")):
                            # Reject the target if `root/board.yml` is missing.
                            # This covers an edge case where the `twister.yaml`
                            # file is located in the vendor directory tree; for
                            # example `mediatek/twister.yaml`.
                            continue
                        if 'identifier' in data:
                            identifier = data['identifier']
                            if filter_targets and any(target in identifier for target in filter_targets):
                                continue
                            all_boards[identifier] = root
                        elif 'variants' in data:
                            for identifier in data['variants'].keys():
                                if filter_targets and any(target in identifier for target in filter_targets):
                                    continue
                                all_boards[identifier] = root
                        else:
                            raise KeyError("unrecognized file structure")

                    except yaml.YAMLError as e:
                        dprint(f"Error reading {file_path}: {e}")
                    except KeyError as e:
                        dprint(f"KeyError in: {file_path}: {e}")
    return all_boards


def get_board_vendor(board_dir: str, board_name: str) -> str | None:
    """
    Retrieve the vendor of a board, as declared in its `board.yml`.

    Returns None if the vendor is not declared, in which case the board is not
    matched against the blacklist and gets built.
    """
    with open(f'{board_dir}/board.yml') as f:
        data = yaml.safe_load(f)

    if 'board' in data:
        # single board schema
        return data['board'].get('vendor')

    # multi-board schema with multiple boards
    sanitized_board = board_name.split('@')[0].split('/')[0]
    for board in data.get('boards', []):
        if board['name'] == sanitized_board:
            return board.get('vendor')

    return None


def generate_samples_from_yaml(blacklisted_vendors: set) -> None:
    """
    Generate combinations of boards and samples based on configuration file

    If sample has defined 'boards' key, only generate the samples for given boards,
    otherwise generate the sample for all boards
    """
    omit_arch = ["posix"]
    omit_target = ["nsim", "xenvm", "xt-sim", "fvp_"]
    directory_path = f'{config.project_path}/boards'
    identifiers = get_yaml_identifiers(directory_path, omit_arch, omit_target)
    for board, dir in identifiers.items():
        vendor = get_board_vendor(dir, board)
        if vendor in blacklisted_vendors:
            print(f"Ignoring blacklisted board: {board} (vendor: {vendor})", file=sys.stderr)
            continue

        for sample, sample_data in config.samples.items():
            sample_boards = sample_data.get("boards", [board])
            if board in sample_boards:
                print(f"{dir} {board} {sample}")


if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("--vendor-blacklist", help="File listing vendors to skip, one per line")
    args, _ = ap.parse_known_args()

    blacklisted_vendors = set()
    if args.vendor_blacklist:
        with open(args.vendor_blacklist) as f:
            blacklisted_vendors = {line.strip() for line in f if line.strip()}

    config.load()
    generate_samples_from_yaml(blacklisted_vendors)
