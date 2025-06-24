# Bash Script to setup code coverage.
# Please run this at the root of the repo.

ROOT_FOLDER=$(pwd)

# same check installed from /tests/prepare.sh
check_installed() {
    if ! command -v "$1" &>/dev/null; then
        echo "You must have $1 installed to run those tests!"
        exit 1
    fi
}

export RUSTFLAGS="-C instrument-coverage"
    export LLVM_PROFILE_FILE="$ROOT_FOLDER/contrib/coverageflorestad_coverage-%p-%m.profraw"

rustup component add llvm-tools

llvm-profdata merge -sparse florestad_coverage-*.profraw -o florestad_coverage.profdata

