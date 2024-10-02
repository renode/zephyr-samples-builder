#!/usr/bin/env python3

import csv
import os
import json
import config
import jinja2
from common import get_versions

# Setup Jinja2 environment
template_loader = jinja2.FileSystemLoader(searchpath="./")
template_env = jinja2.Environment(loader=template_loader)
summary_template = template_env.get_template("templates/summary.md")


def aggregate_json_files(directory: str) -> list:
    """
    Aggregate data from JSON files in the given directory

    Args:
        directory (str): The directory containing JSON files

    Returns:
        list: List of aggregated JSON data
    """
    aggregated_data = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith("-result.json"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as f:
                    data = json.load(f)
                    aggregated_data.append(data)
    return aggregated_data


def generate_stats(data: list) -> dict:
    """
    Generate statistics based on aggregated JSON data

    Args:
        data (list): List of aggregated JSON data

    Returns:
        dict: Dictionary containing built, built with extended memory
              and failed statistics
    """
    built = 0
    built_ext = 0
    failed = 0

    for result in data:
        if result["success"]:
            if result["extended_memory"]:
                built_ext += 1
            else:
                built += 1
        else:
            failed += 1

    return {
        "built": built,
        "built_ext": built_ext,
        "failed": failed,
    }


def process_sample_data(aggregated_jsons: list) -> dict:
    """
    Process aggregated build result data into a dictionary organized by sample names.

    Args:
        aggregated_jsons (list): A list of dictionaries containing aggregated build result data.
            Each dictionary should contain information about a build result.

    Returns:
        dict: A dictionary where keys are sample names and values are lists of build result items
            sorted by 'platform' value within each list.
    """
    sample_dict = {}

    # Generate and fill dict keys
    for build_result in aggregated_jsons:
        sample_name = build_result['sample_name']
        if sample_name not in sample_dict:
            sample_dict[sample_name] = []
        sample_dict[sample_name].append(build_result)

    # Sort the items in each list by 'platform'
    for sample_name, items in sample_dict.items():
        sample_dict[sample_name] = sorted(items, key=lambda x: x['platform'])

    return sample_dict


def soc_info(dts_chain):
    if not dts_chain and not len(dts_chain):
        return ''

    dts_chain_filtered = [el.lstrip('!') for el in dts_chain if "!skeleton" not in el]  # remove all '!skeleton' entries, strip every '!' from other
    dts_chain_filtered = list(dict.fromkeys(dts_chain_filtered))  # delete duplicates

    r = {
        'arm/armv': 'Arm v',
        'arm64/armv': 'Arm v',
        'xtensa/xtensa': 'Xtensa'
    }

    if not dts_chain_filtered:
        return ''

    for k, v in r.items():
        if k in dts_chain_filtered[-1]:
            dts_chain_filtered[-1] = dts_chain_filtered[-1].replace(k, v)

    if len(dts_chain_filtered) == 1:
        dts_cpu_info = dts_chain_filtered[0]
    else:
        dts_cpu_info = f'{dts_chain_filtered[-1]} {dts_chain_filtered[0]}'

    return dts_cpu_info


def collective_result(aggregated_results: list):
    """
    Process aggregated build result into a single dict organized by board names.
    """
    collective = dict()

    # Find duplicated board names.
    names = set()
    duplicates = set()
    first_sample_name = next(iter(config.samples))
    for result in aggregated_results:
        if result["sample_name"] != first_sample_name:
            continue
        name = result["platform_full_name"]
        if name in names:
            duplicates.add(name)
        names.add(name)
    del names

    for result in aggregated_results:
        sample_name = result["sample_name"]
        platform = result["platform"]
        soc = ''
        if dts_chain := result.get('dts_include_chain'):
            soc = soc_info(dts_chain)

        # If the pretty name is not unique, append its revision.
        if result["platform_full_name"] in duplicates:
            result["platform_full_name"] += ' ' + (result.get("platform_revision") or '')

        if platform not in collective:
            collective[platform] = dict(
                    arch=result["arch"],
                    arch_bits=result["arch_bits"],
                    name=result["platform_full_name"],
                    soc=soc,
                    samples=dict())

        sample_entry = dict(
            status="BUILT" if result["success"] else "NOT BUILT",
            extended_memory=result["extended_memory"],
        )

        collective[platform]["samples"][sample_name] = sample_entry

    return collective


def collective_json_result(aggregated_results: list) -> str:
    """
    Process aggregated build result into a single JSON organized by board names.
    """
    return json.dumps(collective_result(aggregated_results))


def minimal_csv_result(aggregated_results: list):
    return [[
        elem['platform'],
        elem['sample_name'],
        1 if elem['success'] else 0,
        1 if elem['extended_memory'] else 0
    ] for elem in aggregated_results]


def board_info_csv(collective_result):
    # use a dictionary in order not to duplicate entries about the same platform
    boards = {}
    for platform, data in collective_result.items():
        boards[platform] = [
            data['name'],
            data['soc'],
            data['arch'],
            data['arch_bits'],
        ]
    return [[key, *val] for key, val in boards.items()]


def main():
    versions = get_versions()
    summary_data = aggregate_json_files("build/")

    # Data for markdown table
    stats = generate_stats(summary_data)

    with open('build/result.csv', 'w') as res_csv:
        writer = csv.writer(res_csv)
        writer.writerows(minimal_csv_result(summary_data))

    with open('build/boards.csv', 'w') as boards_csv:
        writer = csv.writer(boards_csv)
        writer.writerows(board_info_csv(collective_result(summary_data)))

    sample_data = process_sample_data(summary_data)

    # Render the table
    rendered = summary_template.render(versions=versions, stats=stats, sample_data=sample_data)
    print(rendered)


if __name__ == "__main__":
    config.load()
    main()
