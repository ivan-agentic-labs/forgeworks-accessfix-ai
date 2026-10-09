"""Bounded offline image-alt rule. Not browser rendering or WCAG certification."""
from __future__ import annotations

import hashlib
import json
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
