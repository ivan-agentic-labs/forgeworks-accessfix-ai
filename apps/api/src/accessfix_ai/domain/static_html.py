"""Bounded offline image-alt rule. Not browser rendering or WCAG certification."""
from __future__ import annotations

import hashlib
import json
import difflib
from html import escape
from html.parser import HTMLParser

MAX_SOURCE_BYTES = 1_048_576
MAX_ELEMENTS = 20_000


def image_alt_findings(source: bytes) -> list[dict]:
    if not isinstance(source, bytes) or len(source) > MAX_SOURCE_BYTES:
        raise ValueError("HTML source exceeds the offline scanner budget")
    html = source.decode("utf-8", errors="strict")
    if "\x00" in html:
        raise ValueError("NUL is not accepted in HTML source")
    source_sha = hashlib.sha256(source).hexdigest()

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.elements = 0
            self.images = []
            self.ids = {}

        def handle_starttag(self, tag, attrs):
            self.elements += 1
            if self.elements > MAX_ELEMENTS:
                raise ValueError("HTML element budget exceeded")
            values = dict(attrs)
            identifier = values.get("id")
            if identifier:
                self.ids[identifier] = self.ids.get(identifier, 0) + 1
            if tag == "img":
                # Duplicate attributes are ambiguous, not safe repair targets.
                names = [key for key, _ in attrs]
                if len(names) != len(set(names)):
                    raise ValueError("Duplicate image attributes are unsupported")
                self.images.append((values, self.get_starttag_text()))

        handle_startendtag = handle_starttag

    parser = Parser()
    parser.feed(html)
    parser.close()
    findings = []
    for index, (attrs, snippet) in enumerate(parser.images, 1):
        # Empty alt is intentional decoration and requires separate human review.
        # A valueless alt attribute is not a valid supplied alternative.
        if "alt" in attrs and attrs["alt"] is not None:
            continue
        identifier = attrs.get("id")
        safe_id = identifier and all(c.isascii() and (c.isalnum() or c in "_-") for c in identifier)
        # Without a unique safe ID, a broad selector is honest; a global image
        # ordinal is not a valid CSS nth-of-type position across different parents.
        selector = "img#" + identifier if safe_id and parser.ids[identifier] == 1 else "img"
        fingerprint = hashlib.sha256(json.dumps([source_sha, "image-alt", index, snippet], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        findings.append({"rule_id": "image-alt", "severity": "SERIOUS", "selector": selector, "fingerprint": fingerprint, "manual_required": 1})
    return findings


def build_image_alt_patch(source: bytes, identifier: str, alt_text: str) -> dict:
    """Repair exactly one unambiguous image using an owner-supplied label.

    Returned bytes must be persisted and bound to a repository snapshot by the
    caller. This function does not claim repository mapping or semantic quality.
    """
    image_alt_findings(source)  # Validate encoding, attributes and budgets first.
    if not identifier or not all(c.isascii() and (c.isalnum() or c in "_-") for c in identifier):
        raise ValueError("A safe unique image ID is required")
    if not isinstance(alt_text, str) or not alt_text.strip() or len(alt_text) > 500:
        raise ValueError("Supply a nonempty owner-authored label of at most 500 characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in alt_text):
        raise ValueError("Control characters are not allowed in alternative text")
    text = source.decode("utf-8")
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    matches = []

    class TargetParser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if values.get("id") == identifier:
                if len(attrs) != len(values):
                    raise ValueError("Ambiguous duplicate target attributes")
                line, column = self.getpos()
                matches.append((tag, values, starts[line - 1] + column, self.get_starttag_text()))

        handle_startendtag = handle_starttag

    parser = TargetParser(convert_charrefs=True)
    parser.feed(text)
    parser.close()
    if len(matches) != 1 or matches[0][0] != "img":
        raise ValueError("Target must be exactly one uniquely identified image")
    _, attrs, start, raw = matches[0]
    if "alt" in attrs:
        raise ValueError("Existing alternative text requires a separate reviewed change")
    insertion = len(raw) - (2 if raw.endswith("/>") else 1)
    replacement = raw[:insertion] + ' alt="' + escape(alt_text, quote=True) + '"' + raw[insertion:]
    patched = (text[:start] + replacement + text[start + len(raw):]).encode("utf-8")
    after = image_alt_findings(patched)
    before = image_alt_findings(source)
    if len(after) != len(before) - 1 or any(row["selector"] == "img#" + identifier for row in after):
        raise ValueError("Static retest did not remove exactly the target finding")
    patch = "".join(difflib.unified_diff(text.splitlines(keepends=True), patched.decode("utf-8").splitlines(keepends=True), fromfile="a/source.html", tofile="b/source.html"))
    return {"source_sha256": hashlib.sha256(source).hexdigest(), "patched_sha256": hashlib.sha256(patched).hexdigest(), "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(), "patch": patch, "patched_source": patched, "static_retest": "PASSED", "remaining_findings": len(after)}
