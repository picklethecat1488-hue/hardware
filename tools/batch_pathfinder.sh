#!/bin/zsh

SCRIPT_DIR="${0:A:h}"
NUM_ITERATIONS=${1:-100}
MASTER_OUTPUT="out/pathfinder_output.txt"

# Run N attempts then concatenate all outputs into out/pathfinder_output.txt
cat "$SCRIPT_DIR/pathfinder_variants.txt" | parallel -j6 --tag --line-buffer "$(which python)" src/pathfinder.py {} -n ${NUM_ITERATIONS}
cat out/*/pathfinder_output.txt >> "$MASTER_OUTPUT"