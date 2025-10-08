# Diff Tool

A Python tool for analyzing and processing diff files and package changes.

## Features

- Compares Flutter/Dart dependencies between two git references
- Generates detailed diffs for each changed package
- **Supports path dependencies with git submodules**
- **Tracks git commit SHAs for submodule packages**
- **Supports Dart pub workspaces (monorepo)** - automatically detects and tracks workspace packages
- Handles packages from multiple sources: pub.dev, git, local paths, Flutter SDK, and workspace packages
- Parallel processing for faster analysis
- Comprehensive summary reports

## Prerequisites

This project uses [Rye](https://rye.astral.sh/) for dependency management. Install Rye first:

```bash
curl -sSf https://rye.astral.sh/get | bash
```

## Installation

```bash
# Clone and navigate to the project
cd diff_tool

# Sync dependencies (creates virtual environment and installs dependencies)
rye sync
```

## Usage

```bash
# Run the diff tool
rye run diff --help

# Example usage
rye run diff /path/to/repo commit1 commit2

# With options
rye run diff /path/to/repo commit1 commit2 --skip-unchanged --verbose
```

## Git Submodule Support

The tool automatically handles repositories with git submodules. When path dependencies reference submodule directories (e.g., `sdk/packages/my_package`), the tool:

1. Creates git worktrees for each ref being compared
2. Initializes all submodules recursively
3. Resolves path dependencies correctly
4. **Tracks submodule commit SHAs** for accurate version tracking
5. Reports submodule packages as `git:{commit_sha}` in summaries
6. Cleans up worktrees after processing

### Submodule Commit Tracking

Path dependencies pointing to git submodules are now tracked by their git commit SHA, not just as generic paths. This enables:

- Accurate version comparison between refs
- Proper change detection for submodule packages
- Consistent reporting with other git dependencies

The tool automatically:
- Parses `.gitmodules` to identify submodules
- Extracts commit SHAs from the parent repository
- Reports them in package summaries as `git:{commit_sha}`

**Example:** A package like `komodo_cex_market_data` in `sdk/packages/` will show:
- **Old sha256**: `git:abc123def456...`
- **New sha256**: `git:789xyz012abc...`

For more details, see [SUBMODULE_COMMIT_TRACKING.md](SUBMODULE_COMMIT_TRACKING.md).

## Dart Workspace Support

The tool fully supports [Dart pub workspaces](https://dart.dev/tools/pub/workspaces) for monorepo projects. Workspace packages are local packages defined in the root `pubspec.yaml` under the `workspace:` section.

### How It Works

1. **Automatic Detection**: The tool parses the root `pubspec.yaml` to identify workspace packages
2. **Commit Tracking**: Workspace packages are tracked by the worktree's git commit SHA
3. **Summary Reporting**: Workspace packages appear in summaries with:
   - **Dependency**: `workspace`
   - **Version**: First 8 characters of the git commit SHA
   - **Old/New sha256**: Full commit SHA as `git:{commit_sha}`

### Why Workspace Packages Don't Appear in pubspec.lock

In Dart workspaces, local workspace packages are resolved at the workspace root and **do not appear as entries in `pubspec.lock`**. They are listed only in the `workspace:` section of the root `pubspec.yaml`. The tool accounts for this by:

- Reading the workspace configuration from root `pubspec.yaml`
- Extracting package names from each workspace package's `pubspec.yaml`
- Using the repository's git commit as their version identifier

### Example

For a workspace package like `app_theme`:

```
Root pubspec.yaml:
  workspace:
    - packages/app_theme
    - packages/komodo_ui_kit
```

In the summary, these packages will show:

| Package | Status | Old version | New version | Dependency | Old sha256 | New sha256 |
|---------|--------|-------------|-------------|------------|------------|------------|
| app_theme | Updated | abc12345 | def67890 | workspace | git:abc12345... | git:def67890... |
| komodo_ui_kit | Updated | abc12345 | def67890 | workspace | git:abc12345... | git:def67890... |

This ensures workspace packages are properly tracked even though they don't appear in `pubspec.lock`.

## Development

```bash
# Install development dependencies (already included with rye sync)
rye sync

# Run tests
rye run test

# Lint code
rye run lint

# Format code
rye run format

# Fix linting issues automatically
rye run lint --fix
```

## Migration from Poetry

This project was migrated from Poetry to Rye. The key changes:
- `pyproject.toml` updated to use standard Python project format
- Poetry lock file removed, replaced with `requirements.lock` and `requirements-dev.lock`
- `.python-version` file added to specify Python version
- Development dependencies moved to `[project.optional-dependencies]`
- Build system changed from Poetry to Hatchling

## Available Scripts

- `rye run diff` - Main diff tool command
- `rye run test` - Run tests with pytest
- `rye run lint` - Lint code with ruff
- `rye run format` - Format code with ruff
