import logging
from typing import Dict, List

import pandas as pd


def generate_summary_table(deps1: Dict, deps2: Dict) -> pd.DataFrame:
    package_names = set(deps1.keys()) | set(deps2.keys())
    summary_data: List[Dict] = []

    def get_sha256(package_info) -> str:
        description = package_info.get('description', {})
        if isinstance(description, dict):
            return description.get("sha256", "-")
        elif isinstance(description, str):
            return "-"  # or you could return the string itself if that's more appropriate
        return "-"

    for package_name in package_names:
        status = "Updated"
        old_version = deps1.get(package_name, {}).get("version", "-")
        new_version = deps2.get(package_name, {}).get("version", "-")
        dependency = deps1.get(package_name, deps2.get(package_name, {})).get("dependency", "-")
        old_sha256 = get_sha256(deps1.get(package_name, {}))
        new_sha256 = get_sha256(deps2.get(package_name, {}))

        identicalHashes = old_sha256 != "-" and old_sha256 == new_sha256
        identicalVersions = old_version == new_version and old_sha256 == new_sha256
        if identicalHashes or identicalVersions:
            logging.debug(f'skipping package {package_name}: no change in sha256 hash')
            continue

        if package_name not in deps1:
            status = "Added"
        elif package_name not in deps2:
            status = "Removed"

        summary_data.append({
            "Package": package_name,
            "Status": status,
            "Old version": old_version,
            "New version": new_version,
            "Dependency": dependency,
            "Old sha256": old_sha256,
            "New sha256": new_sha256
        })

    return pd.DataFrame(summary_data).sort_values(['Status', 'Package'], ascending=[True, True])