import argparse
import logging
import multiprocessing
import sys
import tempfile

from git import GitCommandError

from logging_utils import configure_logging
from package_processor import generate_output_files
from repo_utils import fetch_dependencies, validate_inputs


def main(repo_path: str, ref1: str, ref2: str, skip_unchanged: bool, skip_sdk_packages: bool, max_workers: int = None):
    try:
        # Validate inputs
        repo = validate_inputs(repo_path, ref1, ref2)
        
        # Fetch dependencies
        packages_filter = []
        deps1, deps2 = fetch_dependencies(repo, ref1, ref2, packages_filter)

        # Generate all outputs
        with tempfile.TemporaryDirectory() as temp_dir:
            output_diff_file = generate_output_files(
                deps1, deps2, ref1, ref2, temp_dir, 
                skip_unchanged, skip_sdk_packages, max_workers
            )
                
        logging.info(
            f"Dependency code diff process completed successfully. Diff file saved to {output_diff_file}"
        )
    except ValueError as e:
        logging.error(str(e))
        sys.exit(1)
    except GitCommandError as e:
        logging.error(f"Git error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Process failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Generate dependency code diffs between two Git refs."
    )
    parser.add_argument("repo_path", help="Path to the Git repository")
    parser.add_argument("ref1", help="Old Git reference (e.g., commit hash)")
    parser.add_argument("ref2", help="New Git reference (e.g., commit hash)")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable detailed logging output"
    )
    parser.add_argument(
        "--skip-unchanged",
        action="store_true",
        default=False,
        help="Skip unchanged dependencies based on pubspec.lock comparison",
    )
    parser.add_argument(
        "--skip-sdk-packages",
        action="store_true",
        default=False,
        help="Skip Flutter SDK packages from being included in the diff (default: False)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help=f"Maximum number of worker threads (default: CPU count = {multiprocessing.cpu_count()})",
    )

    args = parser.parse_args()
    configure_logging(args.verbose)
    main(args.repo_path, args.ref1, args.ref2, args.skip_unchanged, args.skip_sdk_packages, args.max_workers)
