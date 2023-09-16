# Komodo Dev Tools for Flutter

`komodo_dev_tools_flutter` is a development toolkit designed to streamline the Flutter development process at Komodo Platform. Initially, it focuses on providing custom linter rules tailored for our team. However, we have an ambitious roadmap to include other profiling, debugging tools, and possibly set Flutter code standards for our organization.

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

## Contribution

We welcome contributions from all team members. If you have suggestions, improvements, or encounter any issues, please raise them in our GitHub repository.