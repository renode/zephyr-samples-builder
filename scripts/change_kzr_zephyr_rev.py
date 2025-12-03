#!/usr/bin/env python3

import argparse
import yaml

p = argparse.ArgumentParser()
p.add_argument("-f", "--file", required=True)
p.add_argument("-r", "--revision", required=True)
args = p.parse_args()

with open(args.file) as f:
    data = yaml.safe_load(f)

for proj in data["manifest"]["projects"]:
    if proj.get("name") == "zephyr":
        proj["revision"] = args.revision
        break

with open(args.file, "w") as f:
    yaml.dump(data, f, sort_keys=False)
