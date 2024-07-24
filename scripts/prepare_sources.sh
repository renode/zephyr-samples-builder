#!/bin/bash
set -euxo pipefail

# This script does not work for SDK versions below 0.16.0
# This is caused by an URL change from Zephyr SDK release pages

# Download and patch MicroPython
mkdir -p micropython
cd micropython
git init > /dev/null 2> /dev/null
git remote add origin https://github.com/micropython/micropython
git pull --depth 1 origin ${MICROPYTHON_VERSION} > /dev/null 2> /dev/null
git am ../patches/micropython/*.patch
cd ..

# Download and patch Zephyr
mkdir -p zephyrproject/zephyr
cd zephyrproject/zephyr
git init > /dev/null 2> /dev/null
git remote add origin https://github.com/zephyrproject-rtos/zephyr
git pull --depth 1 origin ${ZEPHYR_VERSION} > /dev/null 2> /dev/null

# Prepare zephyr-rust application
mkdir -p zephyr-rust
cd zephyr-rust
git init > /dev/null 2> /dev/null
git remote add origin https://github.com/tylerwhall/zephyr-rust
git pull --depth 1 origin ${ZEPHYR_RUST_VERSION} > /dev/null 2> /dev/null
git submodule update --init --recursive  > /dev/null 2> /dev/null
git am ../../../patches/zephyr-rust/*.patch
rm -rf .git
cd ../../..

# Download Zephyr SDK
mkdir -p zephyr-sdk
curl -kLs https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64.tar.xz | tar xJ --strip 1 -C zephyr-sdk &
ZEPHYR_SDK_BG=$!

# Install Zephyr requirements (west)
cd zephyrproject/zephyr
pip3 -q install -r scripts/requirements.txt
cd -

# Wait for download and unpacking of SDK to finish.
# This should fail if the download failed.
wait "$ZEPHYR_SDK_BG"

# Zephyrproject setup
west init -l zephyrproject/zephyr
cd zephyrproject
west config manifest.group-filter -- +ci,+optional

for i in $(seq 1 5)
do
    echo try $i of 5
    west update >> /dev/null 2>&1 && break || sleep 5;
done

west zephyr-export
cd ..

# Prepare Kenning Zephyr Runtime Demo application
# This demo uses a custom workspace (west.yaml configuration)
mkdir -p kenning-zephyr-workspace/kenning-zephyr-runtime
cd kenning-zephyr-workspace/kenning-zephyr-runtime
git init > /dev/null 2> /dev/null
git remote add origin https://github.com/antmicro/kenning-zephyr-runtime
git pull --depth 1 origin ${KENNING_ZEPHYR_RUNTIME_VERSION} > /dev/null 2> /dev/null

# Initialize another zephyr workspace
west init -l .
west update
west zephyr-export

# Prepare required modules
./scripts/prepare_modules.sh

# Checkout proper Zephyr version for the kenning samples
cd ../zephyr
git checkout $ZEPHYR_VERSION
cd ../..

