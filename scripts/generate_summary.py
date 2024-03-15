#!/usr/bin/env python3

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


def collective_json_result(aggregated_results: list) -> str:
    """
    Process aggregated build result into a single JSON organized by board names.
    """
    collective = dict()

    # Find duplicated board names.
    names = set()
    duplicates = set()
    for result in aggregated_results:
        if result["sample_name"] != "hello_world":
            continue
        name = result["platform_full_name"]
        if name in names:
            duplicates.add(name)
        names.add(name)
    del names

    for result in aggregated_results:
        sample_name = result["sample_name"]
        platform = result["platform"]

        # If the pretty name is not unique, append its revision.
        if result["platform_full_name"] in duplicates:
            result["platform_full_name"] += ' ' + (result.get("platform_revision") or '')

        if platform not in collective:
            collective[platform] = dict(
                    arch=result["arch"],
                    arch_bits = result["arch_bits"],
                    name=result["platform_full_name"],
                    samples=dict())

        sample_entry = dict(
            status="BUILT" if result["success"] else "NOT BUILT",
            extended_memory=result["extended_memory"],
        )

        collective[platform]["samples"][sample_name] = sample_entry

    return json.dumps(collective)

def main():
    versions = get_versions()
    summary_data = aggregate_json_files("build/")

    # Data for markdown table
    stats = generate_stats(summary_data)
    json_res = collective_json_result(summary_data)

    with open('build/result.json', 'w') as res:
        res.write(json_res)

    sample_data = process_sample_data(summary_data)

    # Render the table
    rendered = summary_template.render(versions=versions, stats=stats, sample_data=sample_data)
    print(rendered)


if __name__ == "__main__":
    config.load()
    main()
