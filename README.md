# Komodo Dev Tools for Flutter

`komodo_dev_tools_flutter` is a development toolkit designed to streamline the Flutter development process at Komodo Platform. Initially, it focuses on providing custom linter rules tailored for our team. However, we have an ambitious roadmap to include other profiling, debugging tools, and possibly set Flutter code standards for our organization.

## Project Components

This repository contains the following major components:

1. **Flutter Linter Rules** - Custom lint rules tailored for Komodo Platform's Flutter development standards.

2. **Diff Tool** - A Python-based utility for analyzing and comparing Flutter package dependencies, generating detailed diffs between versions.

3. **Apps** - Sample Flutter applications that demonstrate the usage of our tooling.

## Installation

### 1. Using the Package Locally:

If you want to use or test the package from your local machine, follow these steps:

1. Clone the repository:
    ```bash
    git clone https://github.com/com.komodoplatform/komodo_dev_tools_flutter.git
    ```

2. Add a local path `dev_dependency` in your `pubspec.yaml`:
    ```yaml
    dev_dependencies:
      komodo_dev_tools_flutter:
        path: /path/to/your/local/directory/komodo_dev_tools_flutter
    ```

Replace `/path/to/your/local/directory` with the actual path where you've cloned the package.

### 2. Using the Package from GitHub:

If you prefer to use the package directly from our GitHub repository:

Add a Git `dev_dependency` in your `pubspec.yaml`:

```yaml
dev_dependencies:
  komodo_dev_tools_flutter:
    git:
      url: https://github.com/KomodoPlatform/komodo_dev_tools_flutter.git
      ref: main # Or a specific branch, tag, or commit hash
```

Remember to run:
```bash
dart pub get
```
to fetch the package after updating your `pubspec.yaml`.

## Roadmap

- **Phase 1**: Focus on custom linter rules.
- **Phase 2**: Integrate profiling and debugging tools.
- **Phase 3**: Establish and enforce Flutter code standards for our organization.

## Python Setup with Poetry

The Python tools in this repository use Poetry for dependency management. To set up the Python environment:

```bash
# Navigate to the diff_tool directory
cd diff_tool

# Install dependencies with Poetry
poetry install

# Run a command with Poetry
poetry run python -m diff_tool --help
```

For more information about Poetry, visit [the Poetry documentation](https://python-poetry.org/docs/).

## Diff Tool

The `diff_tool` is a Python-based utility for analyzing Flutter package dependencies. It helps in:

- Comparing dependencies between different versions
- Generating detailed diffs between package versions
- Identifying unchanged dependencies
- Working with monorepo structures

### Using the Diff Tool

The diff tool is built with Poetry for dependency management. Navigate to the diff_tool directory and use the following:

```bash
cd diff_tool

# Install dependencies
poetry install

# Method 1: Run using the Python module (recommended)
poetry run python -m diff-tool <repo_path> <ref1> <ref2> [options]

# Method 2: Run using the script entry point
poetry run diff-tool <repo_path> <ref1> <ref2> [options]

# Example with options
poetry run python -m diff_tool /path/to/repo main dev --skip-unchanged --skip-sdk-packages
```

#### Command Line Arguments

- `repo_path`: Path to the Git repository
- `ref1`: Old Git reference (e.g., commit hash, branch name)
- `ref2`: New Git reference (e.g., commit hash, branch name)
- `--skip-unchanged`: Skip unchanged dependencies (optional)
- `--skip-sdk-packages`: Skip Flutter SDK packages from the diff (optional)
- `--verbose`: Enable detailed logging output (optional)
- `--max-workers`: Maximum number of worker threads (optional)
```

## Contribution

We welcome contributions from all team members. If you have suggestions, improvements, or encounter any issues, please raise them in our GitHub repository.