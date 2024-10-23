#!/bin/bash

autoflake --in-place --remove-all-unused-imports --recursive .
black .
isort .
mdformat .