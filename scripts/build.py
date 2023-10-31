#!/usr/bin/env python3

import jinja2
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from argparse import ArgumentParser
import json
import config
import yaml
from common import bold, print_frame, create_zip_archive, find_node_size, get_sample_path, calculate_md5, get_versions, zephyr_config_to_list

templateLoader = jinja2.FileSystemLoader(searchpath="./")
templateEnv = jinja2.Environment(loader=templateLoader)

dts_overlay_template = templateEnv.get_template("templates/overlay.dts")


def run_west_cmd(cmd: str, log_file: str) -> tuple[int, str]:
    """
    Execute a west command and log the output to a file.

    Parameters:
        cmd (str): The command to be executed.
        log_file (str): The path to the log file.

    Returns:
        str: The command output (including error output, if any).
    """
    try:
        return_code = 0
        output = subprocess.check_output((cmd.split(" ")), stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as error:
        return_code = error.returncode
        output = error.output.decode()

    with open(log_file, "a") as file:
        file.write(output)

    return return_code, output


def build_copy_sample(platform: str, sample_name: str, sample_path: str, args: str) -> tuple[int, str]:
    """
    Build the Zephyr project for a given platform and sample, and copy the resulting artifacts and SPDX files

    Parameters:
        platform (str): The board for building the Zephyr project
        sample_path (str): The path to the sample code within the Zephyr project
        args (str): Additional build arguments for west build command
        sample_name (str): The name of the sample being built

    Returns:
        tuple: A tuple containing the return code (0 for success, 1 for failure)
        and the output of the 'west build' command
    """
    project_sample_name = f"{platform}/{sample_name}"
    return_code = 1

    # Create the build directory if it doesn't exist
    os.makedirs(f"build/{project_sample_name}", exist_ok=True)
    previous_dir = os.getcwd()
    os.chdir(config.project_path)

    # Create a temporary directory inside a Zephyr tree
    build_path = f"build.{platform}.{sample_name}"
    if os.path.isdir(build_path):
        shutil.rmtree(build_path)

    log_path = f"../../build/{project_sample_name}/{sample_name}-zephyr.log"

    # Build sample and collect SPDX data
    run_west_cmd(f"west spdx --init -d {build_path}", log_path)
    return_code, west_output = run_west_cmd(
        f"west build --pristine -b {platform} -d {build_path} {sample_path} {args}".strip(), log_path
    )
    run_west_cmd(f"west spdx -d {build_path}", log_path)

    # Copy files
    os.chdir(previous_dir)

    format_args = {"board_name": platform, "sample_name": sample_name}

    # Same keys as in `artifact_names` in config
    file_map = {
        "elf": "zephyr/zephyr.elf",
        "dts": "zephyr/zephyr.dts",
        "config": "zephyr/.config",
        "sbom-app": "spdx/app.spdx",
        "sbom-build": "spdx/build.spdx",
        "sbom-zephyr": "spdx/zephyr.spdx",
    }

    # Copy all matching artifacts
    for key, file_name in file_map.items():
        file_path = f"{config.project_path}/{build_path}/{file_name}"
        if os.path.exists(file_path):
            shutil.copyfile(file_path, config.artifact_paths[key].format(**format_args))

    # Clean up
    if os.path.isdir(f"{config.project_path}/{build_path}"):
        shutil.rmtree(f"{config.project_path}/{build_path}")

    return return_code, west_output


def try_build_copy_sample(platform: str, sample_name: str, sample_path: str, sample_args: str = None) -> tuple[int, bool]:
    """
    A wrapper for `build_sample`. Intended to capture recoverable errors
    This function might increase the flash node size in the DTS if the sample build requires it.

    Parameters:
        platform (str): The platform for building the Zephyr sample
        sample_name (str): The name of the sample being built
        sample_path (str): The path to the sample code within the Zephyr project
        sample_args (str): Additional build arguments for the sample

    Returns:
        A tuple (returncode: int, memory_extended: bool)
    """
    return_code = 1
    extended_memory = False

    print(f"Building for {bold(platform)}, sample: {bold(sample_name)} with args: {bold(sample_args)}.")

    # Prepare arguments for the build_and_copy_bin function
    args = f"-- {sample_args}" if sample_args else ""
    return_code, west_output = build_copy_sample(platform, sample_name, sample_path, args)

    # Check whether the build was successful. If "region overflowed" is present in the logs, attempt to build with extended memory node.
    if return_code:
        ocurrences = re.findall(r"region `(\S+)' overflowed by (\d+) bytes", west_output)
        dts_filename = config.artifact_paths["dts"].format(board_name=platform, sample_name=sample_name)

        if ocurrences and os.path.exists(dts_filename):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as f:
                for m in ocurrences:
                    node = m[0].lower()
                    if node == "ram":
                        node = "sram"

                    shutil.copy2(dts_filename, dts_filename + ".orig")

                    node = find_node_size(node, dts_filename)
                    if node is None:
                        print("No node")
                        return (return_code, extended_memory)

                    node_name, node_size = node
                    node_increase = math.ceil(int(m[1]) / 4096) * 4096
                    if len(node_size) >= 2:
                        node_base, node_size = node_size[-2:]
                        node_size = int(node_size, 16)
                        node_size += node_increase
                        f.write(dts_overlay_template.render(reg_name=node_name, reg_base=node_base, reg_size=node_size))
                        f.flush()
                overlay_path = f.name

                # Build again, this time with bigger flash size
                overlay_args = f"-DDTC_OVERLAY_FILE={overlay_path}"
                args = f"-- {sample_args} {overlay_args}"
                print("Building again with extended node(s) size...")
                return_code, _ = build_copy_sample(platform, sample_name, sample_path, args)
                extended_memory = True

    return (return_code, extended_memory)


def get_full_name(yaml_filename):
    if os.path.exists(yaml_filename):
        with open(yaml_filename) as f:
            board_data = yaml.load(f, Loader=yaml.FullLoader)
        full_board_name = board_data['name']
        if len(full_board_name) > 50:
            full_board_name = re.sub(r'\(.*\)', '', full_board_name)
    else:
        full_board_name = ''
    return full_board_name


def get_board_yaml_path(arch, board_name):
    board_yaml = f'{config.project_path}/boards/{arch}/{board_name}/{board_name}.yaml'

    # this hack is needed for pinetime_devkit0
    if not os.path.exists(board_yaml):
        board_yaml = f'{config.project_path}/boards/{arch}/{board_name}/{board_name.replace("_", "-")}.yaml'

    return board_yaml


def main(arch: str, board_name: str, sample_name: str) -> None:
    """
    Main function to build a Zephyr sample for a specific board and create relevant artifacts.

    Parameters:
        board_name (str): The name of the board to build the Zephyr sample for
        sample_name (str): The name of the sample being built
    """

    sample_path = get_sample_path(sample_name)
    os.makedirs(f"build/{board_name}/{sample_name}", exist_ok=True)

    config_path = f"configs/{sample_name}.conf"
    if os.path.exists(config_path):
        sample_args = f"-DCONF_FILE={os.path.realpath(config_path)}"
    else:
        sample_args = None

    return_code, extended_memory = try_build_copy_sample(board_name, sample_name, f"samples/{sample_path}", sample_args)

    format_args = {
        "board_name": board_name,
        "sample_name": sample_name,
    }

    elf_name = config.artifact_paths["elf"].format(**format_args)
    elf_md5_name = config.artifact_paths["elf-md5"].format(**format_args)

    platform_full_name = get_full_name(get_board_yaml_path(arch, board_name))

    result = {
        "platform": board_name,
        "sample_name": sample_name,
        "success": (return_code == 0) and os.path.exists(elf_name),
        "extended_memory": extended_memory,
        "configs": zephyr_config_to_list(config_path) if sample_args is not None else None,
        "zephyr_sha": get_versions()["zephyr"],
        "zephyr_sdk": get_versions()["sdk"],
        "arch": arch,
        "platform_full_name": platform_full_name
    }

    # Create JSON with build results
    results_json_name = config.artifact_paths["result"].format(**format_args)
    with open(results_json_name, "w") as f:
        json.dump(result, f)

    if result["success"]:
        # Create MD5 hash file for the binary
        with open(elf_md5_name, "w") as f:
            f.write(calculate_md5(elf_name))

        # Create ZIP archive with sboms
        sbom_zip_name = config.artifact_paths["zip-sbom"].format(**format_args)
        create_zip_archive(sbom_zip_name, format_args, files=["sbom-app", "sbom-zephyr", "sbom-build"])

    # Create a ZIP archive with all artifacts
    all_zip_name = config.artifact_paths["zip-all"].format(**format_args)
    all_artifacts = list(config.artifact_paths.keys())
    all_artifacts.remove("zip-all")
    create_zip_archive(all_zip_name, format_args, all_artifacts)


if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("arch")
    ap.add_argument("board_name")
    ap.add_argument("sample_name")
    ap.add_argument("-j", "--job-number")
    ap.add_argument("-J", "--jobs-total")
    args, _ = ap.parse_known_args()

    config.load()

    multijob = args.job_number is not None and args.jobs_total is not None
    arch = args.arch
    board_name = args.board_name
    sample_name = args.sample_name

    if multijob:
        start_time = time.time()
        print_frame(f"job {args.job_number} / {args.jobs_total} started")

    main(arch, board_name, sample_name)

    if multijob:
        total_time = time.time() - start_time
        print_frame(f"job {args.job_number} / {args.jobs_total} finished in {total_time:.2f}")
