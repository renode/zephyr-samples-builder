#!/usr/bin/env python3

import json
import requests
import config
from common import (
    bold
)


def get_remote_json(version: str | None = None) -> dict:
    """
    Retrieves a remote JSON from a specified version or latest version if none is specified.

    Args:
        version (str | None): The version of the JSON to retrieve. If None, retrieves the latest version.

    Returns:
        dict: The retrieved JSON as a dictionary.
    """
    BASE = "https://storage.googleapis.com/zephyr-samples-builder/zephyr"
    s = requests.Session()

    if version is None:
        version = s.get(f"{BASE}/latest").text.strip()

    return s.get(f"{BASE}/{version}/result.json").json()


def json_sample_diff(sample: str, remote_json: dict, local_json: dict) -> tuple[dict, dict, dict]:
    """
    Compares local and remote JSON and returns changed, added and removed elements.

    Args:
        sample (str): The sample to compare for.
        remote_json (dict): The remote JSON structure.
        local_json (dict): The local JSON structure.

    Returns:
        tuple[dict, dict, dict]: A tuple containing dictionaries of changed, added and removed elements.
    """
    changed = {}
    added = {}
    removed = {}
    for target in remote_json.keys() | local_json.keys():
        try:
            remote_status = remote_json[target]["samples"][sample]
        except KeyError:
            remote_status = None

        try:
            local_status = local_json[target]["samples"][sample]
        except KeyError:
            local_status = None

        if local_status != remote_status:
            category = added if remote_status is None else removed if local_status is None else changed
            category[target] = (remote_status, local_status)

    return changed, added, removed


def main() -> None:
    with open("build/result.json", "r") as f:
        local_results = json.load(f)

    try:
        remote_results = get_remote_json()
    except Exception as e:
        print(f'Failed to get remote JSON, quitting!\n{e}')
        exit(0)

    for sample in config.samples:
        changed, added, removed = json_sample_diff(sample, remote_results, local_results)

        print(80 * '-')
        if all(not var for var in (changed, added, removed)):
            print(f"No status changes for sample: {bold(sample)}")
            continue
        else:
            print(f"Status changes for sample: {bold(sample)}")
            for k, v in changed.items():
                print(f"{k}: {v[0]} -> {v[1]}")

            for k, v in added.items():
                print(f"{k}: {v[0]} -> {v[1]}")

            for k, v in removed.items():
                print(f"{k}: {v[0]} -> {v[1]}")
        print(80 * '-', '\n')


if __name__ == "__main__":
    config.load()
    main()
