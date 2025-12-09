#!/usr/bin/env python3

import os
import yaml
import config


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


def generate_samples_from_yaml() -> None:
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
        for sample, sample_data in config.samples.items():
            sample_boards = sample_data.get("boards", [board])
            if board in sample_boards:
                print(f"{dir} {board} {sample}")


if __name__ == "__main__":
    config.load()
    generate_samples_from_yaml()
