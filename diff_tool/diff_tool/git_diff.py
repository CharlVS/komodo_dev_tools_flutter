import fnmatch
import logging
import subprocess
from typing import Any

import yaml
from git import GitCommandError, Repo


def get_dependencies(repo: Repo, ref: str, filter: list[str] = []) -> dict[str, dict]:
    try:
        logging.info(f"Extracting dependencies from pubspec.lock for ref {ref}.")
        pubspec_lock_content = repo.git.show(f"{ref}:pubspec.lock")
        pubspec_lock_data = yaml.safe_load(pubspec_lock_content)
        packages = pubspec_lock_data.get("packages", {})
        logging.info(f"Found {len(packages)} packages in {ref}.")

        filtered_packages = filter_packages_by_name(filter, packages)
        logging.info(f"Filtered out {len(filtered_packages)} packages.")
        logging.info(f"Remaining packages: {len(packages)}")

        return packages
    except (GitCommandError, yaml.YAMLError) as e:
        logging.error(f"Error processing pubspec.lock in ref {ref}: {e}")
        return {}


def filter_packages_by_name(exclude_filter: list[str], packages: dict[str, Any]):
    filtered_packages: dict[str, Any] = {}

    for package_name in list(packages.keys()):
        if any(
                fnmatch.fnmatch(package_name, pattern)
                for pattern in exclude_filter
            ):
            filtered_packages[package_name] = packages.pop(package_name)
            logging.info(f"Filtered package: {package_name}")

    return filtered_packages


def generate_diff(old_dir: str, new_dir: str, output_file: str) -> None:
    try:
        logging.info(f"Generating diff between {old_dir} and {new_dir}.")
        with open(output_file, "w") as diff_file:
            # ["git", "diff", "--no-index", old_dir, new_dir],
            subprocess.run(
                # ["git", "diff", "--no-index", old_dir + "/", new_dir + "/"],
                # ["git", "diff", "--no-index", "--no-prefix", old_dir, new_dir],
                # ["git", "diff", "--no-index", "--relative", old_dir, new_dir],
                ["git", "diff", "--no-index", old_dir, new_dir, "--diff-filter=d"],
                stdout=diff_file,
                text=True,
                check=True,
            )
        logging.info(f"Diff file written to {output_file}")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:  # Git diff returns 1 if there are differences
            logging.info(
                "Diff generated successfully (non-zero exit code is expected for differences)."
            )
        else:
            logging.error(f"Error generating diff between directories: {e}")
