import tempfile
from pathlib import Path

import yaml

from diff_tool.summary import _parse_workspace_packages, _get_worktree_commit


class TestWorkspacePackageSupport:
    """Tests for Dart pub workspace package support."""

    def test_parse_workspace_packages_with_valid_workspace(self):
        """Test parsing workspace packages from a valid workspace structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root pubspec.yaml with workspace section
            root_pubspec = {
                "name": "_",
                "publish_to": "none",
                "environment": {"sdk": "^3.6.0"},
                "workspace": ["packages/app_theme", "packages/komodo_ui_kit"],
            }

            root_pubspec_path = Path(tmpdir) / "pubspec.yaml"
            with open(root_pubspec_path, "w") as f:
                yaml.dump(root_pubspec, f)

            # Create workspace packages
            packages_dir = Path(tmpdir) / "packages"
            packages_dir.mkdir()

            # Create app_theme package
            app_theme_dir = packages_dir / "app_theme"
            app_theme_dir.mkdir()
            app_theme_pubspec = {
                "name": "app_theme",
                "version": "0.0.1",
                "resolution": "workspace",
                "environment": {"sdk": "^3.6.0"},
            }
            with open(app_theme_dir / "pubspec.yaml", "w") as f:
                yaml.dump(app_theme_pubspec, f)

            # Create komodo_ui_kit package
            ui_kit_dir = packages_dir / "komodo_ui_kit"
            ui_kit_dir.mkdir()
            ui_kit_pubspec = {
                "name": "komodo_ui_kit",
                "version": "0.0.0",
                "resolution": "workspace",
                "environment": {"sdk": "^3.6.0"},
            }
            with open(ui_kit_dir / "pubspec.yaml", "w") as f:
                yaml.dump(ui_kit_pubspec, f)

            # Parse workspace packages
            workspace_packages = _parse_workspace_packages(tmpdir)

            assert len(workspace_packages) == 2
            assert "app_theme" in workspace_packages
            assert "komodo_ui_kit" in workspace_packages

    def test_parse_workspace_packages_no_workspace_section(self):
        """Test parsing when there's no workspace section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root pubspec.yaml without workspace section
            root_pubspec = {
                "name": "my_app",
                "environment": {"sdk": "^3.6.0"},
                "dependencies": {"flutter": {"sdk": "flutter"}},
            }

            root_pubspec_path = Path(tmpdir) / "pubspec.yaml"
            with open(root_pubspec_path, "w") as f:
                yaml.dump(root_pubspec, f)

            # Parse workspace packages
            workspace_packages = _parse_workspace_packages(tmpdir)

            assert len(workspace_packages) == 0

    def test_parse_workspace_packages_no_pubspec(self):
        """Test parsing when there's no root pubspec.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Don't create any pubspec.yaml
            workspace_packages = _parse_workspace_packages(tmpdir)

            assert len(workspace_packages) == 0

    def test_parse_workspace_packages_missing_workspace_package(self):
        """Test parsing when a workspace package directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root pubspec.yaml with workspace section
            root_pubspec = {
                "name": "_",
                "workspace": ["packages/app_theme", "packages/missing_package"],
            }

            root_pubspec_path = Path(tmpdir) / "pubspec.yaml"
            with open(root_pubspec_path, "w") as f:
                yaml.dump(root_pubspec, f)

            # Create only app_theme package
            packages_dir = Path(tmpdir) / "packages"
            packages_dir.mkdir()

            app_theme_dir = packages_dir / "app_theme"
            app_theme_dir.mkdir()
            app_theme_pubspec = {"name": "app_theme", "version": "0.0.1"}
            with open(app_theme_dir / "pubspec.yaml", "w") as f:
                yaml.dump(app_theme_pubspec, f)

            # Don't create missing_package

            # Parse workspace packages
            workspace_packages = _parse_workspace_packages(tmpdir)

            # Should only find the existing package
            assert len(workspace_packages) == 1
            assert "app_theme" in workspace_packages
            assert "missing_package" not in workspace_packages

    def test_parse_workspace_packages_invalid_worktree_path(self):
        """Test parsing with invalid worktree path."""
        workspace_packages = _parse_workspace_packages("/nonexistent/path")
        assert len(workspace_packages) == 0

    def test_parse_workspace_packages_empty_string_worktree_path(self):
        """Test parsing with empty string worktree path."""
        workspace_packages = _parse_workspace_packages("")
        assert len(workspace_packages) == 0

    def test_get_worktree_commit_invalid_path(self):
        """Test getting commit from invalid worktree path."""
        commit = _get_worktree_commit("/nonexistent/path")
        assert commit is None

    def test_get_worktree_commit_empty_path(self):
        """Test getting commit from empty string worktree path."""
        commit = _get_worktree_commit("")
        assert commit is None

    def test_parse_workspace_packages_with_nested_paths(self):
        """Test parsing workspace packages with nested directory structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root pubspec.yaml with nested workspace paths
            root_pubspec = {
                "name": "_",
                "workspace": [
                    "packages/features/auth",
                    "packages/core/utils",
                ],
            }

            root_pubspec_path = Path(tmpdir) / "pubspec.yaml"
            with open(root_pubspec_path, "w") as f:
                yaml.dump(root_pubspec, f)

            # Create nested workspace packages
            auth_dir = Path(tmpdir) / "packages" / "features" / "auth"
            auth_dir.mkdir(parents=True)
            auth_pubspec = {"name": "auth_feature", "version": "1.0.0"}
            with open(auth_dir / "pubspec.yaml", "w") as f:
                yaml.dump(auth_pubspec, f)

            utils_dir = Path(tmpdir) / "packages" / "core" / "utils"
            utils_dir.mkdir(parents=True)
            utils_pubspec = {"name": "core_utils", "version": "1.0.0"}
            with open(utils_dir / "pubspec.yaml", "w") as f:
                yaml.dump(utils_pubspec, f)

            # Parse workspace packages
            workspace_packages = _parse_workspace_packages(tmpdir)

            assert len(workspace_packages) == 2
            assert "auth_feature" in workspace_packages
            assert "core_utils" in workspace_packages

    def test_parse_workspace_packages_with_malformed_yaml(self):
        """Test parsing when a workspace package has malformed YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root pubspec.yaml
            root_pubspec = {
                "name": "_",
                "workspace": ["packages/good", "packages/bad"],
            }

            root_pubspec_path = Path(tmpdir) / "pubspec.yaml"
            with open(root_pubspec_path, "w") as f:
                yaml.dump(root_pubspec, f)

            # Create packages directory
            packages_dir = Path(tmpdir) / "packages"
            packages_dir.mkdir()

            # Create good package
            good_dir = packages_dir / "good"
            good_dir.mkdir()
            with open(good_dir / "pubspec.yaml", "w") as f:
                yaml.dump({"name": "good_package"}, f)

            # Create bad package with malformed YAML
            bad_dir = packages_dir / "bad"
            bad_dir.mkdir()
            with open(bad_dir / "pubspec.yaml", "w") as f:
                f.write("name: bad_package\n  invalid: yaml: here:")

            # Parse workspace packages - should handle error gracefully
            workspace_packages = _parse_workspace_packages(tmpdir)

            # Should at least get the good package
            assert "good_package" in workspace_packages

    def test_parse_workspace_packages_empty_workspace_list(self):
        """Test parsing when workspace list is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create root pubspec.yaml with empty workspace section
            root_pubspec = {"name": "_", "workspace": []}

            root_pubspec_path = Path(tmpdir) / "pubspec.yaml"
            with open(root_pubspec_path, "w") as f:
                yaml.dump(root_pubspec, f)

            # Parse workspace packages
            workspace_packages = _parse_workspace_packages(tmpdir)

            assert len(workspace_packages) == 0
