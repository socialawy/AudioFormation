"""Tests for input sanitization and path safety."""

import pytest
from pathlib import Path

from audioformation.utils.security import (
    sanitize_project_id,
    sanitize_filename,
    validate_path_within,
    redact_api_keys,
)


class TestSanitizeProjectId:
    """Tests for project ID sanitization."""

    def test_simple_name(self) -> None:
        assert sanitize_project_id("MY_NOVEL") == "MY_NOVEL"

    def test_spaces_to_underscores(self) -> None:
        assert sanitize_project_id("My Novel") == "MY_NOVEL"

    def test_strips_special_characters(self) -> None:
        assert sanitize_project_id("My Novel 2026!@#") == "MY_NOVEL_2026"

    def test_uppercase_conversion(self) -> None:
        assert sanitize_project_id("my_novel") == "MY_NOVEL"

    def test_hyphens_preserved(self) -> None:
        assert sanitize_project_id("my-novel") == "MY-NOVEL"

    def test_empty_after_sanitization_raises(self) -> None:
        with pytest.raises(ValueError, match="no valid characters"):
            sanitize_project_id("!!!")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="no valid characters"):
            sanitize_project_id("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="no valid characters"):
            sanitize_project_id("   ")

    def test_arabic_stripped(self) -> None:
        # Arabic characters are not valid in project IDs (filesystem safety)
        with pytest.raises(ValueError, match="no valid characters"):
            sanitize_project_id("رواية")

    def test_mixed_arabic_latin(self) -> None:
        assert sanitize_project_id("Novel_رواية_2026") == "NOVEL__2026"


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_simple_filename(self) -> None:
        assert sanitize_filename("chapter01.txt") == "chapter01.txt"

    def test_strips_path_components(self) -> None:
        assert sanitize_filename("/etc/passwd") == "passwd"
        assert sanitize_filename("../../secret.txt") == "secret.txt"

    def test_strips_windows_paths(self) -> None:
        assert sanitize_filename("C:\\Windows\\system32") == "system32"

    def test_strips_null_bytes(self) -> None:
        assert sanitize_filename("file\x00name.txt") == "filename.txt"

    def test_strips_dangerous_characters(self) -> None:
        assert sanitize_filename('file<>:"|?*.txt') == "file.txt"

    def test_strips_leading_dots(self) -> None:
        assert sanitize_filename(".hidden") == "hidden"
        assert sanitize_filename("..double") == "double"

    def test_empty_after_sanitization_raises(self) -> None:
        with pytest.raises(ValueError, match="empty after sanitization"):
            sanitize_filename("...")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="empty after sanitization"):
            sanitize_filename("")


class TestValidatePathWithin:
    """Tests for directory traversal prevention."""

    def test_valid_child_path(self, tmp_path: Path) -> None:
        child = tmp_path / "subdir" / "file.txt"
        assert validate_path_within(child, tmp_path) is True

    def test_exact_root_is_valid(self, tmp_path: Path) -> None:
        assert validate_path_within(tmp_path, tmp_path) is True

    def test_traversal_rejected(self, tmp_path: Path) -> None:
        escape = tmp_path / ".." / ".." / "etc" / "passwd"
        assert validate_path_within(escape, tmp_path) is False

    def test_sibling_rejected(self, tmp_path: Path) -> None:
        root = tmp_path / "my_root_dir"
        root.mkdir(exist_ok=True)
        sibling = tmp_path / "other_dir" / "file.txt"
        assert validate_path_within(sibling, root) is False


class TestRedactApiKeys:
    """Tests for API key redaction in logging."""

    def test_redacts_key_fields(self) -> None:
        config = {"api_key": "sk-12345", "name": "test"}
        redacted = redact_api_keys(config)
        assert redacted["api_key"] == "***REDACTED***"
        assert redacted["name"] == "test"

    def test_redacts_nested_keys(self) -> None:
        config = {
            "engines": {
                "elevenlabs": {"api_key": "secret123"},
                "name": "el",
            }
        }
        redacted = redact_api_keys(config)
        assert redacted["engines"]["elevenlabs"]["api_key"] == "***REDACTED***"
        assert redacted["engines"]["name"] == "el"

    def test_redacts_various_patterns(self) -> None:
        config = {
            "secret": "hidden",
            "token": "abc",
            "password": "pass",
            "normal": "visible",
        }
        redacted = redact_api_keys(config)
        assert redacted["secret"] == "***REDACTED***"
        assert redacted["token"] == "***REDACTED***"
        assert redacted["password"] == "***REDACTED***"
        assert redacted["normal"] == "visible"

    def test_preserves_non_string_values(self) -> None:
        config = {"api_key": 12345, "name": "test"}
        redacted = redact_api_keys(config)
        # Non-string values for key fields are left as-is
        assert redacted["api_key"] == 12345

    def test_handles_lists(self) -> None:
        config = {
            "providers": [
                {"api_key": "key1", "name": "a"},
                {"api_key": "key2", "name": "b"},
            ]
        }
        redacted = redact_api_keys(config)
        assert redacted["providers"][0]["api_key"] == "***REDACTED***"
        assert redacted["providers"][1]["api_key"] == "***REDACTED***"
        assert redacted["providers"][0]["name"] == "a"

    def test_empty_dict(self) -> None:
        assert redact_api_keys({}) == {}