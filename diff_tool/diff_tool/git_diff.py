import fnmatch
import logging
import os
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
        
        split_dir = f"{os.path.splitext(output_file)[0]}_split"
        os.makedirs(split_dir, exist_ok=True)
        
        with open(output_file, "w") as diff_file:
            subprocess.run(
                ["git", "diff", "--no-index", old_dir, new_dir, "--diff-filter=d"],
                stdout=diff_file,
                text=True,
                check=True,
            )
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:  # Git diff returns 1 if there are differences
            logging.info(
                "Diff generated successfully (non-zero exit code is expected for differences)."
            )
        else:
            logging.error(f"Error generating diff between directories: {e}")
            
    logging.info(f"Checking directory: {new_dir}")
    try:
        if not os.path.exists(new_dir):
            logging.error(f"Directory does not exist: {new_dir}")
            return
            
        contents = os.listdir(new_dir)
        logging.info(f"Directory contents: {contents}")
        
        if not contents:
            logging.warning(f"Directory is empty: {new_dir}")
            return
            
        for package_dir in contents:
            logging.info(f'Creating chunk file for: {package_dir}')
            old_package_path = os.path.join(old_dir, package_dir)
            new_package_path = os.path.join(new_dir, package_dir)
            
            if not os.path.exists(new_package_path):
                logging.warning(f"Package path does not exist: {new_package_path}")
                continue

            if not os.path.exists(old_package_path):
                os.makedirs(old_package_path)
                logging.info(f"Created directory: {old_package_path}")

            
            package_diff_file = os.path.join(split_dir, f"{package_dir}.patch")
            
            try:
                with open(package_diff_file, "w") as diff_file:
                    subprocess.run(
                        ["git", "diff", "--no-index", old_package_path, new_package_path, "--diff-filter=d"],
                        stdout=diff_file,
                        text=True,
                        check=True,
                    )
                # Check file size and delete if empty
                if os.path.getsize(package_diff_file) == 0:
                    os.remove(package_diff_file)
                    logging.info(f"Deleted empty diff file: {package_diff_file}")
                else:
                    logging.info(f"Package diff written to {package_diff_file}")
            except subprocess.CalledProcessError as e:
                if e.returncode != 1:  # Ignore expected diff return code
                    logging.error(f"Error generating diff for package {package_dir}: {e}")

    except OSError as e:
        logging.error(f"Error accessing directory {new_dir}: {e}")
                
    logging.info(f"Main diff file written to {output_file}")
    logging.info(f"Split diffs written to {split_dir}")
        
    
