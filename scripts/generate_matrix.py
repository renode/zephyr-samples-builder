#!/usr/bin/env python3
import os

# Get the number of runners from the environment variable 'MATRIX_RUNNERS', default to 2
jobs = int(os.getenv("MATRIX_RUNNERS", "2"))

# Generate a matrix configuration with runner numbers
print({"runner": list(range(1, jobs + 1))})
