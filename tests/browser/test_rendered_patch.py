"""Opt-in real Chromium proof on fixed synthetic bytes; no remote scan service."""
import os
from pathlib import Path
import pytest
from accessfix_ai.domain.static_html import build_image_alt_patch


def test_rendered_fixture_patch_preserves_owner_label_and_blocks_requests():
    if os.getenv("ACCESSFIX_DISPOSABLE_BROWSER") != "yes":
        pytest.skip("Disposable Chromium proof not enabled; NOT a browser pass")
    from playwright.sync_api import sync_playwright
    source = (Path(__file__).resolve().parents[2] / "fixtures/golden/fixture.html").read_bytes()
    patch = build_image_alt_patch(source, "hero", 'Owner label "A & B" <view>')
    blocked = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(java_script_enabled=False, service_workers="block", accept_downloads=False)
        def deny(route):
            blocked.append(route.request.url)
            route.abort("blockedbyclient")
        context.route("**/*", deny)
        page = context.new_page()
        page.set_default_timeout(5000)
        page.set_content(source.decode(), wait_until="load")
        assert page.locator("img#hero").count() == 1
        assert page.locator("img#hero").get_attribute("alt") is None
        before = {"title": page.title(), "heading": page.locator("h1").inner_text(), "button": page.locator("button").inner_text()}
        page.set_content(patch["patched_source"].decode(), wait_until="load")
        assert page.locator("img#hero").get_attribute("alt") == 'Owner label "A & B" <view>'
        assert page.locator("img:not([alt])").count() == 0
        assert {"title": page.title(), "heading": page.locator("h1").inner_text(), "button": page.locator("button").inner_text()} == before
        page.set_content('<img src="https://synthetic.invalid/network-canary">', wait_until="load")
        assert "https://synthetic.invalid/network-canary" in blocked
        context.close()
        browser.close()


@pytest.mark.parametrize('source', ['<img id="hero" src=image.png/>', '<img id="hero" src=image.png />', '<img id="hero" src="image.png"/>', '<IMG id="hero" SRC=image.png/ class=photo>', '<img id="hero" hidden/>', '<img id="hero" data-value=a//>'])
def test_rendered_patch_preserves_existing_dom_attributes(source):
    if os.getenv('ACCESSFIX_DISPOSABLE_BROWSER') != 'yes':
        pytest.skip('Disposable Chromium proof not enabled; NOT a browser pass')
    from playwright.sync_api import sync_playwright
    patch = build_image_alt_patch(source.encode(),'hero','Owner supplied label')
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(java_script_enabled=False,service_workers='block',accept_downloads=False)
        context.route('**/*',lambda route: route.abort('blockedbyclient'))
        page = context.new_page()
        page.set_content(source,wait_until='load')
        attributes = '(node) => Object.fromEntries(Array.from(node.attributes, a => [a.name,a.value]))'
        before = page.locator('img#hero').evaluate(attributes)
        page.set_content(patch['patched_source'].decode(),wait_until='load')
        after = page.locator('img#hero').evaluate(attributes)
        assert after == {**before,'alt':'Owner supplied label'}
        context.close()
        browser.close()
