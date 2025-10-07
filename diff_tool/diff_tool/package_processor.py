import concurrent.futures
import logging
import multiprocessing
import os
import re
import shutil
from functools import partial
from typing import Dict, Tuple, Optional, Any

from git import Repo, GitCommandError
from tqdm import tqdm

from diff_tool.git_diff import generate_diff
from diff_tool.sources import download_dart_package_sources, FlutterSDKCache
from diff_tool.summary import (
    generate_summary_table,
    # generate_summary_table_with_calculated_hashes,
)
from diff_tool.sources import FlutterSDKCache


def _create_worktree_with_submodules(repo: Repo, ref: str, worktree_path: str) -> None:
    """
    Create a git worktree at the specified ref and initialize submodules.

    Args:
        repo: Git repository object
        ref: Git reference to checkout
        worktree_path: Path where the worktree should be created
    """
    try:
        logging.info(f"Creating worktree for {ref} at {worktree_path}")
        repo.git.worktree("add", worktree_path, ref)

        # Initialize submodules in the worktree
        worktree_repo = Repo(worktree_path)
        try:
            logging.debug(f"Initializing submodules in worktree for {ref}")
            worktree_repo.git.submodule("update", "--init", "--recursive")
            logging.info(f"Submodules initialized successfully in worktree for {ref}")
        except GitCommandError as e:
            logging.debug(
                f"No submodules to initialize in worktree or error occurred: {e}"
            )
    except GitCommandError as e:
        logging.error(f"Failed to create worktree for {ref}: {e}")
        raise


def _cleanup_worktree(repo: Repo, worktree_path: str) -> None:
    """
    Clean up a git worktree.

    Args:
        repo: Git repository object
        worktree_path: Path to the worktree to remove
    """
    try:
        if os.path.exists(worktree_path):
            logging.info(f"Cleaning up worktree at {worktree_path}")
            # Remove the worktree directory first
            shutil.rmtree(worktree_path)
            # Then prune the worktree reference
            repo.git.worktree("prune")
    except (GitCommandError, OSError) as e:
        logging.warning(f"Failed to clean up worktree at {worktree_path}: {e}")


def _process_single_package(
    package_name: str,
    deps1: Dict,
    deps2: Dict,
    old_dir: str,
    new_dir: str,
    old_worktree: Optional[str],
    new_worktree: Optional[str],
    skip_unchanged: bool,
    skip_sdk_packages: bool,
) -> None:
    if skip_sdk_packages and (
        (package_name in deps1 and deps1[package_name].get("source") == "sdk")
        or (package_name in deps2 and deps2[package_name].get("source") == "sdk")
    ):
        logging.info(f"Skipping SDK package: {package_name}")
        return

    if skip_unchanged and package_name in deps1 and package_name in deps2:
        if deps1[package_name] == deps2[package_name]:
            logging.info(f"Skipping unchanged package: {package_name}")
            return

    try:
        if package_name in deps1:
            download_dart_package_sources(
                package_name,
                deps1[package_name],
                os.path.join(old_dir, package_name),
                worktree_path=old_worktree,
            )
        if package_name in deps2:
            download_dart_package_sources(
                package_name,
                deps2[package_name],
                os.path.join(new_dir, package_name),
                worktree_path=new_worktree,
            )
    except Exception as e:
        logging.error(f"Failed to download package {package_name}: {str(e)}")
        raise  # Re-raise to be caught by the executor


