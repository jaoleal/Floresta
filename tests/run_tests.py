"""
run_tests.py

Command Line Interface to run a test by its name. The name should be placed at ./tests folder.
It's suposed that you run it through `poetry` package management and `poe` task manager, but you
can run it with `python` if you installed the packages properly, in a isolated or not isolated
environment (althought we recommend the isolated environment).

All tests will run as a spwaned subprocess and what happens will be logged to a temporary directory
(we defined, in linux, /tmp/floresta-func-tests/<test_name>):

```bash
# The default way to run all tests
poetry run poe tests

# The default way to run a separated test (see the ones -- or define one -- in pyproject.toml)
poetry run poe example-test

# This will do the same thing in the isolated environment
poetry run python tests/run_tests.py --test-name example_test

# You can even define the `data_dir` to logs
poetry run python tests/run_tests.py --test-name example_test --data-dir $HOME/my/path

# If you have a proper environment wit all necessary packages installed
# it can be possible to run without poetry
python tests/run_tests.py --test-name example_test --data-dir $HOME/my/path
```
"""

import os
import subprocess
import time
import argparse
import tempfile


BASE_DIR = os.path.normpath(os.path.join(tempfile.gettempdir(), "floresta-func-tests"))
SUCCESS_EMOJI = "✅"
FAILURE_EMOJI = "❌"
ALLDONE_EMOJI = "🎉"


def main():
    """
    Create a CLI called `run_tests` with calling arguments

    usage: run_tests [-h] [-d DATA_DIR] [-t TEST_NAME]

    tool to help with function testing of Floresta

    options:
        -h, --help                show this help message and exit
        -d, --data-dir DATA_DIR   data directory of the run_tests's functional test logs
    """
    # Structure the CLI
    parser = argparse.ArgumentParser(
        prog="run_tests",
        description="tool to help with function testing of Floresta",
    )

    parser.add_argument(
        "-d",
        "--data-dir",
        help="data directory of the %(prog)s's functional test logs",
        default=BASE_DIR,
    )

    parser.add_argument(
        "-t",
        "--test-suite",
        help="test-suit directory to be tested by %(prog)s's",
    )

    # Parse arguments of CLI
    args = parser.parse_args()

    # Setup directories and filenames for the specific test
    test_dir = os.path.abspath(os.path.dirname(__file__))
    test_suit = os.path.join(test_dir, args.test_suite)

    # search for all all tests
    # inside ./tests/<test-suite>/*-test.py
    for file in os.listdir(test_suit):
        if file.endswith("-test.py"):

            # Define the data-dir and create it
            data_dir = os.path.normpath(os.path.join(args.data_dir, file))
            if not os.path.isdir(data_dir):
                os.makedirs(data_dir)

            # get test file and create a log for it
            test_filename = os.path.normpath(os.path.join(test_suit, file))
            test_logname = os.path.normpath(
                os.path.join(data_dir, f"{int(time.time())}.log")
            )
            # Now start the test
            with open(test_logname, "wt", encoding="utf-8") as log_file:
                cli = ["python", test_filename]
                cli_msg = " ".join(cli)
                print(f"Running '{cli_msg}'")
                with subprocess.Popen(cli, stdout=log_file, stderr=log_file) as test:
                    test.wait()
                    print(f"Writing stuff to {test_logname}")

            # Check the test, if failed, log the results
            # if passed, just show that worked
            if test.returncode != 0:
                print(f"Test {file} not passed {FAILURE_EMOJI}")
                with open(test_logname, "rt", encoding="utf-8") as log_file:
                    raise RuntimeError(f"Tests failed: {log_file.read()}")

            print(f"Test {file} passed {SUCCESS_EMOJI}")
            print()


if __name__ == "__main__":
    main()
    print("🎉 ALL TESTS PASSED! GOOD JOB!")
