"""Run the upstream axe image-alt rule on a local, disconnected Chromium fixture.

This deliberately does not crawl any live website, attest WCAG compliance, or
make any network request. The axe runtime is installed only into the CI runner.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from accessfix_ai.domain.static_html import build_image_alt_patch


def test_offline_axe_detects_and_rechecks_owner_authored_image_alt():
    if os.getenv("ACCESSFIX_DISPOSABLE_BROWSER") != "yes":
        pytest.skip("Only opt-in disposable Chromium is allowed")
    script = os.getenv("ACCESSFIX_AXE_SCRIPT")
    if not script:
        pytest.skip("A pinned local axe-core runtime was not supplied")
    axe_path = Path(script)
    if not axe_path.is_file() or axe_path.stat().st_size > 1_000_000:
        raise AssertionError("Trusted axe-core runtime is missing or exceeds size budget")

    from playwright.sync_api import sync_playwright
    fixture = (Path(__file__).resolve().parents[2] / "fixtures/golden/fixture.html").read_bytes()
    patch = build_image_alt_patch(fixture, "hero", "Owner-confirmed illustration")
    network_attempts = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                java_script_enabled=True, service_workers="block",
                accept_downloads=False, offline=True,
            )
            context.route("**/*", lambda route: (
                network_attempts.append(route.request.url),
                route.abort("blockedbyclient"),
            ))
            try:
                page = context.new_page()
                page.set_default_timeout(10000)

                def axe_results(source: bytes) -> dict:
                    page.set_content(source.decode("utf-8", errors="strict"), wait_until="load")
                    page.add_script_tag(path=str(axe_path))
                    return page.evaluate("""async () => {
                        const report = await window.axe.run(document, {
                            runOnly: {type: 'rule', values: ['image-alt']}
                        });
                        return {
                            violations: report.violations.map(v => ({
                                id: v.id,
                                targets: v.nodes.map(n => n.target)
                            })),
                            incomplete: report.incomplete.map(v => v.id),
                            passes: report.passes.map(v => v.id)
                        };
                    }""")

                before = axe_results(fixture)
                assert before["violations"], "axe failed to identify missing image alternative"
                assert any(rule["id"] == "image-alt" for rule in before["violations"]), before
                after = axe_results(patch["patched_source"])
                assert after["violations"] == [], after
                assert "image-alt" in after["passes"], after
                assert not network_attempts, "Disposable axe scan attempted external network activity"
            finally:
                context.close()
        finally:
            browser.close()
