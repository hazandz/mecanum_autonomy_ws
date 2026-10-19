from pathlib import Path
import importlib.util

import pytest

HELPER_PATH = Path(__file__).with_name("prepare_step07_runtime_python_environment.py")
SPEC = importlib.util.spec_from_file_location("step07_runtime_python_environment", HELPER_PATH)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)


def test_requirements_pin_is_exact():
    path = HELPER_PATH.with_name("step07_runtime_python_requirements.txt")
    assert path.read_text(encoding="utf-8").strip() == "pydantic==2.10.6"


def test_relative_target_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="VENV_TARGET_MUST_BE_ABSOLUTE"):
        helper.validate_target(Path("relative/venv"), tmp_path)


def test_in_repository_target_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="VENV_TARGET_MUST_BE_OUTSIDE_REPOSITORY"):
        helper.validate_target(repo / ".venv", repo)


def test_existing_target_is_not_overwritten(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = tmp_path / "venv"
    target.mkdir()
    monkeypatch.setattr(helper.sys, "version_info", (3, 12, 0, "final", 0))
    with pytest.raises(RuntimeError, match="VENV_TARGET_ALREADY_EXISTS_NO_OVERWRITE"):
        helper.prepare_environment(target, repo)


def test_prepare_requests_system_site_packages_and_exact_pin(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = tmp_path / "venv"
    calls = []
    monkeypatch.setattr(helper.sys, "version_info", (3, 12, 0, "final", 0))
    def fake_run(command, check=True):
        calls.append(command)
        if command[1:3] == ["-m", "venv"]:
            Path(command[-1]).mkdir(parents=True)
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(helper, "_run", fake_run)
    monkeypatch.setattr(helper, "inspect_interpreter", lambda _path: {
        "python_major": 3, "python_minor": 12, "pydantic_version": "2.10.6",
        "rclpy_validation": "DEFERRED_TO_SOURCED_RUNNER_PREFLIGHT",
    })
    helper.prepare_environment(target, repo)
    assert calls[0][1:4] == ["-m", "venv", "--system-site-packages"]
    assert calls[1][1:3] == ["-m", "pip"] and "pydantic==2.10.6" in Path(calls[1][-1]).read_text()
    assert target.is_dir()


@pytest.mark.parametrize("facts,expected", [
    ({"python_major": 3, "python_minor": 12, "pydantic_import_error": "ModuleNotFoundError"}, "PYDANTIC_IMPORT_FAILED"),
    ({"python_major": 3, "python_minor": 12, "pydantic_version": "1.10.12", "errors": []}, "PYDANTIC_VERSION_MISMATCH"),
    ({"python_major": 3, "python_minor": 11, "pydantic_version": "2.10.6", "errors": []}, "PYTHON_VERSION_MISMATCH"),
])
def test_helper_rejects_invalid_interpreter_fingerprint(tmp_path, monkeypatch, facts, expected):
    import json
    interpreter = tmp_path / "python"
    interpreter.write_text("#!/bin/sh\nexit 0\n")
    interpreter.chmod(0o755)
    monkeypatch.setattr(helper, "_run", lambda *_a, **_k: type("R", (), {
        "returncode": 0, "stdout": json.dumps(facts), "stderr": ""})())
    with pytest.raises(RuntimeError, match=f"RUNTIME_PYTHON_ENVIRONMENT_INVALID:{expected}"):
        helper.inspect_interpreter(interpreter)


def test_helper_rejects_missing_interpreter(tmp_path):
    with pytest.raises(RuntimeError, match="RUNTIME_PYTHON_ENVIRONMENT_INVALID:INTERPRETER_MISSING_OR_NOT_EXECUTABLE"):
        helper.inspect_interpreter(tmp_path / "missing-python")


def test_provisioning_fingerprint_passes_without_rclpy_in_provisioning_shell(tmp_path, monkeypatch):
    import json

    interpreter = tmp_path / "python"
    interpreter.write_text("#!/bin/sh\nexit 0\n")
    interpreter.chmod(0o755)
    facts = {"python_major": 3, "python_minor": 12, "python_version": "3.12.3",
             "pydantic_version": "2.10.6", "pydantic_module": "/venv/site-packages/pydantic/__init__.py"}
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        assert "import rclpy" not in command[-1]
        return type("R", (), {"returncode": 0, "stdout": json.dumps(facts), "stderr": ""})()

    monkeypatch.setattr(helper, "_run", fake_run)
    result = helper.inspect_interpreter(interpreter)
    assert result["pydantic_version"] == "2.10.6"
    assert result["rclpy_validation"] == "DEFERRED_TO_SOURCED_RUNNER_PREFLIGHT"
    assert len(calls) == 1
