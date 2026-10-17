import json
import subprocess
import sys
from pathlib import Path


def test_cli_fixture_build_validate_round_trip(tmp_path: Path) -> None:
    fixture = tmp_path / "bundle.json"
    result = subprocess.run([sys.executable, "-m", "youseela.cli", "fixture", "--output", str(fixture)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(fixture.read_text())
    assert payload["data_kind"] == "fixture"
    result = subprocess.run([sys.executable, "-m", "youseela.cli", "validate", str(fixture)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "3 areas" in result.stdout


def test_cli_missing_key_returns_helpful_error_without_traceback(tmp_path: Path) -> None:
    import os
    env = dict(os.environ, CENSUS_API_KEY="")
    result = subprocess.run([sys.executable, "-m", "youseela.cli", "census", "--year", "2024", "--output", str(tmp_path/"data.json")], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "CENSUS_API_KEY" in result.stderr
    assert "Traceback" not in result.stderr
