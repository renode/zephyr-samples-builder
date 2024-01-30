# Zephyr Samples Builder

Copyright (c) 2023-2024 [Antmicro](https://www.antmicro.com)

A GitHub Actions workflow for building Zephyr RTOS samples for multiple platforms.

## Overview

This repository contains a GitHub Actions workflow that automatically builds Zephyr RTOS samples using the provided `zephyr.yaml` file.

## Configuration

Edit the `zephyr.yaml` file to define the Zephyr samples you want to build.

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

## Requesting a build for a specific version of Zephyr

The `gh` tool can be used to trigger a workflow with a hash provided as argument:

	gh workflow run Build --ref main -f zephyr_version=8873c0784772413ee521abae4b9129dd7cd9e3ee

A full hash representing a commit in the Zephyr repository must be provided.
