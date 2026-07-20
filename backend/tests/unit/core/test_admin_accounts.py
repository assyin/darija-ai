"""Unit tests for multi-admin credential parsing (pure, no I/O)."""

from __future__ import annotations

from app.core.config import parse_admin_accounts


def test_empty_returns_no_accounts() -> None:
    assert parse_admin_accounts("") == []
    assert parse_admin_accounts("   ") == []


def test_single_account() -> None:
    assert parse_admin_accounts("a@x.com:pw1") == [("a@x.com", "pw1")]


def test_multiple_accounts() -> None:
    assert parse_admin_accounts("a@x.com:pw1,b@y.com:pw2") == [
        ("a@x.com", "pw1"),
        ("b@y.com", "pw2"),
    ]


def test_first_colon_splits_email_from_password() -> None:
    # A password may contain characters like '@' and '.', but not ':'.
    assert parse_admin_accounts("Ikram2014.ic@gmail.com:i.c@2026") == [
        ("Ikram2014.ic@gmail.com", "i.c@2026"),
    ]


def test_blank_and_malformed_entries_ignored() -> None:
    # Empty entry, an entry with no colon, and an entry with empty password.
    assert parse_admin_accounts("a@x.com:pw1, ,noSeparator,b@y.com:") == [
        ("a@x.com", "pw1"),
    ]


def test_whitespace_trimmed_around_entries() -> None:
    assert parse_admin_accounts("  a@x.com:pw1 , b@y.com:pw2 ") == [
        ("a@x.com", "pw1"),
        ("b@y.com", "pw2"),
    ]
