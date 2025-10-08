import configparser
import logging
import os
from typing import Dict, List, Optional, Any, Set

import pandas as pd
import yaml
from git import Repo, GitCommandError


def _parse_gitmodules(worktree_path: str) -> Dict[str, str]:
    """
    Parse .gitmodules file from a worktree to build a map of submodule paths to names.

    Args:
        worktree_path: Path to the git worktree

    Returns:
        Dictionary mapping submodule paths to their names
    """
    gitmodules_path = os.path.join(worktree_path, ".gitmodules")
    submodule_map = {}

    if not os.path.exists(gitmodules_path):
        logging.debug(f"No .gitmodules file found in {worktree_path}")
        return submodule_map

    try:
        config = configparser.ConfigParser()
        config.read(gitmodules_path)

        for section in config.sections():
            if section.startswith("submodule"):
                name = (
                    section.split('"')[1]
                    if '"' in section
                    else section.replace("submodule ", "")
                )
                path = config.get(section, "path", fallback=None)
                if path:
                    submodule_map[path] = name
                    logging.debug(f"Found submodule: {name} at path {path}")

    except Exception as e:
        logging.warning(f"Failed to parse .gitmodules in {worktree_path}: {e}")

    return submodule_map


def _get_submodule_commit(worktree_path: str, submodule_path: str) -> Optional[str]:
    """
    Get the commit SHA of a submodule in a worktree.

    Args:
        worktree_path: Path to the git worktree
        submodule_path: Relative path to the submodule within the worktree

    Returns:
        Commit SHA string, or None if unavailable
    """
    try:
        repo = Repo(worktree_path)
        submodule_full_path = os.path.join(worktree_path, submodule_path)

        if not os.path.exists(submodule_full_path):
            logging.debug(f"Submodule path does not exist: {submodule_full_path}")
            return None

        # Try to get the submodule commit from the parent repo's index
        try:
            # Use git ls-tree to get the commit that the submodule is pinned to
            ls_tree_output = repo.git.ls_tree("HEAD", submodule_path)
            logging.debug(f"ls-tree output for {submodule_path}: {ls_tree_output}")
            # Output format: <mode> <type> <object> <file>
            # We want the third field (object/commit SHA)
            parts = ls_tree_output.split()
            if len(parts) >= 3:
                commit_sha = (
                    parts[2] if isinstance(parts[2], str) else parts[2].decode("utf-8")
                )
                logging.debug(f"Submodule {submodule_path} is at commit {commit_sha}")
                return commit_sha
            else:
                logging.debug(
                    f"ls-tree output had {len(parts)} parts, expected at least 3"
                )
        except (GitCommandError, IndexError) as e:
            logging.debug(f"ls-tree failed for {submodule_path}: {e}")
            # If that fails, try to get it from the submodule itself
            try:
                submodule_repo = Repo(submodule_full_path)
                commit_sha = submodule_repo.head.commit.hexsha
                logging.debug(f"Submodule {submodule_path} HEAD is at {commit_sha}")
                return commit_sha
            except Exception as e:
                logging.debug(
                    f"Failed to get submodule commit from submodule repo: {e}"
                )
                return None

    except Exception as e:
        logging.warning(f"Failed to get submodule commit for {submodule_path}: {e}")
        return None


def _is_path_in_submodule(path: str, submodule_map: Dict[str, str]) -> Optional[str]:
    """
    Check if a path points to or is within a submodule.

    Args:
        path: The path to check
        submodule_map: Dictionary mapping submodule paths to names

    Returns:
        The submodule path if the path is within a submodule, None otherwise
    """
    # Normalize the path
    normalized_path = path.replace("\\", "/").rstrip("/")

    for submodule_path in submodule_map.keys():
        normalized_submodule_path = submodule_path.replace("\\", "/").rstrip("/")

        # Check if the path starts with the submodule path
        if normalized_path == normalized_submodule_path or normalized_path.startswith(
            normalized_submodule_path + "/"
        ):
            return submodule_path

    return None


