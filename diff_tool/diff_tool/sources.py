import logging
import os
import shutil
import time
import functools
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
        @with_retry(max_retries=max_retries)
        def _download_package() -> None:
            if package_info.get("source") == "hosted":
                download_dart_package_sources_from_pub(package_name, package_info, package_dir)
            elif package_info.get("source") == "git":
                clone_dart_package_from_git(package_info, package_dir)
            else:
                raise ValueError(f"Unsupported package source: {package_info.get('source')}")

        _download_package()
        
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
