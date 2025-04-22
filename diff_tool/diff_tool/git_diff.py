import fnmatch
import logging
import os
import subprocess
from typing import Any, Tuple, Optional

import yaml
from git import GitCommandError, Repo


def get_dependencies(
    repo: Repo, ref: str, filter: list[str] = [], include_filter: list[str] = []
) -> dict[str, dict]:
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


def filter_packages_by_name(
    exclude_filter: list[str], packages: dict[str, Any], include_filter: list[str] = []
) -> dict[str, Any]:
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
            fnmatch.fnmatch(package_name, pattern) for pattern in include_filter
        )

        # If not explicitly included, check if it should be excluded
        should_exclude = (
            not explicitly_included
            and exclude_filter
            and any(
                fnmatch.fnmatch(package_name, pattern) for pattern in exclude_filter
            )
        )

        if should_exclude:
            filtered_packages[package_name] = packages.pop(package_name)
            logging.info(f"Excluded package: {package_name}")
        elif explicitly_included:
            logging.info(f"Explicitly included package: {package_name}")

    return filtered_packages


def get_git_error_message(return_code: int) -> str:
    """
    Return a more descriptive message for common Git error codes.

    Args:
        return_code: Git command return code

    Returns:
        Human-readable error description
    """
    error_messages = {
        1: "Differences were found (normal for git diff)",
        128: "Fatal Git error - possibly bad reference or corrupted repository",
        129: "Usage error - incorrect arguments provided to Git",
        130: "Git process terminated by user signal",
    }

    return error_messages.get(return_code, f"Unknown Git error (code {return_code})")


def run_git_diff(
    old_path: str, new_path: str, output_file: str, diff_filter: str = "d"
) -> bool:
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
        old_exists = os.path.exists(old_path)
        new_exists = os.path.exists(new_path)

        if not old_exists or not new_exists:
            logging.error(
                f"Paths don't exist: old_path={old_path} ({old_exists}), new_path={new_path} ({new_exists})"
            )
            return False

        with open(output_file, "w") as diff_file:
            # Add options to handle binary files properly and suppress CRLF warnings
            completed_process = subprocess.run(
                [
                    "git",
                    "-c",
                    "core.safecrlf=false",
                    "diff",
                    "--no-index",
                    "--binary",
                    "--text",
                    old_path,
                    new_path,
                    f"--diff-filter={diff_filter}",
                ],
                stdout=diff_file,
                stderr=subprocess.PIPE,
                text=True,
                check=False,  # Don't raise exception, we'll handle return codes manually
            )

            if completed_process.returncode == 1:
                # Return code 1 means differences were found - this is expected behavior for git diff
                return True
            elif completed_process.returncode > 1:
                error_message = get_git_error_message(completed_process.returncode)
                stderr_output = completed_process.stderr.strip()
                logging.error(f"Git diff error: {error_message}")
                if stderr_output:
                    logging.error(f"Git stderr: {stderr_output}")
                return False
            return True
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
        logging.debug(f"Created directory: {directory}")


def cleanup_empty_file(file_path: str) -> bool:
    """Remove file if it's empty and return whether it was removed."""
    if os.path.exists(file_path) and os.path.getsize(file_path) == 0:
        os.remove(file_path)
        logging.warning(f"Deleted empty diff file: {file_path}")
        return True
    return False


def generate_package_diff(
    old_dir: str, new_dir: str, package_dir: str, split_dir: str
) -> bool:
    """
    Generate diff for a specific package directory.

    Returns:
        bool: True if diff generation was successful, False otherwise
    """
    logging.debug(f"Creating chunk file for: {package_dir}")
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
            logging.debug(f"Package diff written to {package_diff_file}")
        return True
    else:
        logging.error(f"Failed to generate diff for package: {package_dir}")
        return False


