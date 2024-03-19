#!/usr/bin/env python3

import jinja2
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import yaml
import contextlib
from typing import Tuple
from argparse import ArgumentParser
import config
from common import (
    bold,
    green,
    red,
    create_zip_archive,
    find_node_size,
    decode_node,
    get_sample_path,
    print_frame,
    zephyr_config_to_list,
    get_versions,
    get_yaml_data,
    calculate_md5,
    conv_zephyr_mem_usage,
    get_dts_include_chain,
    sanitize_lower,
    get_sample_workspace,
    get_sample_extra_args,
)

templateLoader = jinja2.FileSystemLoader(searchpath="./")
templateEnv = jinja2.Environment(loader=templateLoader)

dts_overlay_template = templateEnv.get_template('templates/overlay.dts')


@contextlib.contextmanager
def remember_cwd():
    curdir = os.getcwd()
    try:
        yield
    finally:
        os.chdir(curdir)


class YAMLNotFoundException(Exception):
    pass


class SampleBuilder:
    def __init__(self, platform: str, sample_path: str, sample_name: str, sample_workspace: str | None) -> None:
        # Parameters
        self.platform = platform
        self.config = config
        self.sample_path = sample_path
        self.sample_name = sample_name
        self.sample_workspace = self.config.project_path if sample_workspace is None else sample_workspace

        self.args = {}
        self.overlays = {}

        self.log_file = tempfile.mkstemp(suffix='_log', text=True)[1]

        self.temp_dir_path = tempfile.mkdtemp()
        print(f'Build dir: {self.temp_dir_path}')

        self.dts_modified = False
        self.dts_original = tempfile.mkstemp(suffix='_dts_original', text=True)[1]

        self.success = False

    # Constants
    ARTIFACTS = {
        "elf": "zephyr/zephyr.elf",
        "dts": "zephyr/zephyr.dts",
        "config": "zephyr/.config",
        "spdx_app": "spdx/app.spdx",
        "spdx_build": "spdx/build.spdx",
        "spdx_zephyr": "spdx/zephyr.spdx"
    }

    _MEMORY_EXTENSION_REGEX = r"region `(\S+)' overflowed by (\d+) bytes"
    _MEMORY_USAGE_REGEX = r"(?P<region>\w+){1}:\s*(?P<used>\d+\s+\w{1,2})\s*(?P<size>\d+\s+\w{1,2})\s*(?P<percentage>\d+.\d+%)"
    _ARCH_ERROR_REGEX = r"Arch .*? not supported"

    def __del__(self):
        # Remove the temporary build directory
        if os.path.isdir(self.temp_dir_path):
            shutil.rmtree(self.temp_dir_path)

        # Remove temporary files
        for file in [self.log_file, self.dts_original]:
            if os.path.isfile(file):
                os.remove(file)

    def build_sample(self) -> dict:
        """
            Build a Zephyr sample with optional memory size extension

            Args:
            run (SampleBuilder): The SampleBuilder instance for the run.

            Returns:
            dict: A dictionary containing artifacts generated during the build.
        """
        print(f"Building for {bold(self.platform)}, sample: {bold(self.sample_name)}.")

        # Board DTS overlay has been applied, generate an unmodified DTS file
        if self.overlays:
            print("This board specifies a DT overlay file. Performing a clean build to preserve original DTS")
            self._build(prepare_only=True, disable_overlays=True)
            original_dts = self.get_artifacts().get('dts', None)
            if original_dts is not None:
                self._copy_original_dts_file(original_dts)

        fail, west_output = self._build()

        if fail:
            self._check_extend_memory(west_output)

        arifacts = self.get_artifacts()

        self.success = ("elf" in arifacts) and self._check_kconfig_requirements()

        return arifacts

    def _find_elf_file(self) -> str:
        """
            Search for an ELF file in the Zephyr build directory.

            Returns:
                str: filename if an ELF exists, otherwise None.
        """

        for root, _, files in os.walk(self.temp_dir_path):
            for _file in files:
                if _file.endswith(".elf") and _file not in ["zephyr_pre0.elf", "zephyr_pre1.elf"]:
                    return os.path.join(root, _file)

        return None

    def get_artifacts(self) -> dict:
        """
            Retrieves the paths of all existing artifacts in the temporary directory.

            Returns:
            dict: A dictionary containing the names and paths of the existing artifacts.
        """
        artifacts = {}

        for name, path in self.ARTIFACTS.items():
            expanded_path = f"{self.temp_dir_path}/{path}"
            if os.path.exists(expanded_path):
                artifacts[name] = expanded_path

        # Platforms may change the default name of the ELF artifact (`esp32s3_devkitm_appcpu`).
        if ("elf" not in artifacts) and (candidate := self._find_elf_file()):
            print(f"zephyr.elf not found! Trying to use: {candidate}")
            artifacts["elf"] = candidate

        return artifacts

    def get_memory_usage(self) -> dict | None:
        """
            Get memory usage (in bytes) from the Zephyr log file.

            The results are returned as a dict:
            {'MEM': {'used': 100, 'size': 200 }, ...}

            SIZE is the original node size.
            If memory node was extended, USED is going to exceed SIZE.
        """
        if not self.success:
            return None

        memory = {}
        with open(self.log_file) as f:
            match = re.findall(self._MEMORY_USAGE_REGEX, f.read())

        # Get memory usage statistics
        for m in match:
            region, used, size, _ = m
            memory[region] = {
                'used': conv_zephyr_mem_usage(used),
                'size': conv_zephyr_mem_usage(size),
            }

        # Check if flash size was increased
        if "memory" in self.overlays:
            for type in ['FLASH', 'RAM']:
                if type in memory:
                    node_name = self._get_alternative_node_name(type, self.dts_original)
                    _, node_size = find_node_size(node_name, self.dts_original)
                    node_size = int(node_size[-1], 16)
                    memory[type].update({
                        'size': node_size,
                    })

        return memory

    def _copy_original_dts_file(self, dts_original_path: str) -> None:
        """
            Checks if the DTS file was modified. If not, preserves the original file.

            Parameters:
            dts_original_path (str): The path to the original DTS file.
        """
        if not self.dts_modified:
            print(f"Preserving original DTS file at {dts_original_path}")
            shutil.copyfile(dts_original_path, self.dts_original)

    def _run_command(self, cmd: str) -> Tuple[bool, str]:
        """
            Runs a specified west command.

            Parameters:
            cmd (str): The west command to be run.

            Returns:
            bool: True if the command failed, False otherwise.
            str: The output from the executed command.
        """
        failed = False
        output = ""

        try:
            output = subprocess.check_output((cmd.split(" ")), stderr=subprocess.STDOUT).decode()
        except subprocess.CalledProcessError as error:
            failed = True
            output = error.output.decode()

        if self.log_file is not None:
            with open(self.log_file, 'a') as file:
                file.write(output)

        return (failed, output)

    def _build(self, pristine: bool = True, prepare_only: bool = False, disable_overlays: bool = False) -> Tuple[bool, str]:
        """
            Build the Zephyr project with optional configurations.

            Parameters:
            pristine (bool, optional): If True, build with pristine settings. Default is True.
            prepare_only (bool, optional): If True, prepare the build without actually building. Default is False.
            disable_overlays (bool, optional): If True, disable overlays in the build. Default is False.

            Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating build success (True if failed) and
            a string with the build output or error message.
        """

        # Save information about tainted DTS file
        self.dts_modified = bool(self.overlays and not disable_overlays)

        with remember_cwd():
            # Enter Zephyr directory
            os.chdir(self.sample_workspace)

            # Concentrate overlay and base args
            build_args = (' '.join(list(self.args.values())) if self.args else '') + (' -DDTC_OVERLAY_FILE=' + ';'.join(list(self.overlays.values())) if self.overlays and not disable_overlays else '')

            # Print arguments
            print(f"Building with {bold('args')}: {build_args}")

            # Remove the `BUILD_DIR` before building
            # Required for correct SPDX generation, as without this, the SPDX files
            # would not get generated upon a rerun (overlay, node extension)
            if os.path.isdir(self.temp_dir_path):
                shutil.rmtree(self.temp_dir_path)

            # Build the sample in the `temp_dir_path`
            build_command = (
                "west build "
                f"-b {self.platform} "
                f"-d {self.temp_dir_path} "
                f"{self.sample_path} "
                f"{build_args} "
                f"{'--pristine' if pristine else ''} "
                "-DCONFIG_BUILD_OUTPUT_META=y "  # Since Zephyr 7bde51b this config must be enabled to generate spdx files
            ).strip()

            if prepare_only:
                failed, output = self._run_command(f"{build_command} --cmake-only")
            else:
                self._run_command(f"west spdx --init -d {self.temp_dir_path}")
                failed, output = self._run_command(build_command)
                self._run_command(f"west spdx -d {self.temp_dir_path}")

            return failed, output

    def _get_alternative_node_name(self, node_name: str, dts_filename: str) -> str:
        """
            Linker script errors do not match the DTS entries, so we patch them when required.
            ! This heurestic may be too naive for some cases !
            Reference for the names: search for `overflowed by` in `scripts/pylib/twister/twisterlib/runner.py`
            in Zephyr, it also parses the linker output.

            Parameters:
            node_name (str): Memory node to be extended.
            dts_filename (str): Path to the DTS file.

            Returns:
            str: An patched node name, original name if not found
        """
        alternative_names = {
            "ram": "sram",
            "rom": "flash",
            "dram0_1_seg": "ipmmem0",
            "iccm": "iccm0",
            "dccm": "dccm0",
        }
        node_name = node_name.lower()
        alternative = alternative_names.get(node_name, node_name)
        return alternative if find_node_size(node_name, dts_filename) is None else node_name

    def _prepare_node_entries(self, west_output, dts_filename):
        """
        Prepares memory node entries based on west errors and the DTS file.

        Args:
        west_output (str): West build output.
        dts_filename (str): Path to the DTS file.

        Returns:
        dict: Dictionary with log node names as keys and tuples as values.
        None, if no occurrences are found or if the DTS file does not exist.
        """
        occurrences = re.findall(self._MEMORY_EXTENSION_REGEX, west_output)

        if occurrences == [] or not os.path.exists(dts_filename):
            return

        sizes = {}
        for m in occurrences:
            log_node_name = m[0]
            node_name = self._get_alternative_node_name(log_node_name.lower(), dts_filename)
            decoded_node_name, decoded_node_base, decoded_node_size = decode_node(node_name, dts_filename)
            if decoded_node_name is None:
                print(f"No node {node_name} found when trying to resize it")
                return

            if decoded_node_size is None:
                print(f"Unable to parse enough information out of node {node_name} to increase its size, aborting")
                return

            sizes[log_node_name] = (decoded_node_name, decoded_node_base, decoded_node_size)

        return sizes

    def _generate_overlay_file(self, sizes):
        """
        Generates a file with an overlay that will increase required sizes.

        Args:
        sizes (dict): Dictionary with log node names as keys and tuples as values.

        Returns:
        str: Temporary file name.
        """
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
            # create an overlay
            for log_node_name in sizes:
                node_name, node_base, node_size = sizes[log_node_name]
                f.write(dts_overlay_template.render(
                    reg_name=node_name,
                    reg_base=node_base,
                    reg_size=node_size
                ))
            f.flush()
            return f.name

    def _check_extend_memory(self, west_output: str) -> None:
        """
            Check and extend memory node size if necessary for a given run.

            Args:
            west_output (str): The output of the west build tool
        """
        dts_filename = self.get_artifacts().get("dts", None)
        if not dts_filename:
            print("Build failed. DTS file is not present. Aborting!")
            return

        arch_err = re.findall(self._ARCH_ERROR_REGEX, west_output)
        if arch_err:
            print("Build failed. Arch not supported. Aborting!")
            return

        sizes = self._prepare_node_entries(west_output, dts_filename)
        if not sizes:
            print("Build failed. Size is not the issue. Aborting!")
            return

        # we're out of memory. We'll try to increase all detected regions at once, but we'll repeat until:
        # - binary links successfully
        # - increasing node size doesn't change the linker output
        last_occurrences = []
        fail = True
        while fail:
            occurrences = re.findall(self._MEMORY_EXTENSION_REGEX, west_output)

            n_sizes = self._prepare_node_entries(west_output, dts_filename)
            if not n_sizes:
                print("Build failed. Size is not the issue. Aborting!")
                return

            sizes.update(n_sizes)

            if occurrences == []:
                print(f"Build failed. Attempted node size increases: {sizes}. Aborting!")
                return

            if last_occurrences == occurrences:
                print("Resizing didn't change any value in linker output. Failing!")
                return
            last_occurrences = occurrences

            # increase sizes required in this run
            for m in occurrences:
                log_node_name = m[0]
                node_name, node_base, node_size = sizes[log_node_name]
                node_increase = math.ceil(int(m[1]) / 4096) * 4096
                node_size += node_increase
                print(f"Extending {node_name} (at {node_base}) to {node_size:#x} (+{node_increase:#x})")
                sizes[log_node_name] = (node_name, node_base, node_size)

            # build again, this time with bigger flash size
            overlay_path = self._generate_overlay_file(sizes)
            print("Building again with extended node(s) size...")

            # try to preserve original DTS file
            self._copy_original_dts_file(dts_filename)

            # append the overlay file to the SampleBuilder
            self.overlays["memory"] = overlay_path
            fail, west_output = self._build()

    def _check_kconfig_requirements(self):
        """
        Check if the config file generated for this board has symbols set to the
        required status.
        """
        ret = True

        try:
            symbols = self.config.samples[self.sample_name]['kconfig']
        except KeyError:
            # There are no requirements for this sample.
            return ret

        zephyr_config_file = self.get_artifacts()["config"]

        with open(zephyr_config_file) as f:
            zephyr_config = f.read().splitlines()

        for symbol in symbols:
            print(f"Checking for {bold(symbol)} in {bold(zephyr_config_file)}... ", end="")
            for l in zephyr_config:
                if l == symbol:
                    print(bold(green("Found!")))
                    break
            else:
                print(bold(red("Not found!")))
                ret = False

        return ret

