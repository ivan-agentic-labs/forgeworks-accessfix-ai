# Image patch attribute preservation — 2026-10-11

An unquoted attribute value ending in `/` was incorrectly treated as an HTML self-closing marker. For example, `<img id="hero" src=image.png/>` has `src="image.png/"`; the prior patch changed it to `image.png`. Two regression fixtures reproduced this unintended attribute mutation.

Patch insertion now uses the parser's start-tag/start-end-tag distinction and verifies that the target's decoded attributes equal the original attributes plus the owner-authored alt value. Any unintended attribute change rejects the patch. No text label is invented and existing alt values are still protected.

Six unit cases cover unquoted/slash-suffixed values, actual self-closing markup, quoted values, case normalization, boolean attributes and double trailing slashes. Six additional disposable Chromium cases independently compare before/after DOM attributes with JavaScript disabled and all remote requests blocked.

Local complete suite: `python -W error -m pytest tests -q`: 179 passed, 8 skipped (seven opt-in Chromium cases and PostgreSQL). Browser cases are mandatory in the dedicated disposable Chromium workflow; local browser download remains unavailable. Exact-commit CI receipts provide rendered proof. These tests do not certify WCAG compliance, source mapping or full HTML parser/browser equivalence.
