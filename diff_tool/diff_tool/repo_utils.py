import logging
import os
from typing import Dict, List, Tuple

from git import GitCommandError, Repo

from git_diff import get_dependencies

def validate_repository(repo_path: str) -> Repo:
    """Validate that the provided path is a valid git repository."""
    if not os.path.exists(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")
    
    if not os.path.isdir(repo_path):
        raise ValueError(f"Repository path is not a directory: {repo_path}")
    
    try:
        repo = Repo(repo_path)
        if not repo.git_dir:
            raise ValueError(f"Not a valid git repository: {repo_path}")
        return repo
    except GitCommandError as e:
        raise ValueError(f"Error opening git repository: {str(e)}")

def validate_git_ref(repo: Repo, ref: str) -> bool:
    """Validate that a git reference exists in the repository."""
    try:
        repo.git.rev_parse("--verify", ref)
        return True
    except GitCommandError:
        return False

def fetch_dependencies(repo: Repo, ref1: str, ref2: str, packages_filter: List[str] = None) -> Tuple[Dict, Dict]:
    """Fetch dependencies for both git references."""
    if packages_filter is None:
        packages_filter = []
    
    logging.info(f"Fetching dependencies for {ref1} and {ref2}")
    deps1 = get_dependencies(repo, ref1, packages_filter)
    deps2 = get_dependencies(repo, ref2, packages_filter)
    
    return deps1, deps2

def validate_inputs(repo_path: str, ref1: str, ref2: str) -> Repo:
    """Validate repository and git references."""
    # Validate repository path
    repo = validate_repository(repo_path)
    logging.info(f"Opened repository at {repo_path}.")
    
    # Validate git references
    if not validate_git_ref(repo, ref1):
        logging.error(f"Invalid git reference: {ref1}")
        raise ValueError(f"Invalid git reference: {ref1}")
        
    if not validate_git_ref(repo, ref2):
        logging.error(f"Invalid git reference: {ref2}")
        raise ValueError(f"Invalid git reference: {ref2}")
        
    logging.info(f"Validated git references: {ref1} and {ref2}")
    return repo
