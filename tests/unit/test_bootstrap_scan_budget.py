"""Bootstrap scanning stays bounded on large nonsecret source strings and caches."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_large_allowed_text_and_cache_do_not_stall_scanner():
    source = ROOT / 'tests' / '.temporary_scan_budget.txt'
    cache = ROOT / '.pytest_cache' / 'temporary_scan_budget.txt'
    cache.parent.mkdir(exist_ok=True)
    try:
        source.write_text('x' * 1048576 + '@example.com\n', encoding='utf-8')
        cache.write_text('x' * 1048576, encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_bootstrap.py')], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout
    finally:
        source.unlink(missing_ok=True)
        cache.unlink(missing_ok=True)


def test_scanner_still_rejects_synthetic_token_pattern():
    source = ROOT / 'tests' / '.temporary_scan_token.txt'
    try:
        source.write_text('ghp_' + 'X' * 40, encoding='utf-8')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_bootstrap.py')], capture_output=True, text=True, timeout=10)
        assert result.returncode == 1
        assert 'GitHub token' in result.stdout
        assert ('ghp_' + 'X' * 40) not in result.stdout
    finally:
        source.unlink(missing_ok=True)
