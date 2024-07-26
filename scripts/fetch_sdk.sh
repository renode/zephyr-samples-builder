#!/bin/bash
set -uxo pipefail 

max_attempts=5
sdk_dir="zephyr-sdk"
url="https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64.tar.xz"

mkdir -p "${sdk_dir}"

for i in $(seq 1 "${max_attempts}")
do
    echo "Download zephyr-sdk attempt ${i} out of ${max_attempts}"
    curl --insecure --location --silent "${url}" | tar xJ --strip 1 --directory "${sdk_dir}"
    retval=$?
    if [ ${retval} -ne 0 ]; then
        echo "Failed to download zephyr-sdk"
        sleep 5s
    else
        echo "zephyr-sdk has been downloaded"
        exit 0
    fi
done

exit 1
