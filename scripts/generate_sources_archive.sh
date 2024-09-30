#!/bin/bash
set -e

WORKSPACE=`mktemp -d`
CURDIR=`pwd`

echo "Obtaining Zephyr $ZEPHYR_VERSION..."
cd $WORKSPACE
wget -q https://github.com/zephyrproject-rtos/zephyr/archive/$ZEPHYR_VERSION.zip

echo "Decompressing..."
unzip -q $ZEPHYR_VERSION.zip

echo "Cleaning up..."
cd zephyr-$ZEPHYR_VERSION

find . -type d -iname "doc" -exec rm -rf "{}" \; 2>/dev/null || true
find . -type d -iname "docs" -exec rm -rf "{}" \; 2>/dev/null || true
find . -type f -iname "*.jpg" -exec rm -rf "{}" \; 2>/dev/null || true
find . -type f -iname "*.png" -exec rm -rf "{}" \; 2>/dev/null || true
find . -type f -iname "*.jpeg" -exec rm -rf "{}" \; 2>/dev/null || true
find . -type f -iname "*.pyc" -exec rm -rf "{}" \; 2>/dev/null || true

rm -rf .git
rm -rf .github
rm -rf tests

cd ~-

echo "Compressing again..."
zip -q -r zephyr-$ZEPHYR_VERSION.zip zephyr-$ZEPHYR_VERSION

cp zephyr-$ZEPHYR_VERSION.zip $CURDIR
rm -rf $WORKSPACE
