"""Guarded launch entry point; it intentionally creates no runtime graph."""

from pathlib import Path

from mecanum_nav_bringup.navigation_v1_static_contract import (
    StaticContractError,
    reject_pending_markers,
)


def generate_launch_description():
    """Fail closed before any launch graph is constructed.

    The checked-in templates contain unresolved source and map bindings. Even
    after those are separately resolved, runtime graph creation needs its own
    authorization and implementation packet; this source never creates nodes.
    """
    package_root = Path(__file__).resolve().parents[1]
    template_paths = (
        package_root / "config" / "navigation_v1_source_lock.template.yaml",
        package_root / "config" / "navigation_v1_static_bringup.template.yaml",
    )
    try:
        texts = tuple(path.read_text(encoding="utf-8") for path in template_paths)
    except OSError as exc:
        raise RuntimeError("Navigation V1 static templates are unavailable") from exc

    try:
        reject_pending_markers(*texts)
    except StaticContractError as exc:
        raise RuntimeError("Navigation V1 source closure is unresolved") from exc

    raise RuntimeError(
        "Navigation V1 runtime graph creation is outside this static-source authorization"
    )
