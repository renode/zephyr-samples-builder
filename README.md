# Zephyr Samples Builder

Copyright (c) 2023-2024 [Antmicro](https://www.antmicro.com)

A set of CI pipeline tools for building Zephyr RTOS samples for multiple platforms.

## Overview

This repository contains tools used in CI pipelines that automatically builds Zephyr RTOS samples using the provided `zephyr.yaml` file.

## Configuration

Edit the `zephyr.yaml` file to define the Zephyr samples you want to build.


## Building the samples locally

Create and activate a Python virtual environment:
```sh
python -m venv .venv
. .venv/bin/activate
```

Install builder dependencies:
```sh
pip install -r requirements.txt
```

Source the versions file:

```sh
. .env
```

Prepare the build environment:

```sh
./scripts/prepare_sources.sh
```

Generate a list of targets to build:

```sh
./scripts/get_boards_samples_pairs.py -c zephyr.yaml > boards_sample_pairs
```

Run the sequential build using GNU Parallel:

```sh
parallel -j +0 --keep-order --col-sep " " --halt now,fail=1 ./scripts/build.py --config=zephyr.yaml {} -j {#} -J `wc -l < boards_sample_pairs` '::::' boards_sample_pairs
```

Or build a single target:

```sh
./scripts/build.py 'zephyrproject/zephyr/boards/96boards/aerocore2' '96b_aerocore2' 'hello_world' -c zephyr.yaml
```


## Artifacts

Artifacts generated during the build process:

* `elf`: Zephyr's kernel binary.
* `dts`: Platform's flattened Device Tree Source file.
* `config`: Additional Kconfig options used for the build.
* `build-log`: West build output and errors log.
* SPDX files:
  - `sbom-app`: SPDX for app source.
  - `sbom-build`: SPDX for build environment.
  - `sbom-zephyr`: SPDX for Zephyr components.
* ZIP files:
  - `zip-sbom`: ZIP archive of all SBOM files.
* JSON files:
  - `result`: Build outcome JSON file.

---

The `result.json` file consists the following keys:

* `platform`: The platform (board) on which the sample was built.
* `platform_full_name`: Full platform name from the board `yaml` file.
* `arch`: The platform's CPU architecture.
* `sample_name`: The name of the Zephyr sample.
* `success`: Indicates if the build was successful.
* `extended_memory`: Indicates if memory was extended during the build.
* `configs`: Configuration settings used for the build, or null if not present.
* `zephyr_sha`: SHA of the Zephyr version used for the build.
* `zephyr_sdk`: Zephyr SDK version used for the build.
* `board_dir`: Board directory in Zephyr tree.
* `memory`: Memory size and usage.
* `dts_include_chain`: Device Tree include chain.
