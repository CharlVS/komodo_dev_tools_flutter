import os
import sys
import git
import yaml
import tempfile
import shutil
import requests
import subprocess
import logging
import argparse
from git import Repo, GitCommandError
from typing import Dict, List, Tuple
from tqdm import tqdm


def configure_logging(verbose: bool):
    level = logging.INFO if verbose else logging.ERROR
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")


def get_dependencies(repo: Repo, ref: str) -> Dict[str, Dict]:
    try:
        logging.info(f"Extracting dependencies from pubspec.lock for ref {ref}.")
        pubspec_lock_content = repo.git.show(f"{ref}:pubspec.lock")
        pubspec_lock_data = yaml.safe_load(pubspec_lock_content)
        packages = pubspec_lock_data.get("packages", {})
        logging.info(f"Found {len(packages)} packages in {ref}.")
        return packages
    except (GitCommandError, yaml.YAMLError) as e:
        logging.error(f"Error processing pubspec.lock in ref {ref}: {e}")
        return {}


def download_package(package_name: str, package_info: Dict, temp_dir: str) -> str:
    package_dir = os.path.join(temp_dir, package_name)
    os.makedirs(package_dir, exist_ok=True)

    try:
        if package_info.get("source") == "hosted":
            url = f"https://pub.dartlang.org/packages/{package_name}/versions/{package_info['version']}.tar.gz"
            response = requests.get(url)
            response.raise_for_status()
            package_path = os.path.join(package_dir, f"{package_name}.tar.gz")
            with open(package_path, "wb") as f:
                f.write(response.content)
            shutil.unpack_archive(package_path, package_dir, "gztar")
            os.remove(package_path)
        elif package_info.get("source") == "git":
            Repo.clone_from(package_info["description"]["url"], package_dir)
            repo = Repo(package_dir)
            repo.git.checkout(package_info["description"]["resolved-ref"])
        logging.info(f"Downloaded and processed {package_name}.")
    except (requests.RequestException, GitCommandError, OSError, shutil.ReadError) as e:
        logging.error(f"Error handling package {package_name}: {e}")

    return package_dir


def generate_diff(old_dir: str, new_dir: str, output_file: str) -> None:
    try:
        logging.info(f"Generating diff between {old_dir} and {new_dir}.")
        with open(output_file, "w") as diff_file:
            subprocess.run(
                ["git", "diff", "--no-index", old_dir, new_dir],
                stdout=diff_file,
                text=True,
                check=True,
            )
        logging.info(f"Diff file written to {output_file}")
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:  # Git diff returns 1 if there are differences
            logging.info(
                "Diff generated successfully (non-zero exit code is expected for differences)."
            )
        else:
            logging.error(f"Error generating diff between directories: {e}")


def process_packages(
    deps1: Dict, deps2: Dict, temp_dir: str, skip_unchanged: bool
) -> Tuple[str, str]:
    old_dir = os.path.join(temp_dir, "old")
    new_dir = os.path.join(temp_dir, "new")
    os.makedirs(old_dir, exist_ok=True)
    os.makedirs(new_dir, exist_ok=True)

    package_names = set(deps1.keys()) | set(deps2.keys())
    for package_name in tqdm(package_names, desc="Processing packages"):
        if skip_unchanged and package_name in deps1 and package_name in deps2:
            if deps1[package_name] == deps2[package_name]:
                logging.info(f"Skipping unchanged package: {package_name}")
                continue

        if package_name in deps1:
            download_package(
                package_name, deps1[package_name], os.path.join(old_dir, package_name)
            )
        if package_name in deps2:
            download_package(
                package_name, deps2[package_name], os.path.join(new_dir, package_name)
            )

    return old_dir, new_dir


def main(repo_path: str, ref1: str, ref2: str, verbose: bool, skip_unchanged: bool):
    configure_logging(verbose)

    try:
        repo = Repo(repo_path)
        logging.info(f"Opened repository at {repo_path}.")
    except GitCommandError as e:
        logging.error(f"Error opening repository: {e}")
        sys.exit(1)

    deps1 = get_dependencies(repo, ref1)
    deps2 = get_dependencies(repo, ref2)

    with tempfile.TemporaryDirectory() as temp_dir:
        old_dir, new_dir = process_packages(deps1, deps2, temp_dir, skip_unchanged)
        output_diff_file = os.path.abspath("dependency_code_diff.diff")
        generate_diff(old_dir, new_dir, output_diff_file)

    logging.info(
        f"Dependency code diff process completed. Diff file saved to {output_diff_file}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate dependency code diffs between two Git refs."
    )
    parser.add_argument("repo_path", help="Path to the Git repository")
    parser.add_argument("ref1", help="Old Git reference (e.g., commit hash)")
    parser.add_argument("ref2", help="New Git reference (e.g., commit hash)")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable detailed logging output"
    )
    parser.add_argument(
        "--skip-unchanged",
        action="store_true",
        default=True,
        help="Skip unchanged dependencies based on pubspec.lock comparison",
    )

    args = parser.parse_args()
    main(args.repo_path, args.ref1, args.ref2, args.verbose, args.skip_unchanged)
