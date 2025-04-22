import logging
import os
from typing import Dict, List

import pandas as pd


def generate_summary_table(
    deps1: Dict, deps2: Dict, old_dir: str = None, new_dir: str = None
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

    def get_sha256(package_info, package_name=None, package_dir=None) -> str:
        """
        Get the SHA-256 hash from package info or calculate it from package contents.

        Args:
            package_info: The package information from pubspec.lock
            package_name: The name of the package (for logging)
            package_dir: Directory containing the package (to calculate hash if needed)

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

    for package_name in package_names:
        status = "Updated"
        old_version = deps1.get(package_name, {}).get("version", "-")
        new_version = deps2.get(package_name, {}).get("version", "-")
        dependency = deps1.get(package_name, deps2.get(package_name, {})).get(
            "dependency", "-"
        )
        old_package_dir = os.path.join(old_dir, package_name) if old_dir else None
        new_package_dir = os.path.join(new_dir, package_name) if new_dir else None

        old_sha256 = get_sha256(
            deps1.get(package_name, {}), package_name, old_package_dir
        )
        new_sha256 = get_sha256(
            deps2.get(package_name, {}), package_name, new_package_dir
        )

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