def _parse_workspace_packages(worktree_path: str) -> Set[str]:
    """
    Parse workspace packages from root pubspec.yaml.

    Args:
        worktree_path: Path to the git worktree

    Returns:
        Set of workspace package names
    """
    workspace_packages = set()

    if not worktree_path or not os.path.exists(worktree_path):
        logging.debug(f"Worktree path not available: {worktree_path}")
        return workspace_packages

    pubspec_path = os.path.join(worktree_path, "pubspec.yaml")

    if not os.path.exists(pubspec_path):
        logging.debug(f"No pubspec.yaml found at {pubspec_path}")
        return workspace_packages

    try:
        with open(pubspec_path, "r") as f:
            pubspec_data = yaml.safe_load(f)

        workspace_list = pubspec_data.get("workspace", [])
        if not workspace_list:
            logging.debug("No workspace section found in root pubspec.yaml")
            return workspace_packages

        logging.info(
            f"Found workspace with {len(workspace_list)} entries: {workspace_list}"
        )

        # For each workspace path, try to read its pubspec.yaml to get the package name
        for workspace_path in workspace_list:
            workspace_pubspec_path = os.path.join(
                worktree_path, workspace_path, "pubspec.yaml"
            )

            if os.path.exists(workspace_pubspec_path):
                try:
                    with open(workspace_pubspec_path, "r") as f:
                        workspace_pubspec_data = yaml.safe_load(f)

                    package_name = workspace_pubspec_data.get("name")
                    if package_name:
                        workspace_packages.add(package_name)
                        logging.debug(
                            f"Found workspace package: {package_name} at {workspace_path}"
                        )
                except Exception as e:
                    logging.warning(
                        f"Failed to parse workspace package at {workspace_path}: {e}"
                    )
            else:
                logging.debug(f"No pubspec.yaml found at {workspace_pubspec_path}")

        logging.info(
            f"Identified {len(workspace_packages)} workspace packages: {workspace_packages}"
        )

    except Exception as e:
        logging.warning(f"Failed to parse workspace packages from {pubspec_path}: {e}")

    return workspace_packages


def _get_worktree_commit(worktree_path: str) -> Optional[str]:
    """
    Get the git commit SHA of a worktree.

    Args:
        worktree_path: Path to the git worktree

    Returns:
        Commit SHA string, or None if unavailable
    """
    try:
        if not worktree_path or not os.path.exists(worktree_path):
            return None

        repo = Repo(worktree_path)
        commit_sha = repo.head.commit.hexsha
        logging.debug(f"Worktree at {worktree_path} is at commit {commit_sha}")
        return commit_sha
    except Exception as e:
        logging.warning(f"Failed to get commit for worktree {worktree_path}: {e}")
        return None


def generate_summary_table(
    deps1: Dict[str, Any],
    deps2: Dict[str, Any],
    old_dir: Optional[str] = None,
    new_dir: Optional[str] = None,
    old_worktree: Optional[str] = None,
    new_worktree: Optional[str] = None,
) -> pd.DataFrame:
    """
    Generate a summary table of package dependencies.

    Args:
        deps1: Old dependencies from pubspec.lock
        deps2: New dependencies from pubspec.lock
        old_dir: Base directory for old package contents (for hash calculation)
        new_dir: Base directory for new package contents (for hash calculation)
        old_worktree: Path to the old worktree (for submodule resolution)
        new_worktree: Path to the new worktree (for submodule resolution)

    Returns:
        DataFrame with package dependency summary
    """
    package_names = set(deps1.keys()) | set(deps2.keys())
    summary_data: List[Dict[str, Any]] = []

    # Parse submodule maps from worktrees if available
    logging.info(
        f"generate_summary_table called with old_worktree={old_worktree}, new_worktree={new_worktree}"
    )
    old_submodule_map = {}
    new_submodule_map = {}
    if old_worktree and os.path.exists(old_worktree):
        logging.info(f"Parsing .gitmodules from old worktree: {old_worktree}")
        old_submodule_map = _parse_gitmodules(old_worktree)
        logging.info(
            f"Found {len(old_submodule_map)} submodules in old worktree: {old_submodule_map}"
        )
    else:
        logging.warning(f"Old worktree not available or doesn't exist: {old_worktree}")
    if new_worktree and os.path.exists(new_worktree):
        logging.info(f"Parsing .gitmodules from new worktree: {new_worktree}")
        new_submodule_map = _parse_gitmodules(new_worktree)
        logging.info(
            f"Found {len(new_submodule_map)} submodules in new worktree: {new_submodule_map}"
        )
    else:
        logging.warning(f"New worktree not available or doesn't exist: {new_worktree}")

    # Parse workspace packages from worktrees
    old_workspace_packages = _parse_workspace_packages(old_worktree)
    new_workspace_packages = _parse_workspace_packages(new_worktree)

    # Get worktree commits for workspace package tracking
    old_worktree_commit = _get_worktree_commit(old_worktree)
    new_worktree_commit = _get_worktree_commit(new_worktree)

    # Add workspace packages to the package_names set
    all_workspace_packages = old_workspace_packages | new_workspace_packages
    package_names = package_names | all_workspace_packages

    if all_workspace_packages:
        logging.info(
            f"Including {len(all_workspace_packages)} workspace packages in summary: {all_workspace_packages}"
        )

    for package_name in package_names:
        status = "Updated"

        # Check if this is a workspace package
        is_old_workspace = package_name in old_workspace_packages
        is_new_workspace = package_name in new_workspace_packages

        # For workspace packages, use worktree commit as version
        if is_old_workspace or is_new_workspace:
            old_version = (
                old_worktree_commit[:8]
                if is_old_workspace and old_worktree_commit
                else "-"
            )
            new_version = (
                new_worktree_commit[:8]
                if is_new_workspace and new_worktree_commit
                else "-"
            )
            dependency = "workspace"

            # Use full commit SHA as the identifier
            old_sha256 = (
                f"git:{old_worktree_commit}"
                if is_old_workspace and old_worktree_commit
                else "-"
            )
            new_sha256 = (
                f"git:{new_worktree_commit}"
                if is_new_workspace and new_worktree_commit
                else "-"
            )
        else:
            # Regular dependency from pubspec.lock
            old_version = deps1.get(package_name, {}).get("version", "-")
            new_version = deps2.get(package_name, {}).get("version", "-")
            dependency = deps1.get(package_name, deps2.get(package_name, {})).get(
                "dependency", "-"
            )

            old_sha256 = get_sha256_from_package_info(
                deps1.get(package_name, {}), old_worktree, old_submodule_map
            )
            new_sha256 = get_sha256_from_package_info(
                deps2.get(package_name, {}), new_worktree, new_submodule_map
            )

        identicalHashes = old_sha256 != "-" and old_sha256 == new_sha256
        identicalVersions = old_version == new_version and old_sha256 == new_sha256
        if identicalHashes or identicalVersions:
            logging.debug(f"skipping package {package_name}: no change in sha256 hash")
            continue

        # Determine status
        if is_old_workspace or is_new_workspace:
            # For workspace packages, check presence in workspace lists
            if not is_old_workspace and is_new_workspace:
                status = "Added"
            elif is_old_workspace and not is_new_workspace:
                status = "Removed"
            # else: both present, already set to "Updated"
        else:
            # For regular dependencies, check presence in deps
            if package_name not in deps1:
                status = "Added"
            elif package_name not in deps2:
                status = "Removed"

        summary_data.append(
            {
                "Package": package_name,
                "Status": status,
                "Old version": old_version,
                "New version": new_version,
                "Dependency": dependency,
                "Old sha256": old_sha256,
                "New sha256": new_sha256,
            }
        )

    return pd.DataFrame(summary_data).sort_values(
        ["Status", "Package"], ascending=[True, True]
    )


