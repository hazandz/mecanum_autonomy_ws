import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


_PACKAGE_DIR = Path(__file__).parents[1] / "mecanum_nav_rl"
for _name, _path in (("mecanum_nav_rl", _PACKAGE_DIR),
                     ("mecanum_nav_rl.observations", _PACKAGE_DIR / "observations")):
    if _name not in sys.modules:
        _module = ModuleType(_name)
        _module.__path__ = [str(_path)]
        sys.modules[_name] = _module

from mecanum_nav_rl.observations.v3_ingress_binding_types import IngressMessageBinding
from mecanum_nav_rl.observations.v3_measured_twist_ingress_adapter import (
    adapt_measured_twist_message, EXPECTED_ODOMETRY_FRAME, EXPECTED_ODOMETRY_TOPIC,
    EXPECTED_ODOMETRY_TYPE)
from mecanum_nav_rl.observations.v3_snapshot_types import (
    BASE_FRAME, FRAME_TF_CONTRACT_ID, LIFECYCLE_BARRIER_CONTRACT_ID,
    MEASURED_TWIST_CONTRACT_ID, ActiveLifecycleConfigContext)


class FakeOdometry:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def context():
    return ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, 9, 5, 13, "d" * 64)


def message(frame="odom", child="base_link", values=(0.1, -0.2, 0.3)):
    linear = SimpleNamespace(x=values[0], y=values[1])
    angular = SimpleNamespace(z=values[2])
    twist = SimpleNamespace(twist=SimpleNamespace(linear=linear, angular=angular))
    return FakeOdometry(header=SimpleNamespace(frame_id=frame), child_frame_id=child, twist=twist)


def binding(converter):
    return IngressMessageBinding(FakeOdometry, EXPECTED_ODOMETRY_TOPIC,
                                 EXPECTED_ODOMETRY_TYPE, EXPECTED_ODOMETRY_FRAME,
                                 converter, BASE_FRAME)


def test_happy_path_extracts_only_exact_components_and_context():
    ctx = context()
    result = adapt_measured_twist_message(message(), binding=binding(None), context=ctx)
    assert result is not None
    assert result.contract_id == MEASURED_TWIST_CONTRACT_ID
    assert result.frame_contract_id == FRAME_TF_CONTRACT_ID
    assert result.frame_id == BASE_FRAME
    assert result.components == (0.1, -0.2, 0.3)
    assert result.topic_claim == EXPECTED_ODOMETRY_TOPIC
    assert result.type_claim == EXPECTED_ODOMETRY_TYPE
    assert (result.episode_generation, result.reset_epoch,
            result.runtime_generation, result.config_hash) == (
                ctx.episode_generation, ctx.reset_epoch,
                ctx.runtime_generation, ctx.config_hash)


def test_wrong_exact_class_is_rejected():
    class ChildOdometry(FakeOdometry):
        pass
    bad = ChildOdometry(header=SimpleNamespace(frame_id="odom"), child_frame_id="base_link")
    assert adapt_measured_twist_message(bad, binding=binding(None), context=context()) is None


@pytest.mark.parametrize("bad_message", [object(), FakeOdometry()])
def test_missing_nested_fields_are_rejected(bad_message):
    assert adapt_measured_twist_message(bad_message, binding=binding(None), context=context()) is None


@pytest.mark.parametrize("frame,child", [
    (None, "base_link"), (3, "base_link"), ("odom_alias", "base_link"),
    ("odom", None), ("odom", 3), ("odom", "base_scan"),
])
def test_wrong_frames_and_aliases_are_rejected(frame, child):
    assert adapt_measured_twist_message(message(frame, child), binding=binding(None),
                                        context=context()) is None


@pytest.mark.parametrize("values", [
    (True, 0.0, 0.0), (float("nan"), 0.0, 0.0),
    (0.0, float("inf"), 0.0), (0.0, 0.0, float("-inf")),
    (1, 0.0, 0.0),
])
def test_bool_nonfinite_or_coerced_components_are_rejected(values):
    assert adapt_measured_twist_message(message(values=values), binding=binding(None),
                                        context=context()) is None


def test_unexpected_converter_is_not_invoked_and_is_rejected():
    called = []
    bad_binding = binding(lambda _message: called.append(True) or (0.0, 0.0, 0.0))
    assert adapt_measured_twist_message(message(), binding=bad_binding,
                                        context=context()) is None
    assert called == []


def test_missing_or_wrong_context_is_rejected():
    assert adapt_measured_twist_message(message(), binding=binding(None), context=None) is None
    assert adapt_measured_twist_message(message(), binding=binding(None), context=object()) is None
