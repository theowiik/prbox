#!/bin/bash

ruff format .
ruff check --fix
ruff check --select=I --fix
