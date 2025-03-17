import fnmatch
import logging
import os
import subprocess
from typing import Any, Dict, List, Tuple, Optional

import yaml
from git import GitCommandError, Repo


def get_dependencies(repo: Repo, ref: str, filter: list[str] = [], include_filter: list[str] = []) -> dict[str, dict]:
    """
    Extract dependencies from pubspec.lock file at a specific Git reference.
    
    Args:
        repo: Git repository object
        ref: Git reference (commit, branch, tag)
        filter: List of glob patterns to exclude packages
        include_filter: List of glob patterns for packages to include
    
    Returns:
        Dictionary of package dependencies
    """
    try:
        logging.info(f"Extracting dependencies from pubspec.lock for ref {ref}.")
        pubspec_lock_content = repo.git.show(f"{ref}:pubspec.lock")
        pubspec_lock_data = yaml.safe_load(pubspec_lock_content)
        packages = pubspec_lock_data.get("packages", {})
        logging.info(f"Found {len(packages)} packages in {ref}.")

        filtered_packages = filter_packages_by_name(filter, packages, include_filter)
        logging.info(f"Filtered out {len(filtered_packages)} packages.")
        logging.info(f"Remaining packages: {len(packages)}")

        return packages
    except (GitCommandError, yaml.YAMLError) as e:
        logging.error(f"Error processing pubspec.lock in ref {ref}: {e}")
        return {}


def filter_packages_by_name(exclude_filter: list[str], packages: dict[str, Any], 
                           include_filter: list[str] = []) -> dict[str, Any]:
    """
    Filter packages by name using glob patterns.
    
    Args:
        exclude_filter: List of glob patterns to exclude
        packages: Dictionary of packages to filter
        include_filter: List of glob patterns to include (takes precedence over exclude)
    
    Returns:
        Dictionary of filtered packages that were removed from the input
    """
    filtered_packages: dict[str, Any] = {}
    package_names = list(packages.keys())
    
    for package_name in package_names:
        # Check if package should be included regardless of exclude filter
        explicitly_included = include_filter and any(
            fnmatch.fnmatch(package_name, pattern) 
            for pattern in include_filter
        )
        
        # If not explicitly included, check if it should be excluded
        should_exclude = not explicitly_included and exclude_filter and any(
            fnmatch.fnmatch(package_name, pattern)
            for pattern in exclude_filter
        )
            
        if should_exclude:
            filtered_packages[package_name] = packages.pop(package_name)
            logging.info(f"Excluded package: {package_name}")
        elif explicitly_included:
            logging.info(f"Explicitly included package: {package_name}")
    
    return filtered_packages

def run_git_diff(old_path: str, new_path: str, output_file: str, diff_filter: str = "d") -> bool:
    """
    Run git diff and write output to file, handling error codes appropriately.
    
    Args:
        old_path: Path to the old version directory
        new_path: Path to the new version directory
        output_file: Path to write the diff output
        diff_filter: Git diff filter option
    
    Returns:
        True if diff was generated successfully, False otherwise
    """
    try:
        # Validate paths exist before proceeding
        old_exists = os.path.exists(old_path)
        new_exists = os.path.exists(new_path)
        
        if not old_exists or not new_exists:
            logging.error(f"Paths don't exist: old_path={old_path} ({old_exists}), new_path={new_path} ({new_exists})")
            return False
        
        with open(output_file, "w") as diff_file:
            # Add options to handle binary files properly and suppress CRLF warnings
            subprocess.run(
                ["git", "-c", "core.safecrlf=false", "diff", "--no-index", "--binary", "--text", 
                 old_path, new_path, f"--diff-filter={diff_filter}"],
                stdout=diff_file,
                text=True,
                check=True,
            )
        return True
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:  # Git diff returns 1 if there are differences
            return True  # This is actually a success case for git diff
        else:
            logging.error(f"Error running git diff: {e}")
            return False
    except Exception as e:
        logging.error(f"Unexpected error during git diff: {e}")
        return False

def check_directory_exists(directory: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a directory exists and provide detailed status information.
    
    Args:
        directory: Directory path to check
    
    Returns:
        Tuple of (exists_and_valid, error_message)
        - exists_and_valid: True if directory exists and contains files
        - error_message: Error message if any, None otherwise
    """
    if not os.path.exists(directory):
        error_message = f"Directory does not exist: {directory}"
        logging.error(error_message)
        return False, error_message
        
    contents = os.listdir(directory)
    if not contents:
        error_message = f"Directory is empty: {directory}"
        logging.warning(error_message)
        return False, error_message
        
    logging.info(f"Directory contents of {directory}: {len(contents)} items")
    return True, None

def ensure_directory_exists(directory: str) -> None:
    """Create directory if it doesn't exist."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"Created directory: {directory}")

def cleanup_empty_file(file_path: str) -> bool:
    """Remove file if it's empty and return whether it was removed."""
    if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
        os.remove(file_path)
        logging.info(f"Deleted empty diff file: {file_path}")
        return True
    return False

def generate_package_diff(old_dir: str, new_dir: str, package_dir: str, split_dir: str) -> bool:
    """
    Generate diff for a specific package directory.
    
    Returns:
        bool: True if diff generation was successful, False otherwise
    """
    logging.info(f'Creating chunk file for: {package_dir}')
    old_package_path = os.path.join(old_dir, package_dir)
    new_package_path = os.path.join(new_dir, package_dir)
    
    if not os.path.exists(new_package_path):
        logging.warning(f"Package path does not exist: {new_package_path}")
        return True  # Not a failure since the package doesn't exist in new dir
    
    ensure_directory_exists(old_package_path)
    
    package_diff_file = os.path.join(split_dir, f"{package_dir}.patch")
    
    success = run_git_diff(old_package_path, new_package_path, package_diff_file)
    if success:
        if not cleanup_empty_file(package_diff_file):
            logging.info(f"Package diff written to {package_diff_file}")
        return True
    else:
        logging.error(f"Failed to generate diff for package: {package_dir}")
        return False

def generate_diff(old_dir: str, new_dir: str, output_file: str) -> bool:
    """
    Generate diff between two directories and split by subdirectories.
    
    Returns:
        bool: True if all diffs were generated successfully, False otherwise
    """
    try:
        logging.info(f"Generating diff between {old_dir} and {new_dir}.")
        
        split_dir = f"{os.path.splitext(output_file)[0]}_split"
        ensure_directory_exists(split_dir)
        
        # Generate main diff file
        main_diff_success = run_git_diff(old_dir, new_dir, output_file)
        if not main_diff_success:
            logging.error("Failed to generate main diff file")
            return False
            
        # Check if new directory exists and has contents
        exists_and_valid, error_message = check_directory_exists(new_dir)
        if not exists_and_valid:
            logging.error(f"New directory check failed: {error_message}")
            return False
        
        # Generate individual package diffs
        failed_packages = []
        for package_dir in os.listdir(new_dir):
            package_success = generate_package_diff(old_dir, new_dir, package_dir, split_dir)
            if not package_success:
                failed_packages.append(package_dir)
        
        if failed_packages:
            failed_list = ", ".join(failed_packages)
            logging.error(f"Failed to generate diffs for {len(failed_packages)} packages: {failed_list}")
            return False
                
        logging.info(f"Main diff file written to {output_file}")
        logging.info(f"Split diffs written to {split_dir}")
        return True
        
    except OSError as e:
        logging.error(f"Error during diff generation: {e}")
        return False


