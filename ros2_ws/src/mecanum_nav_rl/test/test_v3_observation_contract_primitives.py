"""Focused tests for the pure-Python WP-04 Gate A structural primitives."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import sys
from pathlib import Path

import pytest

from mecanum_nav_rl.core.v3_observation_contracts import (
    ContractReferenceV3,
    GateASchemaConstructionFailure,
    GateASchemaMappedFailure,
    GateASchemaValidationError,
    ObservationCutoffV3,
    ObservationInputContractV3,
)


S2_ID = "mecanum.snapshot-synchronization-temporal/v1"
S2_SHA = "1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f"
RECEIPT_ID = "mecanum.final-issued-receipt/v2"
RECEIPT_SHA = "0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a"


def _valid_cutoff(**overrides: object) -> ObservationCutoffV3:
    values: dict[str, object] = {
        "lifecycle_identity": "lifecycle-opaque",
        "epoch": 0,
        "generation": 0,
        "time_domain": "profile-ros-time",
        "cutoff_time_ns": 12,
        "action_barrier_time_ns": 10,
        "reset_barrier_time_ns": 11,
    }
    values.update(overrides)
    return ObservationCutoffV3(**values)  # type: ignore[arg-type]


def _valid_input_contract(**overrides: object) -> ObservationInputContractV3:
    values: dict[str, object] = {
        "s2_provenance_reference": ContractReferenceV3(
            contract_id=S2_ID,
            contract_sha256=S2_SHA,
        ),
        "receipt_interface_reference": ContractReferenceV3(
            contract_id=RECEIPT_ID,
            contract_sha256=RECEIPT_SHA,
        ),
    }
    values.update(overrides)
    return ObservationInputContractV3(**values)  # type: ignore[arg-type]


def _construction_detail(callable_: object) -> GateASchemaConstructionFailure:
    with pytest.raises(GateASchemaValidationError) as captured:
        callable_()  # type: ignore[operator]
    detail = captured.value.detail
    assert type(detail) is GateASchemaConstructionFailure
    assert not hasattr(detail, "status")
    return detail


def _mapped_detail(callable_: object) -> GateASchemaMappedFailure:
    with pytest.raises(GateASchemaValidationError) as captured:
        callable_()  # type: ignore[operator]
    detail = captured.value.detail
    assert type(detail) is GateASchemaMappedFailure
    return detail


def test_positive_construction_and_exact_schema_members() -> None:
    cutoff = _valid_cutoff()
    reference = ContractReferenceV3(contract_id="opaque", contract_sha256="opaque-sha")
    input_contract = _valid_input_contract()

    assert tuple(field.name for field in dataclasses.fields(ObservationCutoffV3)) == (
        "lifecycle_identity",
        "epoch",
        "generation",
        "time_domain",
        "cutoff_time_ns",
        "action_barrier_time_ns",
        "reset_barrier_time_ns",
    )
    assert tuple(field.name for field in dataclasses.fields(ContractReferenceV3)) == (
        "contract_id",
        "contract_sha256",
    )
    assert tuple(field.name for field in dataclasses.fields(ObservationInputContractV3)) == (
        "s2_provenance_reference",
        "receipt_interface_reference",
    )
    assert cutoff.cutoff_time_ns == 12
    assert reference.contract_id == "opaque"
    assert input_contract.receipt_interface_reference.contract_id == RECEIPT_ID


def test_keyword_only_and_no_implicit_defaults() -> None:
    """Keyword-only positional rejection is call-shape behavior, not error mapping."""

    for model, expected_names in (
        (
            ObservationCutoffV3,
            (
                "lifecycle_identity",
                "epoch",
                "generation",
                "time_domain",
                "cutoff_time_ns",
                "action_barrier_time_ns",
                "reset_barrier_time_ns",
            ),
        ),
        (ContractReferenceV3, ("contract_id", "contract_sha256")),
        (
            ObservationInputContractV3,
            ("s2_provenance_reference", "receipt_interface_reference"),
        ),
    ):
        signature = inspect.signature(model)
        assert tuple(signature.parameters) == expected_names
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            and parameter.default is inspect.Parameter.empty
            for parameter in signature.parameters.values()
        )

    with pytest.raises(TypeError):
        ObservationCutoffV3("lifecycle-opaque")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("field_name", "bad_value", "reason"),
    [
        ("lifecycle_identity", "", "EMPTY_STRING"),
        ("time_domain", "", "EMPTY_STRING"),
        ("epoch", True, "BOOL_AS_INT"),
        ("generation", False, "BOOL_AS_INT"),
        ("cutoff_time_ns", True, "BOOL_AS_INT"),
        ("action_barrier_time_ns", True, "BOOL_AS_INT"),
        ("reset_barrier_time_ns", True, "BOOL_AS_INT"),
        ("epoch", -1, "NEGATIVE_VALUE"),
        ("generation", -1, "NEGATIVE_VALUE"),
        ("cutoff_time_ns", -1, "NEGATIVE_VALUE"),
        ("action_barrier_time_ns", -1, "NEGATIVE_VALUE"),
        ("reset_barrier_time_ns", -1, "NEGATIVE_VALUE"),
        ("lifecycle_identity", 3, "WRONG_TYPE"),
        ("time_domain", str(""), "EMPTY_STRING"),
        ("epoch", 1.0, "WRONG_TYPE"),
    ],
)
def test_cutoff_construction_failures_are_typed(
    field_name: str,
    bad_value: object,
    reason: str,
) -> None:
    detail = _construction_detail(lambda: _valid_cutoff(**{field_name: bad_value}))
    assert detail.reason == reason
    assert detail.field_name == field_name


def test_integer_and_string_subclasses_are_rejected_without_coercion() -> None:
    class IntSubclass(int):
        pass

    class StrSubclass(str):
        pass

    integer_fields = (
        "epoch",
        "generation",
        "cutoff_time_ns",
        "action_barrier_time_ns",
        "reset_barrier_time_ns",
    )
    string_fields = ("lifecycle_identity", "time_domain")
    for field_name in integer_fields:
        detail = _construction_detail(lambda: _valid_cutoff(**{field_name: IntSubclass(1)}))
        assert detail.reason == "WRONG_TYPE"
        assert detail.field_name == field_name
    for field_name in string_fields:
        detail = _construction_detail(
            lambda: _valid_cutoff(**{field_name: StrSubclass("value")})
        )
        assert detail.reason == "WRONG_TYPE"
        assert detail.field_name == field_name

    for field_name, bad_value in (
        ("epoch", 1.0),
        ("generation", "1"),
        ("cutoff_time_ns", 12.0),
        ("action_barrier_time_ns", object()),
        ("reset_barrier_time_ns", None),
    ):
        detail = _construction_detail(lambda: _valid_cutoff(**{field_name: bad_value}))
        assert detail.reason == "WRONG_TYPE"
        assert detail.field_name == field_name


@pytest.mark.parametrize(
    ("field_name", "bad_value", "reason"),
    [
        ("contract_id", "", "EMPTY_STRING"),
        ("contract_sha256", "", "EMPTY_STRING"),
        ("contract_id", 3, "WRONG_TYPE"),
        ("contract_sha256", b"sha", "WRONG_TYPE"),
    ],
)
def test_reference_fields_require_nonempty_exact_strings(
    field_name: str,
    bad_value: object,
    reason: str,
) -> None:
    values: dict[str, object] = {"contract_id": "id", "contract_sha256": "sha"}
    values[field_name] = bad_value
    detail = _construction_detail(lambda: ContractReferenceV3(**values))
    assert detail.reason == reason
    assert detail.field_name == field_name


def test_reference_and_input_contract_exact_pair_validation() -> None:
    valid = _valid_input_contract()
    assert valid.s2_provenance_reference == ContractReferenceV3(
        contract_id=S2_ID,
        contract_sha256=S2_SHA,
    )

    mismatched_pairs = (
        (
            "s2_provenance_reference",
            ContractReferenceV3(contract_id="alias", contract_sha256=S2_SHA),
        ),
        (
            "s2_provenance_reference",
            ContractReferenceV3(contract_id=S2_ID, contract_sha256="wrong-sha"),
        ),
        (
            "receipt_interface_reference",
            ContractReferenceV3(contract_id="alias", contract_sha256=RECEIPT_SHA),
        ),
        (
            "receipt_interface_reference",
            ContractReferenceV3(contract_id=RECEIPT_ID, contract_sha256="wrong-sha"),
        ),
    )
    for reference_field, mismatched_reference in mismatched_pairs:
        detail = _mapped_detail(
            lambda: _valid_input_contract(**{reference_field: mismatched_reference})
        )
        assert detail.status == "LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY"
        assert detail.failure_kind == "CONTRACT_REFERENCE_MISMATCH"
        assert detail.field_name == reference_field


def test_input_contract_rejects_wrong_reference_type() -> None:
    detail = _construction_detail(
        lambda: _valid_input_contract(s2_provenance_reference="not-a-reference")
    )
    assert detail.reason == "WRONG_TYPE"
    assert detail.field_name == "s2_provenance_reference"


def test_missing_and_unknown_constructor_fields_are_typed() -> None:
    detail = _construction_detail(
        lambda: ObservationCutoffV3(
            lifecycle_identity="id",
            epoch=0,
            generation=0,
            time_domain="domain",
            cutoff_time_ns=12,
            action_barrier_time_ns=10,
        )
    )
    assert detail.reason == "MISSING_FIELD"
    assert detail.field_name == "reset_barrier_time_ns"

    detail = _construction_detail(lambda: _valid_cutoff(unrecognized=1))
    assert detail.reason == "UNKNOWN_FIELD"
    assert detail.field_name is None


@pytest.mark.parametrize(
    ("model", "valid_values", "required_field"),
    [
        *[
            (ObservationCutoffV3, {
                "lifecycle_identity": "lifecycle-opaque",
                "epoch": 0,
                "generation": 0,
                "time_domain": "profile-ros-time",
                "cutoff_time_ns": 12,
                "action_barrier_time_ns": 10,
                "reset_barrier_time_ns": 11,
            }, field_name)
            for field_name in ObservationCutoffV3._SCHEMA_FIELDS
        ],
        *[
            (ContractReferenceV3, {"contract_id": "id", "contract_sha256": "sha"}, field_name)
            for field_name in ContractReferenceV3._SCHEMA_FIELDS
        ],
        *[
            (ObservationInputContractV3, {
                "s2_provenance_reference": ContractReferenceV3(
                    contract_id=S2_ID, contract_sha256=S2_SHA
                ),
                "receipt_interface_reference": ContractReferenceV3(
                    contract_id=RECEIPT_ID, contract_sha256=RECEIPT_SHA
                ),
            }, field_name)
            for field_name in ObservationInputContractV3._SCHEMA_FIELDS
        ],
    ],
)
def test_each_required_constructor_field_missing_is_typed(
    model: type[object],
    valid_values: dict[str, object],
    required_field: str,
) -> None:
    supplied = dict(valid_values)
    del supplied[required_field]

    detail = _construction_detail(lambda: model(**supplied))
    assert detail.reason == "MISSING_FIELD"
    assert detail.field_name == required_field


@pytest.mark.parametrize(
    ("model", "valid_values", "required_field"),
    [
        *[
            (ObservationCutoffV3, {
                "lifecycle_identity": "lifecycle-opaque",
                "epoch": 0,
                "generation": 0,
                "time_domain": "profile-ros-time",
                "cutoff_time_ns": 12,
                "action_barrier_time_ns": 10,
                "reset_barrier_time_ns": 11,
            }, field_name)
            for field_name in ObservationCutoffV3._SCHEMA_FIELDS
        ],
        *[
            (ContractReferenceV3, {"contract_id": "id", "contract_sha256": "sha"}, field_name)
            for field_name in ContractReferenceV3._SCHEMA_FIELDS
        ],
        *[
            (ObservationInputContractV3, {
                "s2_provenance_reference": ContractReferenceV3(
                    contract_id=S2_ID, contract_sha256=S2_SHA
                ),
                "receipt_interface_reference": ContractReferenceV3(
                    contract_id=RECEIPT_ID, contract_sha256=RECEIPT_SHA
                ),
            }, field_name)
            for field_name in ObservationInputContractV3._SCHEMA_FIELDS
        ],
    ],
)
def test_unknown_argument_is_typed_for_each_primitive_and_required_field(
    model: type[object],
    valid_values: dict[str, object],
    required_field: str,
) -> None:
    supplied = dict(valid_values)
    supplied[f"{required_field}__unexpected"] = object()

    detail = _construction_detail(lambda: model(**supplied))
    assert detail.reason == "UNKNOWN_FIELD"
    assert detail.field_name is None
    assert not hasattr(detail, "status")


@pytest.mark.parametrize(
    ("model", "valid_values", "omitted_field"),
    [
        (ObservationCutoffV3, {
            "lifecycle_identity": "lifecycle-opaque",
            "epoch": 0,
            "generation": 0,
            "time_domain": "profile-ros-time",
            "cutoff_time_ns": 12,
            "action_barrier_time_ns": 10,
            "reset_barrier_time_ns": 11,
        }, "reset_barrier_time_ns"),
        (ContractReferenceV3, {"contract_id": "id", "contract_sha256": "sha"}, "contract_sha256"),
        (ObservationInputContractV3, {
            "s2_provenance_reference": ContractReferenceV3(
                contract_id=S2_ID, contract_sha256=S2_SHA
            ),
            "receipt_interface_reference": ContractReferenceV3(
                contract_id=RECEIPT_ID, contract_sha256=RECEIPT_SHA
            ),
        }, "receipt_interface_reference"),
    ],
)
def test_simultaneous_missing_and_unknown_fields_remain_neutral_for_each_primitive(
    model: type[object],
    valid_values: dict[str, object],
    omitted_field: str,
) -> None:
    supplied = dict(valid_values)
    del supplied[omitted_field]
    supplied["unrecognized"] = object()

    detail = _construction_detail(lambda: model(**supplied))
    assert detail.reason is None
    assert detail.field_name is None
    assert not hasattr(detail, "status")


def test_simultaneous_missing_and_unknown_fields_use_neutral_typed_detail() -> None:
    detail = _construction_detail(
        lambda: ObservationCutoffV3(
            lifecycle_identity="id",
            epoch=0,
            generation=0,
            time_domain="domain",
            cutoff_time_ns=12,
            action_barrier_time_ns=10,
            unrecognized=1,
        )
    )
    assert detail.reason is None
    assert detail.field_name is None


def test_multiple_missing_fields_keep_typed_failure_without_field_precedence() -> None:
    detail = _construction_detail(
        lambda: ObservationCutoffV3(
            lifecycle_identity="id",
            epoch=0,
            time_domain="domain",
            cutoff_time_ns=12,
            action_barrier_time_ns=10,
        )
    )
    assert detail.reason == "MISSING_FIELD"
    assert detail.field_name is None


@pytest.mark.parametrize(
    ("cutoff", "action", "reset"),
    [(10, 10, 9), (9, 10, 8), (10, 8, 10), (9, 8, 10)],
)
def test_cutoff_must_strictly_follow_each_barrier(
    cutoff: int,
    action: int,
    reset: int,
) -> None:
    detail = _mapped_detail(
        lambda: _valid_cutoff(
            cutoff_time_ns=cutoff,
            action_barrier_time_ns=action,
            reset_barrier_time_ns=reset,
        )
    )
    assert detail.status == "CUTOFF_BARRIER_ORDER_NON_READY"
    assert detail.failure_kind == "CUTOFF_BARRIER_ORDER"
    assert detail.field_name is None


def test_barrier_order_does_not_require_order_between_barriers() -> None:
    first = _valid_cutoff(cutoff_time_ns=12, action_barrier_time_ns=10, reset_barrier_time_ns=11)
    second = _valid_cutoff(cutoff_time_ns=12, action_barrier_time_ns=11, reset_barrier_time_ns=10)
    assert first.cutoff_time_ns == second.cutoff_time_ns


def test_primitive_subclasses_are_rejected() -> None:
    class DerivedCutoff(ObservationCutoffV3):
        pass

    detail = _construction_detail(
        lambda: DerivedCutoff(
            lifecycle_identity="id",
            epoch=0,
            generation=0,
            time_domain="domain",
            cutoff_time_ns=2,
            action_barrier_time_ns=0,
            reset_barrier_time_ns=1,
        )
    )
    assert detail.reason == "WRONG_TYPE"
    assert detail.field_name is None


def test_frozen_slots_equality_hash_and_public_error_detail_boundary() -> None:
    values = (
        (_valid_cutoff(), _valid_cutoff(), "epoch"),
        (
            ContractReferenceV3(contract_id="id", contract_sha256="sha"),
            ContractReferenceV3(contract_id="id", contract_sha256="sha"),
            "contract_id",
        ),
        (_valid_input_contract(), _valid_input_contract(), "s2_provenance_reference"),
    )
    for value, equal_value, field_name in values:
        assert value == equal_value
        assert hash(value) == hash(equal_value)
        assert not hasattr(value, "__dict__")
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            setattr(value, field_name, None)

    detail = _mapped_detail(lambda: _valid_cutoff(cutoff_time_ns=10))
    assert not hasattr(detail, "__dict__")
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        detail.status = "changed"  # type: ignore[misc]

    with pytest.raises(GateASchemaValidationError) as captured:
        _valid_cutoff(cutoff_time_ns=10)
    with pytest.raises(AttributeError):
        captured.value.detail = detail  # type: ignore[misc]


def test_error_detail_does_not_retain_raw_input_values() -> None:
    class StrSubclass(str):
        pass

    raw_identity = StrSubclass("sensitive-caller-value")
    detail = _construction_detail(lambda: _valid_cutoff(lifecycle_identity=raw_identity))
    assert detail.reason == "WRONG_TYPE"
    assert "sensitive-caller-value" not in repr(detail)


def test_import_is_pure_python_and_does_not_load_ros_modules() -> None:
    module_name = "mecanum_nav_rl.core.v3_observation_contracts"
    module = sys.modules[module_name]
    assert module.__name__ == module_name
    assert not any(
        name == "rclpy" or name.startswith("rclpy.") or name.startswith("mecanum_nav_rl_interfaces")
        for name in sys.modules
    )
    assert all(
        item.__class__.__module__ != "rclpy"
        for item in vars(module).values()
        if item is not None
    )

    source_path = (
        Path(__file__).parents[1]
        / "mecanum_nav_rl"
        / "core"
        / "v3_observation_contracts.py"
    )
    syntax_tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0]
        for node in ast.walk(syntax_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if isinstance(node, ast.Import) else [None])
    }
    assert imported_modules == {"__future__", "dataclasses", "typing"}

    def call_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            prefix = call_name(node.value)
            return f"{prefix}.{node.attr}" if prefix else None
        return None

    import_time_calls: set[str | None] = set()
    def collect_definition_time_calls(node: ast.stmt) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            expressions = [
                *node.decorator_list,
                *node.args.defaults,
                *(default for default in node.args.kw_defaults if default is not None),
            ]
        elif isinstance(node, ast.ClassDef):
            expressions = [*node.decorator_list, *node.bases, *node.keywords]
            for child in node.body:
                collect_definition_time_calls(child)
        else:
            expressions = [node]
        for expression in expressions:
            import_time_calls.update(
                call_name(call.func)
                for call in ast.walk(expression)
                if isinstance(call, ast.Call)
            )

    for node in syntax_tree.body:
        collect_definition_time_calls(node)
    assert import_time_calls <= {"dataclass", "frozenset", "_MODEL_FIELDS.update"}
