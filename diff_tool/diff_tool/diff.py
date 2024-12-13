import argparse
import concurrent.futures
import logging
import os
import re
import sys
import tempfile
from functools import partial
from typing import Dict, Tuple
import time

from git_diff import generate_diff, get_dependencies
from sources import (
    download_dart_package_sources,
)
from summary import generate_summary_table
from git import GitCommandError, Repo
from tqdm import tqdm


def configure_logging(verbose: bool):
    level = logging.INFO if verbose else logging.ERROR
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    
    # File handler
    file_handler = logging.FileHandler('diff.log')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Console handler 
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def _process_single_package(
    package_name: str, 
    deps1: Dict,
    deps2: Dict,
    old_dir: str,
    new_dir: str,
    skip_unchanged: bool
) -> None:
    if skip_unchanged and package_name in deps1 and package_name in deps2:
        if deps1[package_name] == deps2[package_name]:
            logging.info(f"Skipping unchanged package: {package_name}")
            return

    if package_name in deps1:
        download_dart_package_sources(
            package_name, deps1[package_name], os.path.join(old_dir, package_name)
        )
    if package_name in deps2:
        download_dart_package_sources(
            package_name, deps2[package_name], os.path.join(new_dir, package_name)
        )


def process_packages(
    deps1: Dict, deps2: Dict, temp_dir: str, skip_unchanged: bool
) -> Tuple[str, str]:
    old_dir = os.path.join(temp_dir, "old", "code")
    new_dir = os.path.join(temp_dir, "new", "code")
    os.makedirs(old_dir, exist_ok=True)
    os.makedirs(new_dir, exist_ok=True)

    package_names = list(set(deps1.keys()) | set(deps2.keys()))
    process_fn = partial(
        _process_single_package,
        deps1=deps1,
        deps2=deps2,
        old_dir=old_dir,
        new_dir=new_dir,
        skip_unchanged=skip_unchanged
    )

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_fn, pkg) for pkg in package_names]
        for _ in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Processing packages"
        ):
            pass

    return old_dir, new_dir


def main(repo_path: str, ref1: str, ref2: str, skip_unchanged: bool):
    try:
        repo = Repo(repo_path)
        logging.info(f"Opened repository at {repo_path}.")
    except GitCommandError as e:
        logging.error(f"Error opening repository: {e}")
        sys.exit(1)

    packages_filter: list[str] = []
    deps1 = get_dependencies(repo, ref1, packages_filter)
    deps2 = get_dependencies(repo, ref2, packages_filter)

    with tempfile.TemporaryDirectory() as temp_dir:
        old_dir, new_dir = process_packages(deps1, deps2, temp_dir, skip_unchanged)

        summary_df = generate_summary_table(deps1, deps2)
        summary_df.to_csv('package_summary.csv', index=False)

        with open('package_summary.md', 'w') as f:
            f.write("# Package Dependencies Summary\n\n")
            f.write(summary_df.to_markdown(index=False))

        sane_ref1 = re.sub(r'[^\w_. -]', '_', ref1)
        sane_ref2 = re.sub(r'[^\w_. -]', '_', ref2)
        output_diff_file = os.path.abspath(f"{sane_ref1}_{sane_ref2}.patch")
        generate_diff(old_dir, new_dir, output_diff_file)

    logging.info(
        f"Dependency code diff process completed. Diff file saved to {output_diff_file}"
    )


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

    # TODO: --skip-unchanged or --no-skip-unchanged
    parser.add_argument(
        "--skip-unchanged",
        action="store_true",
        default=False,
        help="Skip unchanged dependencies based on pubspec.lock comparison",
    )

    args = parser.parse_args()
    configure_logging(args.verbose)
    main(args.repo_path, args.ref1, args.ref2, args.skip_unchanged)
