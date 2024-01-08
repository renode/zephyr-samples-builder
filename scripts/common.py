#!/usr/bin/env python3

import re
import os
import yaml
import zipfile
import hashlib
from colorama import Fore, Style
import config


def bold(text: str) -> str:
    """
    Apply bold formatting to the provided text.

    Args:
        text (str): The input text to be formatted in bold.

    Returns:
        str: The input text with bold formatting.
    """
    return Style.BRIGHT + (text or "") + Style.RESET_ALL


def red(text):
    """
    Apply red color to the provided text.
    """
    return Fore.RED + (text or "") + Style.RESET_ALL


def green(text):
    """
    Apply green color to the provided text.
    """
    return Fore.GREEN + (text or "") + Style.RESET_ALL


def get_sample_path(sample_name: str) -> str:
    """
    Retrieve the path of a sample within the configuration.

    Args:
        sample_name (str): The name of the sample.

    Returns:
        str: The path of the specified sample.
    """
    return config.samples[sample_name]["path"]


def find_node_size(node: str, dts_filename: str):
    """
    Find the size of a specific node in a DTS file.

    Args:
        node (str): The name of the node to find the size for.
        dts_filename (str): The filename of the DTS file.

    Returns:
        tuple or None: A tuple containing the node name and its size as a list of values,
                       or None if the node or size information is not found in the DTS.
    """
    with open(dts_filename) as f:
        dts = f.read()
    try:
        node_name = re.search(r"zephyr,{} = &(\w+);".format(node), dts).group(1)
        node_size = re.search(r"{}:(.*\n)*?.*reg = <(.*)>;".format(node_name), dts).group(2)
        node_size = node_size.split()
    except AttributeError:
        return None
    return node_name, node_size


def decode_node(node_name, dts_filename):
    node = find_node_size(node_name, dts_filename)
    if node is None:
        return (None, None, None)

    node_name, node_size = node
    if len(node_size) >= 2:
        node_base, node_size = node_size[-2:]
        node_size = int(node_size, 16)

        return (node_name, node_base, node_size)
    else:
        return (node_name, node_size, None)


def flatten(boards: dict):
    """
    Flatten nested architecture-based board dictionary.

    Args:
        boards (dict): Dictionary of board lists categorized by architecture.

    Returns:
        dict: Flattened dictionary with board names as keys and objects as values.
    """
    flat_boards = {}
    for arch in boards:
        for board in boards[arch]:
            flat_boards[board.name] = board
    return flat_boards


def create_zip_archive(zip_filename: str, format_args: dict, files: list) -> None:
    """
    Create a zip archive containing specified files based on the given format arguments.

    Parameters:
        zip_filename (str): The name of the zip archive to be created
        format_args (dict): A dictionary of format arguments for building file paths
        files (list): A list of artifacts to include in the zip archive

    Raises:
        ValueError: If a key specified in 'files' does not occur in 'config.artifact_paths'
    """
    with zipfile.ZipFile(zip_filename, "w", compression=zipfile.ZIP_DEFLATED) as f:
        for ftype in files:
            if ftype in config.artifact_paths.keys():
                fname = config.artifact_paths[ftype].format(**format_args)
            else:
                raise ValueError(f"No {ftype} key in artifacts. Path unknown")
            if os.path.exists(fname):
                f.write(fname, fname.split(os.sep)[1] + os.sep + os.path.basename(fname))


def print_frame(text: str, width: int = 80) -> None:
    """
    Print the given text within a frame of equal signs.

    Parameters:
        text (str): The text to be printed within the frame
        width (int, optional): The width of the frame. Defaults to 80
    """
    print("\n" + width * "=")
    print(text)
    print(width * "=" + "\n")


def calculate_md5(filename: str) -> str:
    """
    Calculate the MD5 hash of a file.

    Args:
        filename (str): The name of the file to calculate the MD5 hash for.

    Returns:
        str: The MD5 hash of the file as a hexadecimal digest.
    """
    hash_md5 = hashlib.md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def get_versions() -> dict:
    """
    Retrieve versions of Zephyr, Zephyr SDK, and MicroPython from environment variables.

    The corresponding values are read from environment variables.
    If the environment variable is not set, the value will be "???".
    """
    default = "???"
    return {
        "zephyr": os.environ.get("ZEPHYR_VERSION", default),
        "sdk": os.environ.get("ZEPHYR_SDK_VERSION", default),
        "micropython": os.environ.get("MICROPYTHON_VERSION", default),
    }


def zephyr_config_to_list(config_path: str) -> list:
    """
    Convert a Zephyr configuration file to a list of strings.

    Args:
        config_path (str): The path to the Zephyr configuration file.

    Returns:
        list: A list of non-commented lines from the configuration file.
    """
    with open(config_path, 'r') as cfg:
        return [line.strip() for line in cfg if line.strip() and not line.startswith('#')]


def get_yaml_data(yaml_filename: str):
    """
    Load data from a YAML file.

    Args:
        yaml_filename (str): Path to the YAML file.

    Returns:
        Any: Parsed YAML data.
    """
    with open(yaml_filename) as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def conv_zephyr_mem_usage(val: str) -> int:
    """
    Convert Zephyr memory usage value to bytes.

    Args:
        val (str): Memory usage value with unit (B, KB, MB, GB).

    Returns:
        int: Memory usage in bytes.
    """
    if val.endswith(' B'):
        val = int(val[:-2])
    elif val.endswith(' KB'):
        val = int(val[:-3]) * 1024
    elif val.endswith(' MB'):
        val = int(val[:-3]) * 1024 ** 2
    elif val.endswith(' GB'):
        val = int(val[:-3]) * 1024 ** 3

    return val


def get_dts_include_chain(arch: str, dts_filename: str, chain=[]) -> list:
    """
    Recursively read .dts file to retrieve the CPU dependency chain.

    Args:
        arch (str): The target CPU architecture.
        dts_filename (str): The name of the .dts file to be parsed.
        chain (list): A list for keeping track of the dependencies.

    Returns:
        list: Contains the name(s) of the CPU as determined from the .dts file(s).
    """
    next_include = ''
    if os.path.exists(dts_filename):
        with open(dts_filename) as f:
            dts_file = f.readlines()
        for line in dts_file:
            if next_include == '' and line.startswith('#include'):
                _, next_include = line.split()
                local = not (next_include.startswith('<') and next_include.endswith('>'))
                next_include = next_include.strip(' "<>')
                name, extension = os.path.splitext(next_include)
                if extension.strip('.') == 'h':
                    next_include = ''
                    continue
                if local:
                    dtsi_filename = f'{os.path.dirname(dts_filename)}/{next_include}'
                    name = '!' + name
                else:
                    dtsi_filename = f'{config.project_path}/dts/{arch}/{next_include}'
                return get_dts_include_chain(arch, dtsi_filename, chain + [name])
    return chain
