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
from mecanum_nav_rl.observations.v3_local_reference_ingress_adapter import (
    adapt_local_reference_message, EXPECTED_PATH_SOURCE_FRAME, EXPECTED_PATH_TYPE)
from mecanum_nav_rl.observations.v3_snapshot_types import (
    BASE_FRAME, FRAME_TF_CONTRACT_ID, LOCAL_REFERENCE_CONTRACT_ID,
    LIFECYCLE_BARRIER_CONTRACT_ID, ActiveLifecycleConfigContext)


class FakePath:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def context():
    return ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID, 8, 4, 12, "c" * 64)


def message(frame="map"):
    return FakePath(header=SimpleNamespace(frame_id=frame))


def binding(callback):
    return IngressMessageBinding(FakePath, None, EXPECTED_PATH_TYPE, "map", callback, None)


def project(_message):
    return (2.5, 0.25, 0.9682458365518543)


def test_happy_path_uses_preverified_callback_and_injected_context():
    calls = []
    ctx = context()
    result = adapt_local_reference_message(
        message(), binding=binding(lambda m: calls.append(m) or project(m)), context=ctx)
    assert result is not None
    assert len(calls) == 1
    assert calls[0].header.frame_id == "map"
    assert result.contract_id == LOCAL_REFERENCE_CONTRACT_ID
    assert result.frame_contract_id == FRAME_TF_CONTRACT_ID
    assert result.frame_id == BASE_FRAME
    assert result.features == project(calls[0])
    assert result.topic_claim is None
    assert result.type_claim == EXPECTED_PATH_TYPE
    assert (result.episode_generation, result.reset_epoch,
            result.runtime_generation, result.config_hash) == (
                ctx.episode_generation, ctx.reset_epoch,
                ctx.runtime_generation, ctx.config_hash)


def test_wrong_exact_class_is_rejected_without_callback():
    called = []
    class ChildPath(FakePath):
        pass
    result = adapt_local_reference_message(
        ChildPath(header=SimpleNamespace(frame_id="map")),
        binding=binding(lambda m: called.append(m) or project(m)), context=context())
    assert result is None
    assert called == []


@pytest.mark.parametrize("bad_message", [object(), FakePath()])
def test_missing_header_or_frame_is_rejected(bad_message):
    assert adapt_local_reference_message(bad_message, binding=binding(project), context=context()) is None


@pytest.mark.parametrize("frame", [None, 3, "base_link", "map_alias", "world"])
def test_wrong_or_alias_frame_is_rejected(frame):
    assert adapt_local_reference_message(message(frame), binding=binding(project), context=context()) is None


@pytest.mark.parametrize("bad_result", [
    [2.5, 0.25, 0.9], (2.5, 0.25), (True, 0.25, 0.9),
    (float("nan"), 0.25, 0.9), (2.5, float("inf"), 0.9), (2, 0.25, 0.9),
])
def test_bad_callback_result_is_rejected(bad_result):
    assert adapt_local_reference_message(message(), binding=binding(lambda _m: bad_result),
                                         context=context()) is None


def test_callback_exception_and_runtime_topic_claim_are_rejected():
    def raises(_message):
        raise RuntimeError("fixture callback failure")
    assert adapt_local_reference_message(message(), binding=binding(raises), context=context()) is None
    wrong = IngressMessageBinding(
        FakePath, "/some/plan/topic", EXPECTED_PATH_TYPE, "map", project, None)
    assert adapt_local_reference_message(message(), binding=wrong, context=context()) is None


def test_missing_or_wrong_context_is_rejected():
    assert adapt_local_reference_message(message(), binding=binding(project), context=None) is None
    assert adapt_local_reference_message(message(), binding=binding(project), context=object()) is None