def get_sha256_from_package_info(
    package_info: Dict[str, Any],
    worktree_path: Optional[str] = None,
    submodule_map: Optional[Dict[str, str]] = None,
) -> str:
    """
    Get the SHA-256 hash from package info or git reference for submodules.

    Args:
        package_info: The package information from pubspec.lock
        worktree_path: Path to the worktree (for submodule resolution)
        submodule_map: Dictionary mapping submodule paths to names

    Returns:
        SHA-256 hash string, or "-" if unavailable.
        Hash will be prefixed with 'pub:' for pub.dev packages or 'git:' for git/submodule refs
    """
    description = package_info.get("description", {})
    source = package_info.get("source", "")

    # Check if this is a path dependency that points to a submodule
    if source == "path" and worktree_path and submodule_map:
        logging.debug(f"Checking path dependency with worktree {worktree_path}")
        # Get the path from the description
        if isinstance(description, dict):
            path = description.get("path")
        elif isinstance(description, str):
            path = description
        else:
            path = None

        if path:
            logging.debug(
                f"Path dependency path: {path}, submodule_map: {submodule_map}"
            )
            # Check if this path is within a submodule
            submodule_path = _is_path_in_submodule(path, submodule_map)
            if submodule_path:
                logging.debug(f"Path {path} is in submodule {submodule_path}")
                # Get the commit SHA of the submodule
                commit_sha = _get_submodule_commit(worktree_path, submodule_path)
                if commit_sha:
                    logging.info(
                        f"Path dependency {path} is in submodule {submodule_path} at commit {commit_sha}"
                    )
                    return f"git:{commit_sha}"
                else:
                    logging.warning(
                        f"Failed to get commit SHA for submodule {submodule_path}"
                    )
            else:
                logging.debug(f"Path {path} is not in any submodule")

    # Check for pub.dev packages with SHA-256
    if isinstance(description, dict) and "sha256" in description:
        return f"pub:{description.get('sha256')}"

    # Check for git packages with resolved-ref
    resolved_ref = None
    if isinstance(description, dict) and "resolved-ref" in description:
        resolved_ref = description.get("resolved-ref")
    elif "resolved-ref" in package_info:
        resolved_ref = package_info.get("resolved-ref")

    if resolved_ref:
        return f"git:{resolved_ref}"

    return "-"


def generate_unchanged_dependencies_report(
    unchanged_deps: dict[str, tuple[dict[str, Any], dict[str, Any]]], output_file: str
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

                f.write(
                    f"| {package_name} | {version} | {source} | {old_sha_or_ref} | {new_sha_or_ref} |\n"
                )

        logging.info(f"Unchanged dependencies report written to {output_file}")
    except Exception as e:
        logging.error(f"Error generating unchanged dependencies report: {e}")
