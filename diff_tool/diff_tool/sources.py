import logging
import os
import shutil
import time
import functools
import tempfile
from typing import Any, Callable, TypeVar, ParamSpec, cast

import requests
from git import GitCommandError, Repo

P = ParamSpec('P')
R = TypeVar('R')

def with_retry(
    max_retries: int = 3,
    retry_exceptions: tuple = (requests.RequestException, GitCommandError, OSError, shutil.ReadError),
    non_retryable_status_codes: list[int] = [404]
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to retry a function with exponential backoff
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            attempt = 0
            while attempt < max_retries:
                try:
                    return func(*args, **kwargs)
                except requests.HTTPError as e:
                    # Don't retry for certain status codes
                    if e.response.status_code in non_retryable_status_codes:
                        logging.error(f"HTTP Error with status code {e.response.status_code} (non-retryable): {e}")
                        raise
                    attempt += 1
                    if attempt == max_retries:
                        logging.error(f"Final HTTP error after {max_retries} attempts: {e}")
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff
                    logging.warning(f"HTTP error (attempt {attempt}/{max_retries}): {e}")
                    logging.warning(f"Status code: {e.response.status_code}, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                except retry_exceptions as e:
                    attempt += 1
                    if attempt == max_retries:
                        logging.error(f"Final error after {max_retries} attempts: {e}")
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff
                    logging.warning(f"Error (attempt {attempt}/{max_retries}): {e}")
                    logging.warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            return cast(R, None)  # This should never be reached
        return wrapper
    return decorator


def download_dart_package_sources(package_name: str, package_info: dict[str, Any], temp_dir: str, max_retries: int = 3) -> str:
    package_dir = os.path.join(temp_dir, package_name)
    os.makedirs(package_dir, exist_ok=True)

    try:
        # Each function is wrapped with a retry decorator 
        # so don't retry here or wrap this parent function with a retry decorator
        package_source = package_info.get("source")
        if package_source == "hosted":
            download_dart_package_sources_from_pub(package_name, package_info, package_dir)
        elif package_source == "git":
            clone_dart_package_from_git(package_info, package_dir)
        elif package_source == "path":
            copy_dart_package_from_path(package_info, package_dir)
        elif package_source == "sdk":
            download_dart_package_from_sdk(package_name, package_info, package_dir)
        else:
            raise ValueError(f"Unsupported package source: {package_source}")

        # Verify we actually got some content
        if not os.path.exists(package_dir) or not os.listdir(package_dir):
            raise RuntimeError(f"Package directory is empty after download: {package_dir}")
            
        logging.info(f"Downloaded and processed {package_name}.")
        return package_dir
    except Exception as e:
        logging.error(f"Failed to download package {package_name}: {str(e)}")
        raise  # Re-raise to be caught by the caller


@with_retry(max_retries=3)
def clone_dart_package_from_git(package_info, package_dir):
    Repo.clone_from(package_info["description"]["url"], package_dir)
    repo = Repo(package_dir)
    repo.git.checkout(package_info["description"]["resolved-ref"])


@with_retry(max_retries=3)
def download_dart_package_sources_from_pub(package_name: str, package_info: dict[str, Any], package_dir: str):
    url = f"https://pub.dartlang.org/packages/{package_name}/versions/{package_info['version']}.tar.gz"
    response = requests.get(url)
    response.raise_for_status()  # This will raise HTTPError for bad responses (4XX, 5XX)
    package_path = os.path.join(package_dir, f"{package_name}.tar.gz")
    with open(package_path, "wb") as f:
        f.write(response.content)
    shutil.unpack_archive(package_path, package_dir, "gztar")
    os.remove(package_path)


@with_retry(max_retries=3)
def copy_dart_package_from_path(package_info: dict[str, Any], package_dir: str):
    """
    Copy a Dart package from a local path.
    
    Args:
        package_info: Package information from pubspec.lock
        package_dir: Directory to copy the package to
    """
    description = package_info.get("description", {})
    # Handle case where description is a string
    if isinstance(description, str):
        path = description
    else:
        path = description.get("path")
        
    if not path:
        raise ValueError("Path not specified in package_info")
    
    # List of potential base directories to check
    base_directories = []
    
    # First, check if it's already an absolute path
    if os.path.isabs(path):
        base_directories.append("")  # Empty string means use the path as-is
    else:
        # Assume path package might be relative to different locations
        temp_root = os.path.dirname(os.path.dirname(package_dir))  # Up two levels from package_dir
        
        # Check various possible locations
        base_directories = [
            temp_root,                                      # The temp directory itself
            os.path.dirname(temp_root),                     # Parent of temp directory
            os.path.join(temp_root, "packages"),            # packages/ subdirectory
            os.path.join(os.path.dirname(temp_root), "packages")  # Parent's packages/ subdirectory
        ]
    
    # Try each potential base directory
    found = False
    tried_paths = []
    
    for base_dir in base_directories:
        full_path = path if base_dir == "" else os.path.join(base_dir, path)
        tried_paths.append(full_path)
        
        if os.path.exists(full_path):
            # Copy contents excluding hidden files and directories
            for item in os.listdir(full_path):
                if not item.startswith('.'):  # Skip hidden files
                    source = os.path.join(full_path, item)
                    destination = os.path.join(package_dir, item)
                    
                    if os.path.isdir(source):
                        shutil.copytree(source, destination)
                    else:
                        shutil.copy2(source, destination)
            
            logging.info(f"Copied package from path: {full_path}")
            found = True
            break
    
    if not found:
        error_msg = f"Path package not found. Original path: {path}\nTried these locations:\n" + "\n".join(tried_paths)
        logging.error(error_msg)
        raise FileNotFoundError(error_msg)


class SDKPackageDownloader:
    """Helper class to download and extract packages from Flutter SDK."""
    
    FLUTTER_REPO_URL = "https://github.com/flutter/flutter.git"
    
    def __init__(self, package_name: str, package_info: dict[str, Any], package_dir: str):
        """
        Initialize the SDK package downloader.
        
        Args:
            package_name: Name of the package to download
            package_info: Package information from pubspec.lock
            package_dir: Directory where the package should be copied
        """
        self.package_name = package_name
        self.package_info = package_info
        self.package_dir = package_dir
    
    @with_retry(max_retries=3)
    def download(self) -> None:
        """Download the SDK package and copy it to the target directory."""
        logging.info(f"Downloading SDK package '{self.package_name}' from Flutter GitHub repository")
        
        with tempfile.TemporaryDirectory() as temp_flutter_dir:
            try:
                self._clone_flutter_repo(temp_flutter_dir)
                sdk_package_path = self._locate_package(temp_flutter_dir)
                self._copy_package(sdk_package_path)
            except GitCommandError as e:
                error_msg = f"Failed to clone Flutter repository: {e}"
                logging.error(error_msg)
                raise RuntimeError(error_msg) from e
    
    def _clone_flutter_repo(self, temp_dir: str) -> None:
        """Clone the Flutter repository into the temporary directory."""
        logging.info("Cloning Flutter repository (shallow clone)...")
        Repo.clone_from(
            self.FLUTTER_REPO_URL, 
            temp_dir, 
            depth=1,  # Shallow clone
            single_branch=True,
            branch="master"  # Use master branch
        )
    
    def _locate_package(self, flutter_dir: str) -> str:
        """
        Locate the package in the Flutter repository.
        
        Args:
            flutter_dir: Path to the cloned Flutter repository
            
        Returns:
            The path to the located package
            
        Raises:
            FileNotFoundError: If the package cannot be found
        """
        # Check in the packages directory first (most common location)
        packages_dir = os.path.join(flutter_dir, "packages")
        sdk_package_path = os.path.join(packages_dir, self.package_name)
        
        # If not found in packages, check directly in the SDK root
        if not os.path.exists(sdk_package_path):
            sdk_package_path = os.path.join(flutter_dir, self.package_name)
        
        # If still not found, do a recursive search through the repository
        if not os.path.exists(sdk_package_path):
            logging.info(f"Package not found in standard locations, performing recursive search for '{self.package_name}'")
            sdk_package_path = self._find_package_recursively(flutter_dir)
            
        if not sdk_package_path:
            error_msg = f"SDK package '{self.package_name}' not found in the Flutter repository"
            logging.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        logging.info(f"Found SDK package at: {sdk_package_path}")
        return sdk_package_path
        
    def _find_package_recursively(self, root_dir: str) -> str:
        """
        Search recursively for a directory matching the package name.
        
        Args:
            root_dir: Directory to start the search from
            
        Returns:
            Path to the found directory, or None if not found
        """
        for root, dirs, _ in os.walk(root_dir):
            # Skip hidden directories (starting with .)
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            # Check if current directory contains the package name
            if self.package_name in dirs:
                return os.path.join(root, self.package_name)
        
        return None


    def _copy_package(self, source_path: str) -> None:
        """
        Copy package contents to the destination directory.
        
        Args:
            source_path: Path to the source package in the Flutter repository
        """
        # Copy contents excluding hidden files and directories
        for item in os.listdir(source_path):
            if not item.startswith('.'):  # Skip hidden files
                source = os.path.join(source_path, item)
                destination = os.path.join(self.package_dir, item)
                
                if os.path.isdir(source):
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)


@with_retry(max_retries=3)
def download_dart_package_from_sdk(package_name: str, package_info: dict[str, Any], package_dir: str):
    """
    Download a package from Flutter SDK by cloning the Flutter GitHub repository.
    
    Args:
        package_name: Name of the package
        package_info: Package information from pubspec.lock
        package_dir: Directory to copy the package to
    """
    downloader = SDKPackageDownloader(package_name, package_info, package_dir)
    downloader.download()
