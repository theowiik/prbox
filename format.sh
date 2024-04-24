#!/bin/bash

echo "Running autoflake..."
autoflake --in-place --remove-all-unused-imports --recursive .

echo "Running black..."
black .

echo "Running isort..."
isort .

echo "Running mdformat..."
mdformat .

echo "Formatting complete."
