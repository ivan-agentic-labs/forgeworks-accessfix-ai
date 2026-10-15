"""Security regression: reject URL userinfo even when its parsed value is empty."""
import pytest

from accessfix_ai.domain.target_policy import (
    validate_origin,
    validate_redirect_chain,
    validate_scan_path,
)


@pytest.mark.parametrize("userinfo", ["@", ":@", "user@", "user:pass@"])
def test_verified_origin_rejects_all_userinfo_spellings(userinfo):
    with pytest.raises(ValueError, match="userinfo"):
        validate_origin("https://" + userinfo + "owned.example.test")


@pytest.mark.parametrize("userinfo", ["@", ":@"])
def test_absolute_scan_path_rejects_empty_userinfo_without_dns(userinfo):
    def no_dns(_):
        raise AssertionError("untrusted URL must be rejected before DNS")
    with pytest.raises(ValueError, match="path leaves verified origin"):
        validate_scan_path(
            "https://" + userinfo + "owned.example.test/admin",
            "https://owned.example.test",
            resolver=no_dns,
        )


@pytest.mark.parametrize("userinfo", ["@", ":@"])
def test_redirect_chain_rejects_empty_userinfo_without_dns(userinfo):
    def no_dns(_):
        raise AssertionError("redirect should not cause DNS activity")
    with pytest.raises(ValueError, match="redirect leaves verified origin"):
        validate_redirect_chain(
            ["https://owned.example.test/", "https://" + userinfo + "owned.example.test/admin"],
            "https://owned.example.test",
            resolver=no_dns,
        )


@pytest.mark.parametrize("unsafe_url", [
    "https://owned.example.test:broken/scan",
    "https://owned.example.test:99999/scan",
])
def test_malformed_absolute_scan_url_is_rejected_without_dns(unsafe_url):
    def no_dns(_host):
        raise AssertionError("invalid URL must be rejected before DNS")

    with pytest.raises(ValueError, match="path leaves verified origin"):
        validate_scan_path(unsafe_url, "https://owned.example.test", resolver=no_dns)


@pytest.mark.parametrize("unsafe_url", [
    "https://owned.example.test:broken/scan",
    "https://owned.example.test:99999/scan",
])
def test_malformed_redirect_url_is_rejected_without_dns(unsafe_url):
    def no_dns(_host):
        raise AssertionError("invalid redirect must be rejected before DNS")

    with pytest.raises(ValueError, match="redirect leaves verified origin"):
        validate_redirect_chain(
            ["https://owned.example.test/", unsafe_url],
            "https://owned.example.test",
            resolver=no_dns,
        )