def process_packages(
    repo: Repo,
    ref1: str,
    ref2: str,
    deps1: Dict[str, Any],
    deps2: Dict,
    temp_dir: str,
    skip_unchanged: bool,
    skip_sdk_packages: bool,
    max_workers: Optional[int] = None,
) -> Tuple[str, str, str, str, Repo, bool, bool]:
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count())

    old_dir = os.path.join(temp_dir, "old", "packages")
    new_dir = os.path.join(temp_dir, "new", "packages")
    os.makedirs(old_dir, exist_ok=True)
    os.makedirs(new_dir, exist_ok=True)

    # Create worktrees for each ref to support path dependencies with submodules
    old_worktree = os.path.join(temp_dir, "old", "worktree")
    new_worktree = os.path.join(temp_dir, "new", "worktree")

    old_worktree_created = False
    new_worktree_created = False

    try:
        _create_worktree_with_submodules(repo, ref1, old_worktree)
        old_worktree_created = True
        _create_worktree_with_submodules(repo, ref2, new_worktree)
        new_worktree_created = True
    except GitCommandError as e:
        logging.error(f"Failed to create worktrees: {e}")
        # Clean up any created worktrees
        if old_worktree_created:
            _cleanup_worktree(repo, old_worktree)
        if new_worktree_created:
            _cleanup_worktree(repo, new_worktree)
        raise

    sdk_cache = FlutterSDKCache()
    sdk_cache.initialize_if_needed(deps1, deps2)

    package_names = set(set(deps1.keys()) | set(deps2.keys()))
    process_fn = partial(
        _process_single_package,
        deps1=deps1,
        deps2=deps2,
        old_dir=old_dir,
        new_dir=new_dir,
        old_worktree=old_worktree,
        new_worktree=new_worktree,
        skip_unchanged=skip_unchanged,
        skip_sdk_packages=skip_sdk_packages,
    )

    logging.info(
        f"Processing {len(package_names)} packages with {max_workers} worker threads"
    )
    failed_packages = []
    processed_packages = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_fn, pkg): pkg for pkg in package_names}
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Processing packages",
        ):
            package_name = futures[future]
            try:
                future.result()  # Will raise any exception that occurred
                processed_packages.add(package_name)
            except Exception as e:
                logging.error(f"Package processing failed for {package_name}: {str(e)}")
                failed_packages.append(package_name)

    logging.info(f"Processed {len(processed_packages)} packages successfully.")

    if failed_packages:
        failed_list = ", ".join(failed_packages)
        raise RuntimeError(
            f"Failed to process {len(failed_packages)} packages: {failed_list}"
        )

    missed_packages = package_names - processed_packages
    if missed_packages:
        missed_list = ", ".join(missed_packages)
        logging.warning(f"Missed {len(missed_packages)} packages: {missed_list}. ")

    # Return worktree info so cleanup can happen after summary generation
    return (
        old_dir,
        new_dir,
        old_worktree,
        new_worktree,
        repo,
        old_worktree_created,
        new_worktree_created,
    )


def generate_output_files(
    repo: Repo,
    deps1: Dict[str, Any],
    deps2: Dict[str, Any],
    ref1: str,
    ref2: str,
    temp_dir: str,
    skip_unchanged: bool,
    skip_sdk_packages: bool,
    max_workers: Optional[int] = None,
) -> str:
    """Generate all output files including the diff and summary."""
    (
        old_dir,
        new_dir,
        old_worktree,
        new_worktree,
        worktree_repo,
        old_worktree_created,
        new_worktree_created,
    ) = process_packages(
        repo,
        ref1,
        ref2,
        deps1,
        deps2,
        temp_dir,
        skip_unchanged,
        skip_sdk_packages,
        max_workers,
    )

    try:
        # Pass old_dir and new_dir to generate_summary_table so it can calculate sha256 hashes when needed
        # Also pass worktree paths for submodule resolution
        summary_df = generate_summary_table(
            deps1, deps2, old_dir, new_dir, old_worktree, new_worktree
        )
        summary_df.to_csv("package_summary.csv", index=False)

        with open("package_summary.md", "w") as f:
            f.write("# Package Dependencies Summary\n\n")
            f.write(summary_df.to_markdown(index=False))
    finally:
        # Clean up worktrees after summary is generated
        if old_worktree_created:
            _cleanup_worktree(worktree_repo, old_worktree)
        if new_worktree_created:
            _cleanup_worktree(worktree_repo, new_worktree)

    # summary_calculated_df = generate_summary_table_with_calculated_hashes(
    #     deps1, deps2, old_dir, new_dir
    # )
    # summary_calculated_df.to_csv("package_summary_generated_sha256.csv", index=False)

    # with open("package_summary_generated_sha256.md", "w") as f:
    #     f.write(
    #         "# Package Dependencies Summary (Using Generated SHA256 Hashes Only)\n\n"
    #     )
    #     f.write(
    #         "This summary uses only SHA256 hashes calculated from package contents, ignoring any hashes in pubspec.lock\n\n"
    #     )
    #     f.write(summary_calculated_df.to_markdown(index=False))

    sane_ref1 = re.sub(r"[^\w_. -]", "_", ref1)
    sane_ref2 = re.sub(r"[^\w_. -]", "_", ref2)
    output_diff_file = os.path.abspath(f"{sane_ref1}_{sane_ref2}.patch")

    success, unchanged_deps = generate_diff(
        old_dir, new_dir, output_diff_file, deps1, deps2
    )
    if not success:
        raise RuntimeError("Failed to generate complete diff")

    if unchanged_deps:
        logging.info(
            f"Found {len(unchanged_deps)} unchanged dependencies - see {output_diff_file.replace('.patch', '_unchanged.md')}"
        )

    return output_diff_file