def generate_diff(
    old_dir: str,
    new_dir: str,
    output_file: str,
    deps1: dict[str, Any],
    deps2: dict[str, Any],
) -> tuple[bool, dict[str, dict]]:
    """
    Generate diff between two directories and split by subdirectories.

    Args:
        old_dir: Path to the old version directory
        new_dir: Path to the new version directory
        output_file: Path to write the diff output
        deps1: Dictionary of old dependencies
        deps2: Dictionary of new dependencies

    Returns:
        tuple: (success, unchanged_dependencies)
        - success: True if all diffs were generated successfully, False otherwise
        - unchanged_dependencies: Dictionary of package names to dependency info for unchanged dependencies
    """
    try:
        logging.info(f"Generating diff between {old_dir} and {new_dir}.")

        if deps1 is not None and deps2 is not None:
            filter_monorepo_packages(old_dir, deps1)
            filter_monorepo_packages(new_dir, deps2)

        split_dir = f"{os.path.splitext(output_file)[0]}_split"
        ensure_directory_exists(split_dir)

        main_diff_success = run_git_diff(old_dir, new_dir, output_file)
        if not main_diff_success:
            logging.error("Failed to generate main diff file")
            return False

        exists_and_valid, error_message = check_directory_exists(new_dir)
        if not exists_and_valid:
            logging.error(f"New directory check failed: {error_message}")
            return False

        failed_packages = []
        for package_dir in os.listdir(new_dir):
            package_success = generate_package_diff(
                old_dir, new_dir, package_dir, split_dir
            )
            if not package_success:
                failed_packages.append(package_dir)

        if failed_packages:
            failed_list = ", ".join(failed_packages)
            logging.error(
                f"Failed to generate diffs for {len(failed_packages)} packages: {failed_list}"
            )
            return False, {}

        logging.info(f"Main diff file written to {output_file}")
        logging.info(f"Split diffs written to {split_dir}")

        unchanged_dependencies = identify_unchanged_dependencies(deps1, deps2)
        logging.info(f"Found {len(unchanged_dependencies)} unchanged dependencies")
        if unchanged_dependencies:
            unchanged_file = f"{os.path.splitext(output_file)[0]}_unchanged.md"
            generate_unchanged_dependencies_report(
                unchanged_dependencies, unchanged_file
            )

        return True, unchanged_dependencies

    except OSError as e:
        logging.error(f"Error during diff generation: {e}")
        return False, {}


def filter_monorepo_packages(base_dir: str, deps: dict[str, Any]) -> None:
    """
    Filter out packages in monorepos that aren't referenced in dependencies.

    Args:
        base_dir: Base directory containing package directories
        deps: Dictionary of dependencies
    """
    if not os.path.exists(base_dir):
        return

    all_referenced_packages = set(deps.keys())

    # Also collect packages that might be referenced by a dependency_override or similar
    for pkg_info in deps.values():
        if isinstance(pkg_info, dict) and "dependency" in pkg_info:
            dependency_info = pkg_info.get("dependency", {})
            if isinstance(dependency_info, dict):
                all_referenced_packages.update(dependency_info.keys())

    for pkg_dir in os.listdir(base_dir):
        pkg_path = os.path.join(base_dir, pkg_dir)
        packages_dir = os.path.join(pkg_path, "packages")

        if os.path.isdir(packages_dir):
            logging.info(f"Found monorepo: {pkg_dir}")

            for subpkg in os.listdir(packages_dir):
                subpkg_path = os.path.join(packages_dir, subpkg)

                if not os.path.isdir(subpkg_path):
                    continue

                # Determine the likely package name (may need to extract from pubspec)
                # For now just using directory name as an approximation
                if subpkg not in all_referenced_packages:
                    logging.info(
                        f"Removing unreferenced package: {pkg_dir}/packages/{subpkg}"
                    )
                    try:
                        import shutil

                        shutil.rmtree(subpkg_path)
                    except Exception as e:
                        logging.warning(f"Failed to remove {subpkg_path}: {e}")


def _get_package_ref_info(pkg: dict[str, Any]) -> tuple[str, str]:
    """
    Extract reference type and value from a package.
    
    Returns a tuple of (ref_type, ref_value) where:
    - ref_type is either 'git', 'pub', or 'unknown'
    - ref_value is the actual reference value (sha256 or resolved-ref)
    
    Args:
        pkg: Dictionary containing package information
        
    Returns:
        Tuple of (ref_type, ref_value)
    """
    pkg_desc = pkg.get("description", {})
    if isinstance(pkg_desc, dict):
        sha256 = pkg_desc.get("sha256")
        if sha256:
            return "pub", sha256
            
    resolved_ref = pkg_desc.get("resolved-ref") if isinstance(pkg_desc, dict) else None
    if not resolved_ref:
        resolved_ref = pkg.get("resolved-ref")
    if resolved_ref:
        return "git", resolved_ref
        
    return "unknown", ""


