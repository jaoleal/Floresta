# Prepares a temporary environment to run our tests
#
# This script should be executed atleast once, before running our functinal test.
#
## What this script do  ?
# It basically checks if we have all dependencies needed to run our tests. Failing if not.
# One can use this to ensure that he have all the tooling needed to run the tests. if this script returns 0, that means, got executed sucessfully,
# youll be able to run our tests.
#
# This is a big scope for a single script, so what it really does is
#
#  1. Check if packages these packages:
#   - go: for building utreexod.
#   - cargo (rustup implied): for building floresta binaries.
#   - uv: for resolving and dealing with python deps.
#  are available in $PATH.
#
#  2. To avoid collision between versions of the Floresta project, this script sets a
# temporary directory to store and load binaries. What actually make this avoid collision
# is using the commit hash when creating the directory. Only one binary will exist for this
# commit hash. Hash collisions are known but rare enough for this to work.
#
#  3. Clone and build Utreexod and build Florestad and store them inside the temp dir.

# We expect the current dir is the root dir of the project.
FLORESTA_PROJ_DIR=$(pwd)
# This helps us to keep track of the actual version being tested without conflicting with any already installed binaries.
HEAD_COMMIT_HASH=$(git rev-parse HEAD)

TEMP_DIR="/tmp/floresta-integration-tests.${HEAD_COMMIT_HASH}"


go version &>/dev/null

if [ $? -ne 0 ]
then
	echo "You must have golang installed to run those tests!"
	exit 1
fi


cargo version &>/dev/null

if [ $? -ne 0 ]
then
	echo "You must have rust with cargo installed to run those tests!"
	exit 1
fi

uv -V  &>/dev/null

if [ $? -ne 0 ]
then
	echo "You must have uv installed to run those tests!"
	exit 1
fi



ls $TEMP_DIR &>/dev/null
if [ $? -ne 0 ]
then
	echo "The tests dir for the tests does not exist. Creating it..."
	# Dont use mktemp so we can have deterministic results for each version of floresta.
	mkdir -p "$TEMP_DIR"
fi

echo "$TEMP_DIR already exists. If you need, you can delete it with"
echo "$ rm -rf $TEMP_DIR"
echo " Or, if you just need to start fresh."

cd $TEMP_DIR/

# Download and build utreexod
ls -la utreexod &>/dev/null
if [ $? -ne 0 ]
then
    echo "Utreexo not found on $TEMP_DIR/utreexod."
    echo "Downloading utreexod..."
	git clone https://github.com/utreexo/utreexod &>/dev/null
	echo "Building utreexod..."
	cd utreexod
    go build . &>/dev/null
fi

# Build floresta setting the specific version of this build to the one we are testing
ls -la $TEMP_DIR/florestad &>/dev/null
if [ $? -ne 0 ]
then
    echo "Floresta not found on $TEMP_DIR/florestad."
    echo "Building florestad..."
    cd $FLORESTA_PROJ_DIR
    cargo build --bin florestad --features json-rpc --target-dir $TEMP_DIR/florestad &>/dev/null
fi


echo "You should be able to run ./tests/run.sh"
exit 0
