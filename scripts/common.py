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
    if workspace := get_sample_workspace(sample_name):
        return os.path.realpath(f'{workspace}/{config.samples[sample_name]["path"]}')
    else:
        return os.path.realpath(f'{config.project_path}/{config.samples[sample_name]["path"]}')



def get_sample_workspace(sample_name: str) -> str | None:
    """
    Retrieve the sample workspace location.

    Args:
        sample_name (str): The name of the sample.

    Returns:
        Optional[str]: The Zephyr's workspace path, None if the key is empty.
    """
    return config.samples[sample_name].get("workspace", None)


def get_sample_extra_args(sample_name: str) -> str | None:
    """
    Retrieve the sample extra arguments.

    Args:
        sample_name (str): The name of the sample.

    Returns:
        Optional[str]: Sample extra arguments, None if the key is empty.
    """
    return config.samples[sample_name].get("extra_args", None)


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


def zephyr_config_to_list(config_path: str) -> list | None:
    """
    Convert a Zephyr configuration file to a list of strings.

    Args:
        config_path (str): The path to the Zephyr configuration file.

    Returns:
        Optional[list]: A list of non-commented lines from the configuration file,
                        None if file doesn't exist.
    """
    if os.path.exists(config_path):
        with open(config_path, 'r') as cfg:
            return [line.strip() for line in cfg if line.strip() and not line.startswith('#')]
    else:
        return None


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


def identifier_drop_revision(identifier: str) -> str:
    """
    Drop the revision from the Zephyr identifier.

    Args:
        identifier (str): Non-sanitized Zephyr board identifier.

    Returns:
        str: Non-sanitized Zephyr board identifier without the revision.
    """
    match = re.match(r'^([^@/]+)(?:@[^/]+)?(?:/([^@]+))?$', identifier)
    if match:
        board_path = match.group(1)
        soc_path = match.group(2)
        if soc_path:
            return f"{board_path}/{soc_path}"
        else:
            return board_path

def identifier_split(identifier: str) -> (str, str, str, str):
    """
    Splits target name into a tuple: (platform_name, revision, soc_name, variant) where particular elements can bee emptry string if not specified directly in the target name.
    """
    match = re.match(r'^([^@/]+)(@[^/]+)?(/[^/]+)?(/.+)?$', identifier)
    platform_name = match.group(1) if match and match.group(1) else ''
    revision = match.group(2)[1:] if match and match.group(2) else ''
    soc_name = match.group(3)[1:] if match and match.group(3) else ''
    variant = match.group(4)[1:] if match and match.group(4) else ''
    return (platform_name, revision, soc_name, variant)

def identifier_get_substrings(identifier: str) -> list:
    """
    Drop the revision from the Zephyr identifier.

    Example:
        actinius_icarus/nrf9160 -> ['actinius_icarus_nrf9160', 'actinius_icarus', 'actinius']

    Args:
        identifier (str): Sanitized Zephyr board identifier.

    Returns:
        list: A list of substrings separated on `_`
    """
    substrings = []
    parts = identifier.split('_')
    for i in range(len(parts), 0, -1):
        substrings.append('_'.join(parts[:i]))
    return substrings


def get_dts_by_identifier(board_dir: str, board_identifier: str, board_yaml_path: str) -> str:
    '''
    Try to get the target's base `dts` file.

    XXX: this is a hackfest, but currently Zephyr doesn't provide an easy way of matching
    the identifier to the corresponding dts file.

    TODO: One of the possible approaches to change this would be to actually use the original @wspiak
          approach of generating the workload: use Zephyr's `get_board()` and `get_hardware()` scripts
          to generate all possible `board@rev/soc/cluster` permutations. We could use this data here.

    For more information on how Zephyr determines the correct DTS file and its overlays PTAL:
        * cmake/modules/dts.cmake         - `DTS_SOURCE` variable
        * cmake/modules/extensions.cmake  - `zephyr_build_string` function
    '''
    # Get all dts files inside the `board_dir`
    filenames = []
    for root, dirs, files in os.walk(board_dir):
        for file in files:
            if file.endswith('.dts'):
                filenames.append(file)

    # If there is only one `dts` file -> use it
    if len(filenames) == 1:
        return os.path.join(board_dir, filenames[0])

    # Most of the time the time `.dts` basename is the same as the coresponding `.yaml` file basename, for example:
    # nucleo_h745zi_q_stm32h745xx_m4.yaml -> nucleo_h745zi_q_stm32h745xx_m4.dts
    dts_candidate_from_yaml_name = f'{board_dir}/{os.path.splitext(os.path.basename(board_yaml_path))[0]}.dts'
    if os.path.exists(dts_candidate_from_yaml_name):
        return dts_candidate_from_yaml_name

    # Multiple `dts` files and no direct match has been made. Attempt to match _closest_ `dts` file
    # 1. Remove `BOARD_REVISION` from the target identifier
    # 2. Create a list of possible `dts` filenames, with decreasing specificity (the `.dts` suffix is added to the end of each list)
    # 3. Check if a `dts` file with the decreased specificity exists
    #  3.1. yes -> use it
    #  3.2  no -> attempt lower specificity
    #
    # Example flow
    # (0) target_identifier = actinius_icarus@2.0.0/nrf9160
    # (1) actinius_icarus@2.0.0/nrf9160 -> actinius_icarus/nrf9160
    # (2) ['actinius_icarus_nrf9160.dts', 'actinius_icarus.dts', 'actinius.dts']
    # (3) `actinius_icarus_nrf9160.dts` exists and matches the identifier
    board_identifier_sanitized = sanitize_lower(identifier_drop_revision(board_identifier))
    possible_dts_filenames = [f'{s}.dts' for s in identifier_get_substrings(board_identifier_sanitized)]

    for dts_candidate in possible_dts_filenames:
        full_path = os.path.join(board_dir, dts_candidate)
        if dts_candidate in filenames and os.path.exists(full_path):
            return full_path

    # All heuristics have failed!
    # Return any `dts` file as a failsafe, None if no `dts` files have been found.
    if filenames:
        return filenames[0]
    else:
        print(red(f'NO DTS FILE FOUND FOR {board_identifier}'))
        return ""


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


def sanitize_lower(string: str) -> str:
    """
    Sanitize the string, so that the string only contains alpha-numeric
    characters or underscores. All non-alpha-numeric characters are replaced
    with an underscore, '_'.
    When string has been sanitized it will be converted into lower case.

    Args:
        string(str): The string to sanitize.

    Returns:
        str: Sanitized and lower-cased string.
    """
    return re.sub(r'[^a-zA-Z0-9_]', '_', string).lower()