def identify_unchanged_dependencies(
    deps1: dict[str, Any], deps2: dict[str, Any]
) -> dict[str, tuple[dict, dict]]:
    """
    Identify dependencies that haven't changed between two versions.

    A dependency is considered unchanged if:
    1. It has the same version 
    2. It has the same reference type (git or pub)
    3. It has the same reference value (sha256 or resolved-ref)

    If a package previously used a git reference but now uses a pub reference (or vice versa),
    it is considered changed even if the version is the same.

    Args:
        deps1: Dictionary of old dependencies
        deps2: Dictionary of new dependencies

    Returns:
        Dictionary mapping package names to tuples of (old_pkg_info, new_pkg_info) for unchanged dependencies
    """
    if deps1 is None or deps2 is None:
        return {}

    unchanged_deps = {}

    common_packages = set(deps1.keys()).intersection(set(deps2.keys()))
    for package_name in common_packages:
        old_pkg = deps1[package_name]
        new_pkg = deps2[package_name]

        if not isinstance(old_pkg, dict) or not isinstance(new_pkg, dict):
            continue

        if old_pkg["version"] != new_pkg["version"]:
            logging.debug(
                f"Version mismatch for package {package_name}: {old_pkg.get('version')} vs {new_pkg.get('version')}"
            )
            continue

        old_ref_type, old_ref_value = _get_package_ref_info(old_pkg)
        new_ref_type, new_ref_value = _get_package_ref_info(new_pkg)

        if old_ref_type != new_ref_type:
            logging.debug(
                f"Reference type change for {package_name}: {old_ref_type} -> {new_ref_type}"
            )
            continue
            
        if old_ref_value != new_ref_value:
            logging.debug(
                f"Reference value change for {package_name}: {old_ref_value} -> {new_ref_value}"
            )
            continue

        unchanged_deps[package_name] = (old_pkg, new_pkg)

    return unchanged_deps


def generate_unchanged_dependencies_report(
    unchanged_deps: dict[str, tuple[dict, dict]], output_file: str
) -> None:
    """
    Generate a report file listing all unchanged dependencies.

    Args:
        unchanged_deps: Dictionary mapping package names to tuples of (old_pkg_info, new_pkg_info)
        output_file: Path to write the report output
    """
    try:
        with open(output_file, "w") as f:
            f.write("# Unchanged Dependencies Report\n\n")
            f.write(
                "This file lists dependencies that remained unchanged between versions.\n"
            )
            f.write(
                "These dependencies resulted in empty diff files that were cleaned up.\n\n"
            )

            f.write("| Package | Version | Source | Old SHA/Ref | New SHA/Ref |\n")
            f.write("|---------|---------|--------|-----------|-----------|\n")

            for package_name in sorted(unchanged_deps.keys()):
                old_pkg_info, new_pkg_info = unchanged_deps[package_name]
                version = new_pkg_info.get("version", "N/A")
                source = new_pkg_info.get("source", "N/A")

                old_pkg_desc = old_pkg_info.get("description", {})
                if not isinstance(old_pkg_desc, dict):
                    old_pkg_desc = {}

                old_sha256 = old_pkg_desc.get("sha256")
                old_resolved_ref = old_pkg_desc.get("resolved-ref") or old_pkg_info.get(
                    "resolved-ref"
                )

                if old_sha256:
                    old_sha_or_ref = f"pub:{old_sha256}"
                elif old_resolved_ref:
                    old_sha_or_ref = f"git:{old_resolved_ref}"
                else:
                    old_sha_or_ref = "N/A"

                new_pkg_desc = new_pkg_info.get("description", {})
                if not isinstance(new_pkg_desc, dict):
                    new_pkg_desc = {}

                new_sha256 = new_pkg_desc.get("sha256")
                new_resolved_ref = new_pkg_desc.get("resolved-ref") or new_pkg_info.get(
                    "resolved-ref"
                )

                if new_sha256:
                    new_sha_or_ref = f"pub:{new_sha256}"
                elif new_resolved_ref:
                    new_sha_or_ref = f"git:{new_resolved_ref}"
                else:
                    new_sha_or_ref = "N/A"

                f.write(f"| {package_name} | {version} | {source} | {old_sha_or_ref} | {new_sha_or_ref} |\n")

        logging.info(f"Unchanged dependencies report written to {output_file}")
    except Exception as e:
        logging.error(f"Error generating unchanged dependencies report: {e}")
