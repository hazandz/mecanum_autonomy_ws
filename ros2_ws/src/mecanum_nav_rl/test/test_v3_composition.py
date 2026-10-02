from __future__ import annotations

from copy import deepcopy
import ast
import inspect
from collections.abc import Mapping

import pytest

from mecanum_nav_rl.config import (
    CanonicalFragmentKindV3 as PackageCanonicalFragmentKindV3,
    CanonicalFragmentV3 as PackageCanonicalFragmentV3,
    compose_canonical_v3_fragments as package_compose_canonical_v3_fragments,
)
from mecanum_nav_rl.config.v3_composition import (
    CanonicalFragmentKindV3,
    CanonicalFragmentV3,
    compose_canonical_v3_fragments,
)


def _fragment(kind: CanonicalFragmentKindV3, values: Mapping[str, object]) -> CanonicalFragmentV3:
    return CanonicalFragmentV3(kind=kind, values=values)


def _fragments(
    *,
    profile_runtime: object | None = None,
    mode_runtime: object | None = None,
) -> tuple[CanonicalFragmentV3, ...]:
    profile_runtime = (
        {"runtime_profile": "sim_train", "use_sim_time": True}
        if profile_runtime is None
        else profile_runtime
    )
    mode_runtime = (
        {"navigation_mode": "LOCAL_TRAINING"}
        if mode_runtime is None
        else mode_runtime
    )
    return (
        _fragment(
            CanonicalFragmentKindV3.BASE,
            {
                "schema_version": "3.0",
                "project": {"identity": {"name": "project"}},
                "provenance": {"source": "explicit"},
                "observation": {"schema": "fixed"},
                "action": {"shape": "three"},
                "map_identity": {"map": "external"},
            },
        ),
        _fragment(CanonicalFragmentKindV3.FRAMES, {"frames_tf": {"map": "map"}}),
        _fragment(CanonicalFragmentKindV3.TOPICS_QOS, {"topics_qos": []}),
        _fragment(
            CanonicalFragmentKindV3.STATE_LOCALIZATION,
            {
                "state_estimation": {"owner": "EKF"},
                "localization": {"owner": "AMCL"},
            },
        ),
        _fragment(
            CanonicalFragmentKindV3.SYSTEM_CONTRACTS,
            {
                "command_safety": {"owner": "SafetySupervisor"},
                "reward": {"contract": "external"},
                "training": {"contract": "external"},
                "evaluation": {"contract": "external"},
                "acceptance": {"contract": "external"},
            },
        ),
        _fragment(
            CanonicalFragmentKindV3.RUNTIME_PROFILE,
            {
                "runtime": profile_runtime,
                "motion_limits": {"source": "unresolved"},
            },
        ),
        _fragment(
            CanonicalFragmentKindV3.NAVIGATION_MODE,
            {"runtime": mode_runtime, "navigation": {"owner": "PPO"}},
        ),
    )


def test_package_level_public_imports_match_composition_module_and_compose() -> None:
    assert PackageCanonicalFragmentKindV3 is CanonicalFragmentKindV3
    assert PackageCanonicalFragmentV3 is CanonicalFragmentV3
    assert package_compose_canonical_v3_fragments is compose_canonical_v3_fragments
    result = package_compose_canonical_v3_fragments(*_fragments())
    assert result["runtime"]["navigation_mode"] == "LOCAL_TRAINING"


def test_happy_path_composes_all_seven_owned_fragments() -> None:
    result = compose_canonical_v3_fragments(*_fragments())
    assert result["runtime"] == {
        "runtime_profile": "sim_train",
        "use_sim_time": True,
        "navigation_mode": "LOCAL_TRAINING",
    }
    assert set(result) == {
        "schema_version", "project", "provenance", "observation", "action",
        "map_identity", "frames_tf", "topics_qos", "state_estimation",
        "localization", "command_safety", "reward", "training", "evaluation",
        "acceptance", "runtime", "motion_limits", "navigation",
    }


def test_runtime_profile_and_navigation_mode_merge_disjoint_descendants() -> None:
    result = compose_canonical_v3_fragments(*_fragments())
    assert result["runtime"]["runtime_profile"] == "sim_train"
    assert result["runtime"]["navigation_mode"] == "LOCAL_TRAINING"


def test_inputs_remain_unmutated_and_output_has_no_nested_alias() -> None:
    fragments = _fragments()
    before = deepcopy(fragments[0].values)
    result = compose_canonical_v3_fragments(*fragments)
    result["project"]["identity"]["name"] = "changed"
    assert fragments[0].values == before
    assert fragments[0].values["project"]["identity"]["name"] == "project"


def test_missing_duplicate_and_wrong_order_kinds_fail_closed() -> None:
    fragments = _fragments()
    with pytest.raises(TypeError):
        compose_canonical_v3_fragments(*fragments[:-1])
    with pytest.raises(ValueError, match="expected fragment kind FRAMES, got BASE"):
        compose_canonical_v3_fragments(
            fragments[0], fragments[0], *fragments[2:]
        )
    with pytest.raises(ValueError, match="expected fragment kind BASE, got FRAMES"):
        compose_canonical_v3_fragments(
            fragments[1], fragments[0], *fragments[2:]
        )


def test_fragment_top_level_ownership_and_unknown_fields_fail_closed() -> None:
    fragments = list(_fragments())
    fragments[1] = _fragment(
        CanonicalFragmentKindV3.FRAMES, {"observation": {"wrong": True}}
    )
    with pytest.raises(ValueError, match="observation is not owned"):
        compose_canonical_v3_fragments(*fragments)
    fragments = list(_fragments())
    fragments[0] = _fragment(
        CanonicalFragmentKindV3.BASE, {"not_a_canonical_field": {"x": 1}}
    )
    with pytest.raises(ValueError, match="unknown canonical top-level field not_a_canonical_field"):
        compose_canonical_v3_fragments(*fragments)


def test_duplicate_leaf_even_with_same_value_reports_canonical_path() -> None:
    fragments = _fragments(profile_runtime={"navigation_mode": "LOCAL_TRAINING"})
    with pytest.raises(ValueError, match="runtime.navigation_mode"):
        compose_canonical_v3_fragments(*fragments)


def test_scalar_mapping_collision_reports_canonical_path() -> None:
    fragments = _fragments(profile_runtime="not-a-mapping")
    with pytest.raises(ValueError, match="runtime"):
        compose_canonical_v3_fragments(*fragments)


def test_new_module_has_no_path_yaml_or_runtime_imports() -> None:
    module = __import__("mecanum_nav_rl.config.v3_composition", fromlist=["*"])
    tree = ast.parse(inspect.getsource(module))
    forbidden_roots = {"pathlib", "yaml", "os", "rclpy", "gazebo", "gymnasium", "stable_baselines3"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        assert not any(name.split(".")[0] in forbidden_roots for name in names)


def test_output_is_plain_mapping_without_compiler_hash_or_model_construction() -> None:
    result = compose_canonical_v3_fragments(*_fragments())
    assert type(result) is dict
    assert not hasattr(result, "model_dump")