def get_full_name(yaml_data):
    full_board_name = yaml_data['name']
    if len(full_board_name) > 50:
        full_board_name = re.sub(r'\(.*\)', '', full_board_name)
    return full_board_name


def get_board_yaml_path_by_identifier(board_dir: str, board_name: str) -> str:
    """
    Attempt to parse all .yaml files inside `board_dir`.
    If any yaml file identifier matches the board_name -> return yaml file location,
    In case no matches are made, raise YAMLNotFoundException.
    """
    print(f'board_dir: {board_dir}, board_name: {board_name}')
    for root, dirs, files in os.walk(board_dir):
        for file in files:
            if file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    try:
                        data = yaml.safe_load(f)
                        if data['identifier'] == board_name:
                            return file_path
                    except yaml.YAMLError as e:
                        print(f"Error reading {file_path}: {e}")
                    except KeyError as e:
                        print(f"No identifier key in: {file_path}: {e}")

    raise YAMLNotFoundException


def get_board_yaml_path(board_dir, board_name):
    yamlpath = f'{board_dir}/{board_name}.yaml'

    if not os.path.exists(yamlpath):
        raise Exception(f"Could not find a YAML file for the board '{board_name}': {yamlpath}")

    return yamlpath


def main(board_dir: str, board_name: str, sample_name: str) -> None:
    """
    Main function to build a Zephyr sample for a specific board and create relevant artifacts.

    Parameters:
        board_dir (str): Board directory in the Zephyr tree
        board_name (str): The name of the board to build the Zephyr sample for
        sample_name (str): The name of the sample being built
    """
    sample_path = get_sample_path(sample_name)
    sample_workspace = get_sample_workspace(sample_name)
    sample_extra_args = get_sample_extra_args(sample_name)
    config_path = f'configs/{sample_name}.conf'
    overlay_path = f'overlays/{board_name}.overlay'

    run = SampleBuilder(board_name, sample_path, sample_name, sample_workspace)

    # Check for sample prj.conf overlay
    if os.path.exists(config_path):
        run.args["config"] = f'-DCONF_FILE={os.path.realpath(config_path)}'

    if sample_extra_args:
        run.args["extra_args"] = sample_extra_args

    # Check for board specific overlay file
    # This also necessitates a generation of an original DTS file
    if os.path.exists(overlay_path):
        run.overlays["custom"] = os.path.realpath(overlay_path)

    # Build the sample
    artifacts = run.build_sample()

    # Template used for naming arfitacts
    # Use sanitized `board_name` for the folder structure and artifact names
    board_name_sanitized = sanitize_lower(board_name)
    project_sample_name = f"{board_name_sanitized}/{sample_name}"

    # Create artifacts location
    os.makedirs(f"build/{project_sample_name}", exist_ok=True)

    # Save logs
    shutil.copyfile(run.log_file, f"build/{project_sample_name}/{sample_name}.log")

    # Save original DTS
    if run.dts_modified:
        shutil.copyfile(run.dts_original, f"build/{project_sample_name}/{sample_name}.dts.orig")

    for key, path in artifacts.items():
        if re.search("spdx.+", key):
            filename = os.path.basename(path)
            shutil.copyfile(path, f"build/{project_sample_name}/{sample_name}-{filename}")
        elif key == "elf":
            shutil.copyfile(path, f"build/{project_sample_name}/{sample_name}.elf")
        elif key == "dts":
            shutil.copyfile(path, f"build/{project_sample_name}/{sample_name}.dts")
        elif key == "config":
            shutil.copyfile(path, f"build/{project_sample_name}/{sample_name}-config")

    format_args = {
        "board_name": board_name_sanitized,
        "sample_name": sample_name,
    }

    elf_name = config.artifact_paths["elf"].format(**format_args)
    elf_md5_name = config.artifact_paths["elf-md5"].format(**format_args)

    try:
        board_yaml_data = get_yaml_data(get_board_yaml_path_by_identifier(board_dir, board_name))
    except YAMLNotFoundException:
        print(bold(f"Skipping target due to missing YAML file: {board_name}"))
        return

    platform_full_name = get_full_name(board_yaml_data)
    arch = board_yaml_data["arch"]

    result = {
        "platform": board_name_sanitized,
        "platform_original": board_name,
        "sample_name": sample_name,
        "success": run.success,
        "extended_memory": "memory" in run.overlays,
        "configs": zephyr_config_to_list(config_path) if run.args else None,
        "zephyr_sha": get_versions()["zephyr"],
        "zephyr_sdk": get_versions()["sdk"],
        "arch": arch,
        "platform_full_name": platform_full_name,
        "board_dir": '/'.join(board_dir.split('/')[2:]),  # Drop 'zephyrproject/zephyr' from the path
        "memory": run.get_memory_usage(),
        "dts_include_chain": get_dts_include_chain(arch, f'{board_dir}/{board_name}.dts'),  # XXX: uses _non-flattened_ device tree
    }

    info = "Success!" if run.success else "Fail!"
    print(bold(info))

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


if __name__ == "__main__":
    ap = ArgumentParser()
    ap.add_argument("board_dir")
    ap.add_argument("board_name")
    ap.add_argument("sample_name")
    ap.add_argument("-j", "--job-number")
    ap.add_argument("-J", "--jobs-total")
    args, _ = ap.parse_known_args()

    config.load()

    multijob = args.job_number is not None and args.jobs_total is not None
    board_dir = args.board_dir
    board_name = args.board_name
    sample_name = args.sample_name

    if multijob:
        start_time = time.time()
        print_frame(f"job {args.job_number} / {args.jobs_total} started")

    main(board_dir, board_name, sample_name)

    if multijob:
        total_time = time.time() - start_time
        print_frame(f"job {args.job_number} / {args.jobs_total} finished in {total_time:.2f}")
