import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[2] / "scripts/load_smoke.py"
spec = importlib.util.spec_from_file_location("load_smoke", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_rate_and_duration_are_hard_capped():
    for rps, duration in ((0, 30), (6, 30), (1, 0), (1, 301)):
        with pytest.raises(SystemExit):
            module.validate(rps, duration)
    module.validate(1, 30)


def test_only_https_targets_are_allowed():
    with pytest.raises(SystemExit, match="https"):
        module.main(["--base", "http://example.invalid", "--rps", "1", "--duration", "1"])


def test_percentile_is_nearest_rank():
    assert module.pct([1, 2, 3, 4], 50) == 2
    assert module.pct([], 95) == 0.0
