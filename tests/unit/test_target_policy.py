import pytest

from accessfix_ai.domain.target_policy import (
    MAX_REDIRECTS,
    validate_origin,
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


@pytest.mark.parametrize("origin", [
    " https://example.test",
    "https://example.test\r\n",
    "https://example.test\\\\@attacker.test",
    "https://example.test\t",
])
def test_origin_rejects_parser_normalized_or_ambiguous_characters(origin):
    with pytest.raises(ValueError, match="unsafe URL characters"):
        validate_origin(origin)


@pytest.mark.parametrize("path", ["/ok\t", "/ok\r\n", "/ok\\\\suffix", "/has space"])
def test_scan_paths_reject_unsafe_url_bytes_even_without_origin(path):
    with pytest.raises(ValueError, match="unsafe URL characters"):
        validate_scan_request([path])
    with pytest.raises(ValueError, match="unsafe URL characters"):
        validate_scan_path(path, "https://example.test", lambda host: ["93.184.216.34"])


def test_redirect_chain_rejects_parser_normalized_hop():
    with pytest.raises(ValueError, match="unsafe URL characters"):
        validate_redirect_chain(
            ["https://example.test/", "https://example.test/\tadmin"],
            "https://example.test",
            lambda host: ["93.184.216.34"],
        )


def test_malformed_https_origin_port_fails_during_validation():
    with pytest.raises(ValueError, match="invalid HTTPS origin port"):
        validate_origin("https://example.test:notaport")


@pytest.mark.parametrize("runtime", ["production", "staging", "preview"])
def test_fixture_http_origin_rejected_outside_local_test_runtime(monkeypatch, runtime):
    monkeypatch.setenv("APP_ENV", runtime)
    with pytest.raises(ValueError, match="only canonical HTTPS origins"):
        validate_origin("http://fixture.local")
    with pytest.raises(ValueError, match="only canonical HTTPS origins"):
        validate_scan_path("/index", "http://fixture.local")


@pytest.mark.parametrize("runtime", ["development", "test"])
def test_fixture_origin_remains_available_for_isolated_synthetic_tests(monkeypatch, runtime):
    monkeypatch.setenv("APP_ENV", runtime)
    assert validate_origin("http://fixture.local") == "http://fixture.local"
    assert validate_scan_path("/index", "http://fixture.local") == "http://fixture.local/index"
