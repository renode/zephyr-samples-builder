#!/usr/bin/env python3

import argparse
import yaml

p = argparse.ArgumentParser()
p.add_argument("-f", "--file", required=True)
p.add_argument("-r", "--revision", required=True)
p.add_argument("--tflite-micro-revision", default="zephyr-v4.4.0")
args = p.parse_args()

with open(args.file) as f:
    data = yaml.safe_load(f)

for proj in data["manifest"]["projects"]:
    if proj.get("name") == "zephyr":
        proj["revision"] = args.revision
    elif proj.get("name") == "tflite-micro":
        proj["revision"] = args.tflite_micro_revision

with open(args.file, "w") as f:
    yaml.dump(data, f, sort_keys=False)
