#!/usr/bin/env bash
# M12c overnight queue (Git Bash, from the main checkout with the editable install):
#
#     bash scripts/overnight_m12c.sh 0.8 1.0              # the bench slacks, in the order to run them
#     bash scripts/overnight_m12c.sh --dry-run 0.8 1.0    # print the commands, run nothing
#
# The steps and their command lines come from `python -m brickwfc.experiments.overnight steps <slacks>` (see its
# docstring): hollow1 arms, the reconnected 6378-1 chair, then the bench. One heavy job at a time. Each step is
# resumable (rerun the script: finished runs are skipped). Everything goes to out/m12b_complete/overnight.log:
# estimated minutes per step at the top, then per step "START <name>", its output, and "STEP_DONE <name>" or
# "STEP_FAILED <name>" (a failed step does not stop the queue), and "ALL_DONE" at the end.
set -u
cd "$(dirname "$0")/.." || exit 1

DRY_RUN=0
SLACKS=()
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then DRY_RUN=1; else SLACKS+=("$arg"); fi
done
if [ "${#SLACKS[@]}" -eq 0 ]; then
    echo "usage: bash scripts/overnight_m12c.sh [--dry-run] SLACK [SLACK ...]   (e.g. 0.8 1.0)" >&2
    exit 2
fi

# The step list first, so an unknown slack fails before anything runs.
mapfile -t STEPS < <(python -m brickwfc.experiments.overnight steps "${SLACKS[@]}") || exit 1
if [ "${#STEPS[@]}" -eq 0 ]; then
    echo "no steps (see the error above)" >&2
    exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
    python -m brickwfc.experiments.overnight estimate "${SLACKS[@]}"
    for step in "${STEPS[@]}"; do
        printf '%s\n' "${step#*$'\t'}"
    done
    exit 0
fi

LOG=out/m12b_complete/overnight.log
mkdir -p out/m12b_complete
{
    echo "=== overnight_m12c $(date '+%Y-%m-%d %H:%M:%S'), slacks ${SLACKS[*]}, commit $(git rev-parse --short HEAD)"
    python -m brickwfc.experiments.overnight estimate "${SLACKS[@]}"
} >> "$LOG" 2>&1

for step in "${STEPS[@]}"; do
    name=${step%%$'\t'*}
    command=${step#*$'\t'}
    echo "START $name $(date '+%H:%M:%S'): $command" >> "$LOG"
    if eval "$command" < /dev/null >> "$LOG" 2>&1; then
        echo "STEP_DONE $name" >> "$LOG"
    else
        echo "STEP_FAILED $name" >> "$LOG"
    fi
done
echo "ALL_DONE" >> "$LOG"
