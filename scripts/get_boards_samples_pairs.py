#!/usr/bin/env python3

import os
import yaml
import config


def get_yaml_identifiers(directory: str, suppress_output=True) -> dict:
    def dprint(*a, **k):
        if not suppress_output:
            print(*a, **k)

    all_boards = {}
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    try:
                        data = yaml.safe_load(f)
                        all_boards[data['identifier']] = root
                    except yaml.YAMLError as e:
                        dprint(f"Error reading {file_path}: {e}")
                    except KeyError as e:
                        dprint(f"No identifier key in: {file_path}: {e}")
    return all_boards


def generate_samples_from_yaml() -> None:
    """
    Generate combinations of boards and samples based on configuration file

    If sample has defined 'boards' key, only generate the samples for given boards,
    otherwise generate the sample for all boards
    """
    directory_path = f'{config.project_path}/boards'
    identifiers = get_yaml_identifiers(directory_path)
    for board, dir in identifiers.items():
        for sample, sample_data in config.samples.items():
            sample_boards = sample_data.get("boards", [board])
            if board in sample_boards:
                print(f"{dir} {board} {sample}")


if __name__ == "__main__":
    config.load()
    generate_samples_from_yaml()
