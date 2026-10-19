#!/usr/bin/env python3
"""Owner-invoked host helper for the Step-7 Python 3.12 runtime environment.

This helper is deliberately not called by an official runner. A later Owner
may invoke it directly to create the pinned venv outside the repository.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

PYDANTIC_VERSION = "2.10.6"
REQUIREMENT = f"pydantic=={PYDANTIC_VERSION}"
DEFAULT_VENV_ROOT = Path("/home/hazan/step07_runtime_python312_pydantic_2_10_6")

_FINGERPRINT_CODE = r'''import importlib.metadata as md, json, platform, sys
facts = {"python_version": platform.python_version(), "python_major": sys.version_info.major,
         "python_minor": sys.version_info.minor}
errors = []
try:
    import pydantic
    facts["pydantic_version"] = pydantic.__version__
    facts["pydantic_module"] = pydantic.__file__
except Exception as exc:
    errors.append("PYDANTIC_IMPORT:" + type(exc).__name__)
try:
    import rclpy
    facts["rclpy_module"] = rclpy.__file__
    try: facts["rclpy_distribution_version"] = md.version("rclpy")
    except md.PackageNotFoundError: facts["rclpy_distribution_version"] = "ROS_PACKAGE_NO_PYPI_METADATA"
except Exception as exc:
    errors.append("RCLPY_IMPORT:" + type(exc).__name__)
facts["errors"] = errors
print(json.dumps(facts, sort_keys=True, separators=(",", ":")))
'''


def validate_target(venv_root: Path, repository_root: Path) -> tuple[Path, Path]:
    repository = repository_root.resolve(strict=True)
    if not venv_root.is_absolute():
        raise ValueError("VENV_TARGET_MUST_BE_ABSOLUTE")
    target = venv_root.resolve(strict=False)
    try:
        target.relative_to(repository)
    except ValueError:
        pass
    else:
        raise ValueError("VENV_TARGET_MUST_BE_OUTSIDE_REPOSITORY")
    if target == repository:
        raise ValueError("VENV_TARGET_MUST_BE_OUTSIDE_REPOSITORY")
    return target, repository


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f"ENVIRONMENT_COMMAND_FAILED:{command[0]}:{result.returncode}:{result.stdout}{result.stderr}")
    return result


def inspect_interpreter(interpreter: Path) -> dict:
    if not interpreter.is_absolute() or not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:INTERPRETER_MISSING_OR_NOT_EXECUTABLE")
    result = _run([str(interpreter), "-c", _FINGERPRINT_CODE], check=False)
    if result.returncode != 0:
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:INTERPRETER_PROBE_FAILED")
    try:
        facts = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:INTERPRETER_PROBE_INVALID") from exc
    if (facts.get("python_major"), facts.get("python_minor")) != (3, 12):
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:PYTHON_VERSION_MISMATCH")
    if any(error.startswith("PYDANTIC_IMPORT:") for error in facts.get("errors", [])):
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:PYDANTIC_IMPORT_FAILED")
    if facts.get("pydantic_version") != PYDANTIC_VERSION:
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:PYDANTIC_VERSION_MISMATCH")
    if any(error.startswith("RCLPY_IMPORT:") for error in facts.get("errors", [])):
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:RCLPY_IMPORT_FAILED")
    return facts


def prepare_environment(venv_root: Path, repository_root: Path) -> dict:
    target, repository = validate_target(venv_root, repository_root)
    requirements = Path(__file__).with_name("step07_runtime_python_requirements.txt")
    requirement_lines = [line.strip() for line in requirements.read_text(encoding="utf-8").splitlines()
                         if line.strip() and not line.lstrip().startswith("#")]
    if requirement_lines != [REQUIREMENT]:
        raise RuntimeError("RUNTIME_PYTHON_REQUIREMENTS_PIN_MISMATCH")
    if target.exists():
        raise RuntimeError("VENV_TARGET_ALREADY_EXISTS_NO_OVERWRITE")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("RUNTIME_PYTHON_ENVIRONMENT_INVALID:BOOTSTRAP_PYTHON_VERSION_MISMATCH")

    _run([sys.executable, "-m", "venv", "--system-site-packages", str(target)])
    interpreter = target / "bin" / "python"
    _run([str(interpreter), "-m", "pip", "install", "--disable-pip-version-check",
          "--no-input", "-r", str(requirements)])
    facts = inspect_interpreter(interpreter)
    fingerprint = {
        "schema_version": "1.0",
        "interpreter": str(interpreter),
        "venv_root": str(target),
        "repository_root": str(repository),
        "creation_flags": ["--system-site-packages"],
        "requirements": requirement_lines,
        "packages": facts,
    }
    output = target / "step07_runtime_python_environment.json"
    output.write_text(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")), encoding="utf-8")
    return fingerprint


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv-root", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    args = parser.parse_args(argv)
    fingerprint = prepare_environment(args.venv_root, args.repository_root)
    print(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
