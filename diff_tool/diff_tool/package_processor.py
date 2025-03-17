import concurrent.futures
import logging
import multiprocessing
import os
import re
from functools import partial
from typing import Dict, Tuple, Optional, List

from tqdm import tqdm

from git_diff import generate_diff
from sources import download_dart_package_sources
from summary import generate_summary_table

def _process_single_package(
    package_name: str, 
    deps1: Dict,
    deps2: Dict,
    old_dir: str,
    new_dir: str,
    skip_unchanged: bool,
    skip_sdk_packages: bool
) -> None:
    # Skip SDK packages if requested
    if skip_sdk_packages and ((package_name in deps1 and deps1[package_name].get("source") == "sdk") or 
                              (package_name in deps2 and deps2[package_name].get("source") == "sdk")):
        logging.info(f"Skipping SDK package: {package_name}")
        return

    if skip_unchanged and package_name in deps1 and package_name in deps2:
        if deps1[package_name] == deps2[package_name]:
            logging.info(f"Skipping unchanged package: {package_name}")
            return

    try:
        if package_name in deps1:
            download_dart_package_sources(
                package_name, deps1[package_name], os.path.join(old_dir, package_name)
            )
        if package_name in deps2:
            download_dart_package_sources(
                package_name, deps2[package_name], os.path.join(new_dir, package_name)
            )
    except Exception as e:
        logging.error(f"Failed to download package {package_name}: {str(e)}")
        raise  # Re-raise to be caught by the executor


def process_packages(
    deps1: Dict, deps2: Dict, temp_dir: str, skip_unchanged: bool, 
    skip_sdk_packages: bool, max_workers: Optional[int] = None
) -> Tuple[str, str]:
    if max_workers is None:
        max_workers = max(1, multiprocessing.cpu_count())
    
    old_dir = os.path.join(temp_dir, "old", "packages")
    new_dir = os.path.join(temp_dir, "new", "packages")
    os.makedirs(old_dir, exist_ok=True)
    os.makedirs(new_dir, exist_ok=True)

    package_names = list(set(deps1.keys()) | set(deps2.keys()))
    process_fn = partial(
        _process_single_package,
        deps1=deps1,
        deps2=deps2,
        old_dir=old_dir,
        new_dir=new_dir,
        skip_unchanged=skip_unchanged,
        skip_sdk_packages=skip_sdk_packages
    )

    logging.info(f"Processing packages with {max_workers} worker threads")
    failed_packages = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_fn, pkg): pkg for pkg in package_names}
        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Processing packages"
        ):
            package_name = futures[future]
            try:
                future.result()  # Will raise any exception that occurred
            except Exception as e:
                logging.error(f"Package processing failed for {package_name}: {str(e)}")
                failed_packages.append(package_name)

    if failed_packages:
        failed_list = ", ".join(failed_packages)
        raise RuntimeError(f"Failed to process {len(failed_packages)} packages: {failed_list}")

    return old_dir, new_dir

def generate_output_files(deps1: Dict, deps2: Dict, ref1: str, ref2: str, temp_dir: str,
                          skip_unchanged: bool, skip_sdk_packages: bool, max_workers: Optional[int] = None) -> str:
    """Generate all output files including the diff and summary."""
    old_dir, new_dir = process_packages(deps1, deps2, temp_dir, skip_unchanged, skip_sdk_packages, max_workers)

    # Generate summary files
    summary_df = generate_summary_table(deps1, deps2)
    summary_df.to_csv('package_summary.csv', index=False)

    with open('package_summary.md', 'w') as f:
        f.write("# Package Dependencies Summary\n\n")
        f.write(summary_df.to_markdown(index=False))

    # Generate diff file
    sane_ref1 = re.sub(r'[^\w_. -]', '_', ref1)
    sane_ref2 = re.sub(r'[^\w_. -]', '_', ref2)
    output_diff_file = os.path.abspath(f"{sane_ref1}_{sane_ref2}.patch")
    
    # Generate the diff
    success = generate_diff(old_dir, new_dir, output_diff_file)
    if not success:
        raise RuntimeError("Failed to generate complete diff")
    
    return output_diff_file
