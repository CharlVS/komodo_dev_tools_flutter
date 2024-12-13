import logging
import os
import shutil
from typing import Any

import requests
from git import GitCommandError, Repo


def download_dart_package_sources(package_name: str, package_info: dict[str, Any], temp_dir: str) -> str:
    package_dir = os.path.join(temp_dir, package_name)
    os.makedirs(package_dir, exist_ok=True)

    try:
        if package_info.get("source") == "hosted":
            download_dart_package_sources_from_pub(package_name, package_info, package_dir)
        elif package_info.get("source") == "git":
            clone_dart_package_from_git(package_info, package_dir)
        logging.info(f"Downloaded and processed {package_name}.")
    except (requests.RequestException, GitCommandError, OSError, shutil.ReadError) as e:
        logging.error(f"Error handling package {package_name}: {e}")

    return package_dir


def clone_dart_package_from_git(package_info, package_dir):
    Repo.clone_from(package_info["description"]["url"], package_dir)
    repo = Repo(package_dir)
    repo.git.checkout(package_info["description"]["resolved-ref"])


def download_dart_package_sources_from_pub(package_name: str, package_info: dict[str, Any], package_dir: str):
    url = f"https://pub.dartlang.org/packages/{package_name}/versions/{package_info['version']}.tar.gz"
    response = requests.get(url)
    response.raise_for_status()
    package_path = os.path.join(package_dir, f"{package_name}.tar.gz")
    with open(package_path, "wb") as f:
        f.write(response.content)
    shutil.unpack_archive(package_path, package_dir, "gztar")
    os.remove(package_path)