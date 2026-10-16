import pytest

from accessfix_ai.domain.static_html import image_alt_findings, MAX_SOURCE_BYTES


def test_missing_alt_uses_actual_source_and_unique_selector():
    source = b'<main><img id="hero" src="a.png"><img alt="Label"><img alt=""></main>'
    result = image_alt_findings(source)
    assert len(result) == 1 and result[0]["selector"] == "img#hero"
    assert result == image_alt_findings(source)
    assert result[0]["fingerprint"] != image_alt_findings(source.replace(b"a.png", b"b.png"))[0]["fingerprint"]
    assert image_alt_findings(b'<img id="hero" alt="Owner supplied label">') == []


def test_duplicate_ids_never_produce_unique_id_mapping():
    result = image_alt_findings(b'<div id="same"></div><img id="same"><img id="same"/>')
    assert len(result) == 2
    assert all("#" not in row["selector"] for row in result)
    assert result[0]["fingerprint"] != result[1]["fingerprint"]


@pytest.mark.parametrize("source", [b'<img alt="a" alt="b">', b'\x00', b'\xff', b'a' * (MAX_SOURCE_BYTES + 1)], ids=["duplicate-attributes", "nul", "invalid-utf8", "oversized"])
def test_invalid_or_oversized_source_rejected(source):
    with pytest.raises(ValueError):
        image_alt_findings(source)


def test_valueless_alt_is_not_a_verified_alternative():
    assert len(image_alt_findings(b'<IMG id="hero" alt>')) == 1


def test_scripts_do_not_create_fake_image_nodes():
    assert image_alt_findings(b'<script>const x = "<img>";</script>') == []

def test_offline_scanner_detects_unlabelled_image_submit_controls():
    source = b'<form><input type="IMAGE" id="submit" src="/submit.png"><input type="image" alt=""></form>'
    findings = image_alt_findings(source)
    assert len(findings) == 2
    assert findings[0]["selector"] == 'input[type="image"]#submit'
    assert findings[1]["selector"] == 'input[type="image"]'
    assert findings[0]["fingerprint"] != findings[1]["fingerprint"]


def test_image_submit_control_with_action_label_is_not_reported():
    source = b'<form><input type="image" alt="Submit order"><input type="submit" value="Submit"></form>'
    assert image_alt_findings(source) == []


def test_duplicate_image_submit_attributes_are_rejected():
    with pytest.raises(ValueError, match="Duplicate image attributes"):
        image_alt_findings(b'<input type="image" alt="one" alt="two">')
