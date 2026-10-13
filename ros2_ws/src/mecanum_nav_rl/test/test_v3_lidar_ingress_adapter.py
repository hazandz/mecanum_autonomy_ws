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
from mecanum_nav_rl.observations.v3_lidar_ingress_adapter import (
    adapt_lidar_message, EXPECTED_LIDAR_TOPIC, EXPECTED_LIDAR_TYPE)
from mecanum_nav_rl.observations.v3_snapshot_types import (
    FRAME_TF_CONTRACT_ID, LIDAR_CONTRACT_ID, LIFECYCLE_BARRIER_CONTRACT_ID,
    ActiveLifecycleConfigContext)


class FakeScan:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def context():
    return ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, 7, 3, 11, "b" * 64)


def message(frame="lidar_frame"):
    return FakeScan(header=SimpleNamespace(frame_id=frame))


def binding(callback):
    return IngressMessageBinding(
        FakeScan, EXPECTED_LIDAR_TOPIC, EXPECTED_LIDAR_TYPE, "lidar_frame", callback, None)


def convert(_message):
    return (0.25,) * 72


def test_happy_path_uses_exact_input_context_and_one_callback():
    calls = []
    ctx = context()
    result = adapt_lidar_message(message(), binding=binding(lambda m: calls.append(m) or convert(m)), context=ctx)
    assert result is not None
    assert len(calls) == 1
    assert result.contract_id == LIDAR_CONTRACT_ID
    assert result.frame_contract_id == FRAME_TF_CONTRACT_ID
    assert result.frame_id == "lidar_frame"
    assert result.sectors == (0.25,) * 72
    assert (result.episode_generation, result.reset_epoch,
            result.runtime_generation, result.config_hash) == (
                ctx.episode_generation, ctx.reset_epoch,
                ctx.runtime_generation, ctx.config_hash)
    assert calls[0].header.frame_id == "lidar_frame"


def test_wrong_exact_class_is_rejected_without_callback():
    called = []
    class ChildScan(FakeScan):
        pass
    result = adapt_lidar_message(ChildScan(header=SimpleNamespace(frame_id="lidar_frame")),
                                 binding=binding(lambda m: called.append(m) or convert(m)),
                                 context=context())
    assert result is None
    assert called == []


@pytest.mark.parametrize("bad_message", [object(), FakeScan()])
def test_missing_header_or_frame_is_rejected(bad_message):
    assert adapt_lidar_message(bad_message, binding=binding(convert), context=context()) is None


@pytest.mark.parametrize("frame", [None, 3, "RPLiDAR_A1M8_1", "base_scan", "lidar_link", "other"])
def test_alias_and_invalid_frame_are_rejected(frame):
    assert adapt_lidar_message(message(frame), binding=binding(convert), context=context()) is None


@pytest.mark.parametrize("bad_result", [
    [0.25] * 72, (0.25,) * 71, (True,) + (0.25,) * 71,
    (float("nan"),) + (0.25,) * 71,
    (float("inf"),) + (0.25,) * 71,
    (1,) + (0.25,) * 71,
])
def test_bad_callback_result_is_rejected(bad_result):
    assert adapt_lidar_message(message(), binding=binding(lambda _m: bad_result),
                               context=context()) is None


def test_callback_exception_and_unexpected_binding_metadata_fail_closed():
    def raises(_message):
        raise RuntimeError("fixture callback failure")
    assert adapt_lidar_message(message(), binding=binding(raises), context=context()) is None
    wrong = IngressMessageBinding(FakeScan, "/other", EXPECTED_LIDAR_TYPE,
                                  "lidar_frame", convert, None)
    assert adapt_lidar_message(message(), binding=wrong, context=context()) is None


def test_missing_context_or_wrong_context_type_is_rejected():
    assert adapt_lidar_message(message(), binding=binding(convert), context=None) is None
    assert adapt_lidar_message(message(), binding=binding(convert), context=object()) is None
