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
pushd rust/rust
git am ../../../../../patches/rust/*.patch
popd
rm -rf .git
cd ../../..

# Download Zephyr SDK
./scripts/fetch_sdk.sh &
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

# Download Zephyr maintained rust sample
mkdir -p zephyr_rust/apptest
cd zephyr_rust/apptest
git init
git remote add origin https://github.com/zephyrproject-rtos/zephyr-lang-rust
git pull --depth 1 origin main
cd ..
west init -l apptest --mf ci-manifest.yml
west update -o=--depth=1 -o=--no-tags -n
cd ..

# Prepare Kenning Zephyr Runtime Demo application
# This demo uses a custom workspace (west.yaml configuration)
mkdir -p kenning-zephyr-workspace/kenning-zephyr-runtime

if [[ "$BUILD_KZR_ONLY" == "true" ]]; then
    cd kenning-zephyr-workspace
    git clone https://github.com/antmicro/kenning-zephyr-runtime kenning-zephyr-runtime > /dev/null 2> /dev/null
    cd kenning-zephyr-runtime
    echo "using latest KZR version"
else
    cd kenning-zephyr-workspace/kenning-zephyr-runtime
    git init > /dev/null 2> /dev/null
    git remote add origin https://github.com/antmicro/kenning-zephyr-runtime
    git pull --depth 1 origin ${KENNING_ZEPHYR_RUNTIME_VERSION} > /dev/null 2> /dev/null
    echo "using KZR version from .env"
fi

# Initialize another zephyr workspace
west init -l .
west update -o=--no-tags
west zephyr-export

# Prepare required modules
./scripts/prepare_modules.sh

# Checkout proper Zephyr version for the kenning samples
cd ../zephyr
git checkout $ZEPHYR_VERSION
cd ../..

