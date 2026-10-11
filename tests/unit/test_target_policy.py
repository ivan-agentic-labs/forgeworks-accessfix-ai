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


@pytest.mark.parametrize("address", ["100.64.0.1", "100.100.100.200", "100.127.255.254"])
def test_cgnat_literal_origin_is_never_accepted(address):
    # RFC 6598 shared address space: neither private nor reserved in
    # Python's ipaddress semantics, but definitely not public scan space.
    with pytest.raises(ValueError, match="blocked"):
        validate_origin(f"https://{address}")


@pytest.mark.parametrize("answers", [
    ["100.64.0.1"],
    ["93.184.216.34", "100.100.100.200"],
    ["8.8.8.8", "100.127.255.254"],
])
def test_non_global_dns_answer_fails_closed_even_with_public_answers(answers):
    with pytest.raises(ValueError, match="blocked"):
        validate_scan_path("/home", "https://owned.example.test", lambda _: answers)


def test_public_dns_answers_are_accepted_for_bounded_path_and_redirect():
    resolver = lambda _: ["8.8.8.8", "93.184.216.34"]
    assert validate_scan_path("/home", "https://owned.example.test", resolver) == "https://owned.example.test/home"
    assert validate_redirect_chain(
        ["https://owned.example.test/", "https://owned.example.test/home"],
        "https://owned.example.test", resolver,
    ) == ["https://owned.example.test/", "https://owned.example.test/home"]


def test_non_global_redirect_dns_answer_is_rejected_even_on_same_origin():
    answers = iter([["8.8.8.8"], ["8.8.8.8"], ["100.100.100.200"]])
    with pytest.raises(ValueError, match="blocked"):
        validate_redirect_chain(
            ["https://owned.example.test/", "https://owned.example.test/next"],
            "https://owned.example.test",
            lambda _: next(answers),
        )


@pytest.mark.parametrize("runtime", ["development", "test", "staging", "production"])
def test_https_fixture_cannot_bypass_dns_validation(monkeypatch, runtime):
    monkeypatch.setenv("APP_ENV", runtime)
    with pytest.raises(ValueError, match="fixture.local cannot be a public scan origin"):
        validate_origin("https://fixture.local")
    with pytest.raises(ValueError, match="fixture.local cannot be a public scan origin"):
        validate_scan_path("/admin", "https://fixture.local", lambda _: ["8.8.8.8"])


def test_unicode_path_budget_is_enforced_on_actual_utf8_bytes():
    within = "/" + "é" * 1023  # 2047 UTF-8 bytes
    over = "/" + "é" * 1024    # 2049 UTF-8 bytes; only 1025 chars
    assert validate_scan_request([within]) == [within]
    assert validate_scan_path(
        within, "https://owned.example.test", lambda _: ["93.184.216.34"]
    ) == "https://owned.example.test" + within
    with pytest.raises(ValueError, match="UTF-8 bytes"):
        validate_scan_request([over])
    with pytest.raises(ValueError, match="UTF-8 bytes"):
        validate_scan_path(over, "https://owned.example.test", lambda _: ["93.184.216.34"])


def test_unpaired_unicode_surrogates_are_rejected_before_dns_resolution():
    path = "/bad\ud800"
    with pytest.raises(ValueError, match="valid UTF-8"):
        validate_scan_request([path])
    with pytest.raises(ValueError, match="valid UTF-8"):
        validate_scan_path(path, "https://owned.example.test", lambda _: (_ for _ in ()).throw(AssertionError("DNS must not run")))
