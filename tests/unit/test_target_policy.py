import pytest

from accessfix_ai.domain.target_policy import (
    MAX_REDIRECTS,
    validate_redirect_chain,
    validate_scan_path,
    validate_scan_request,
)


def test_redirect_chain_rejects_dns_rebinding():
    answers = iter([
        ["8.8.8.8"],
        ["8.8.8.8"],
        ["1.1.1.1"],
        ["1.1.1.1"],
    ])

    def resolver(_host):
        return next(answers)

    with pytest.raises(ValueError, match="DNS answer changed"):
        validate_redirect_chain(
            ["https://example.test/", "https://example.test/next", "https://example.test/final"],
            "https://example.test",
            resolver,
        )


def test_redirect_chain_rejects_external_hop_and_too_many_hops():
    resolver = lambda _host: ["93.184.216.34"]
    with pytest.raises(ValueError, match="leaves verified origin"):
        validate_redirect_chain(["https://example.test/", "https://attacker.test/"], "https://example.test", resolver)
    urls = ["https://example.test/"] + ["https://example.test/p" for _ in range(MAX_REDIRECTS + 1)]
    with pytest.raises(ValueError, match="redirect limit"):
        validate_redirect_chain(urls, "https://example.test", resolver)


def test_path_rejects_private_literal_and_limits_are_bounded():
    with pytest.raises(ValueError, match="blocked"):
        validate_scan_path("https://127.0.0.1/admin", "https://127.0.0.1")
    with pytest.raises(ValueError, match="between 1"):
        validate_scan_request(["/"] * 21)
    with pytest.raises(ValueError, match="maximum length"):
        validate_scan_request(["/" + "a" * 2048])
