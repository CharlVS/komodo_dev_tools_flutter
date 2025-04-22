import logging
import os
from typing import Dict, List, Optional, Any

import pandas as pd


def generate_summary_table(
    deps1: Dict, deps2: Dict, old_dir: Optional[str] = None, new_dir: Optional[str] = None
) -> pd.DataFrame:
    """
    Generate a summary table of package dependencies.

    Args:
        deps1: Old dependencies from pubspec.lock
        deps2: New dependencies from pubspec.lock
        old_dir: Base directory for old package contents (for hash calculation)
        new_dir: Base directory for new package contents (for hash calculation)

    Returns:
        DataFrame with package dependency summary
    """
    package_names = set(deps1.keys()) | set(deps2.keys())
    summary_data: List[Dict] = []

    

    for package_name in package_names:
        status = "Updated"
        old_version = deps1.get(package_name, {}).get("version", "-")
        new_version = deps2.get(package_name, {}).get("version", "-")
        dependency = deps1.get(package_name, deps2.get(package_name, {})).get(
            "dependency", "-"
        )

        old_sha256 = get_sha256_from_package_info( deps1.get(package_name, {}))
        new_sha256 = get_sha256_from_package_info( deps2.get(package_name, {}))

        identicalHashes = old_sha256 != "-" and old_sha256 == new_sha256
        identicalVersions = old_version == new_version and old_sha256 == new_sha256
        if identicalHashes or identicalVersions:
            logging.debug(f"skipping package {package_name}: no change in sha256 hash")
            continue

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


def get_sha256_from_package_info(package_info: Dict[str, Any]) -> str:
    """
    Get the SHA-256 hash from package info or calculate it from package contents.

    Args:
        package_info: The package information from pubspec.lock

    Returns:
        SHA-256 hash string, or "-" if unavailable.
        Hash will be prefixed with 'pub:' if from pubspec.lock
    """
    description = package_info.get("description", {})
    if isinstance(description, dict) and "sha256" in description:
        return f"pub:{description.get('sha256')}"

    resolved_ref = None
    if isinstance(description, dict) and "resolved-ref" in description:
        resolved_ref = description.get("resolved-ref")
    elif "resolved-ref" in package_info:
        resolved_ref = package_info.get("resolved-ref")

    if resolved_ref:
        return f"git:{resolved_ref}"

    return "-"

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

                f.write(
                    f"| {package_name} | {version} | {source} | {old_sha_or_ref} | {new_sha_or_ref} |\n"
                )

        logging.info(f"Unchanged dependencies report written to {output_file}")
    except Exception as e:
        logging.error(f"Error generating unchanged dependencies report: {e}")
