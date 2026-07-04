"""Unit tests for orch.mcp.audit.scrub_arguments — secret redaction logic."""

from __future__ import annotations


class TestScrubArguments:
    """Covers secret-key redaction and nested dict recursion."""

    def test_plain_args_are_returned_unchanged(self):
        """Verifies that non-sensitive keys are not modified."""
        from orch.mcp.audit import scrub_arguments

        args = {"project_id": "proj-1", "item_id": "F-00001", "title": "My feature"}
        result = scrub_arguments(args)
        assert result["project_id"] == "proj-1"
        assert result["item_id"] == "F-00001"
        assert result["title"] == "My feature"

    def test_password_key_is_redacted(self):
        """Verifies that a key containing 'password' has its value replaced with ***."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"password": "s3cr3t"})
        assert result["password"] == "***"

    def test_token_key_is_redacted(self):
        """Verifies that a key containing 'token' has its value replaced with ***."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"auth_token": "my-tok"})
        assert result["auth_token"] == "***"

    def test_secret_key_is_redacted(self):
        """Verifies that a key containing 'secret' has its value replaced with ***."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"my_secret_value": "hunter2"})
        assert result["my_secret_value"] == "***"

    def test_api_key_variant_is_redacted(self):
        """Verifies that a key containing 'api_key' has its value replaced with ***."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"api_key": "abc123"})
        assert result["api_key"] == "***"

    def test_apikey_variant_is_redacted(self):
        """Verifies that a key containing 'apikey' (no underscore) has its value replaced."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"apikey": "abc123"})
        assert result["apikey"] == "***"

    def test_credential_key_is_redacted(self):
        """Verifies that a key containing 'credential' has its value replaced with ***."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"db_credential": "pass!"})
        assert result["db_credential"] == "***"

    def test_case_insensitive_matching(self):
        """Verifies that key matching is case-insensitive (e.g. PASSWORD is redacted)."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({"PASSWORD": "upper"})
        assert result["PASSWORD"] == "***"

    def test_nested_dict_is_recursed(self):
        """Verifies that nested dicts have their sensitive keys scrubbed recursively."""
        from orch.mcp.audit import scrub_arguments

        args = {
            "config": {
                "host": "localhost",
                "password": "nested-secret",
                "inner": {"token": "tok-xyz", "name": "alice"},
            }
        }
        result = scrub_arguments(args)
        assert result["config"]["host"] == "localhost"
        assert result["config"]["password"] == "***"
        assert result["config"]["inner"]["token"] == "***"
        assert result["config"]["inner"]["name"] == "alice"

    def test_empty_dict_returns_empty(self):
        """Verifies that scrub_arguments({}) returns {}."""
        from orch.mcp.audit import scrub_arguments

        result = scrub_arguments({})
        assert result == {}

    def test_original_dict_is_not_mutated(self):
        """Verifies that the original args dict is not mutated (a copy is returned)."""
        from orch.mcp.audit import scrub_arguments

        original = {"password": "secret"}
        _ = scrub_arguments(original)
        assert original["password"] == "secret"
