# Prepares a temporary environment to run our tests
#
# This script should be executed after prepare.sh. For running our functinal test.
#
## What this script do  ?
# Since we have a deterministic temporary path and we expect it to be already created. Because one thats running this script already runned ./tests/prepare.sh
#
# This script is simple:
#
# 1. Sets $PATH to include the compiled florestad and utreexod.
#
# 2. Run all needed commands for batch executing all python tests suites:
#
#       uv run tests/run_tests.py

# Before we start actually doing things, we check if this script isnt being run by nix.
# If it is, we dont want to mess with variables and let nix do its job.
# Otherwise, if this is being run by a user, we want to set the PATH to include the compiled binaries.

find_binaries() {
    # We will after this to find our tests.
    FLORESTA_PROJ_DIR=$(pwd)

    # This helps us to keep track of the actual version being tested without conflicting with any already installed binaries.
    HEAD_COMMIT_HASH=$(git rev-parse HEAD)

    # Since its deterministic how we make the setup, we already know where to search for the binaries to be testing.
    TEMP_DIR="/tmp/floresta-integration-tests.${HEAD_COMMIT_HASH}"

    UTREEXOD_BIN_DIR="$TEMP_DIR/utreexod"
    FLORESTA_BIN_DIR=""$TEMP_DIR/florestad/debug""

    ls $TEMP_DIR &>/dev/null
    if [ $? -ne 0 ]
    then
        echo "The expected test dir for this version of floresta isnt setted yet."
        echo "Did you run prepare.sh? Please read the README.md file."
	    exit 1
    fi

    # Here we save the original path from the bash session to restore it later. Cmon, we are not savages.
    ORIGINAL_PATH=$PATH

    # We add the generated binaries for testing to the PATH.
    export PATH="$FLORESTA_BIN_DIR:$UTREEXO_BIN_DIR:$PATH"
}

if [[ ! -v IS_RUNNING_BY_NIX ]]; then
    find_binaries
fi
cd "$FLORESTA_PROJ_DIR/"
uv run 

if [[ ! -v IS_RUNNING_BY_NIX ]]; then
    # Restores the original PATH
    export PATH=$ORIGINAL_PATH
fi