import pytest
import subprocess
from accessfix_ai.domain.static_html import build_image_alt_patch, image_alt_findings


def test_generated_patch_is_actually_applicable_with_no_final_newline(tmp_path):
    source = b'<main>\r<img id="hero"></main>'
    result = build_image_alt_patch(source, "hero", "Owner label")
    (tmp_path / "source.html").write_bytes(source)
    subprocess.run(["git", "apply", "--no-index", "-"], input=result["patch"].encode(), cwd=tmp_path, check=True, capture_output=True)
    assert (tmp_path / "source.html").read_bytes() == result["patched_source"]


def test_actual_patch_preserves_other_source_and_retests():
    source = '<main>é\n<img id="hero" src="a.png"/><img id="other"></main>'.encode()
    result = build_image_alt_patch(source, "hero", 'Owner says "A & B" <view>')
    assert b'alt="Owner says &quot;A &amp; B&quot; &lt;view&gt;"' in result["patched_source"]
    assert b'<img id="other">' in result["patched_source"]
    assert result["patched_source"].startswith('<main>é\n'.encode())
    assert result["static_retest"] == "PASSED"
    assert result["remaining_findings"] == 1
    assert image_alt_findings(result["patched_source"])[0]["selector"] == "img#other"
    assert result["source_sha256"] != result["patched_sha256"]
    assert result["patch"] and len(result["patch_sha256"]) == 64


@pytest.mark.parametrize("source", [b'<img id="hero"><div id="hero"></div>', b'<img id="hero" alt="">', b'<div id="hero"></div>', b'<img id="hero" id="hero">'])
def test_ambiguous_or_existing_targets_fail_closed(source):
    with pytest.raises(ValueError):
        build_image_alt_patch(source, "hero", "Owner label")


@pytest.mark.parametrize("label", ["", " ", "a" * 501, "label\ncontrol"])
def test_no_invented_empty_or_unbounded_label(label):
    with pytest.raises(ValueError):
        build_image_alt_patch(b'<img id="hero">', "hero", label)


@pytest.mark.parametrize('source', [b'<img id="hero" src=image.png/>', b'<img id="hero" src=image.png />', b'<img id="hero" src="image.png"/>', b'<IMG id="hero" SRC=image.png/ class=photo>', b'<img id="hero" hidden/>', b'<img id="hero" data-value=a//>'])
def test_patch_preserves_every_existing_image_attribute(source):
    from html.parser import HTMLParser
    def attributes(body):
        values = []
        class Parser(HTMLParser):
            def handle_starttag(self,tag,attrs):
                if tag == 'img': values.append(dict(attrs))
            handle_startendtag = handle_starttag
        Parser().feed(body.decode())
        return values[0]
    before = attributes(source)
    result = build_image_alt_patch(source, 'hero', 'Owner supplied label')
    assert attributes(result['patched_source']) == {**before, 'alt':'Owner supplied label'}
