"""Pure-Python structural primitives for the constrained WP-04 Gate A scope.

This module deliberately performs no I/O, clock access, repository lookup, or
ROS/runtime initialization.  Contract references are compared as supplied;
they are never resolved by reading external artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


_S2_CONTRACT_ID = "mecanum.snapshot-synchronization-temporal/v1"
_S2_CONTRACT_SHA256 = "1be31c1915fedd86f269cee5214d794da0899a0d69dbb0ba5392e619813d4a8f"
_RECEIPT_CONTRACT_ID = "mecanum.final-issued-receipt/v2"
_RECEIPT_CONTRACT_SHA256 = "0c6446674bf17373ec646519043f506a9a7a15f95d5fdd10829b0cedb956500a"

_CUTOFF_STATUS = "CUTOFF_BARRIER_ORDER_NON_READY"
_CONTRACT_STATUS = "LIFECYCLE_OR_CONTRACT_MISMATCH_NON_READY"

_CONSTRUCTION_REASONS = frozenset(
    {
        "MISSING_FIELD",
        "UNKNOWN_FIELD",
        "WRONG_TYPE",
        "BOOL_AS_INT",
        "NEGATIVE_VALUE",
        "EMPTY_STRING",
    }
)


def _validate_field_name(field_name: str | None) -> None:
    if field_name is not None and type(field_name) is not str:
        raise TypeError("field_name must be an exact built-in str or None")


@dataclass(frozen=True, slots=True, kw_only=True)
class GateASchemaMappedFailure:
    """Typed detail for one of the two existing mapped non-ready failures."""

    status: str
    failure_kind: str
    field_name: str | None

    def __post_init__(self) -> None:
        if type(self.status) is not str or type(self.failure_kind) is not str:
            raise TypeError("mapped failure status and failure_kind must be exact str")
        _validate_field_name(self.field_name)
        allowed = {
            (_CUTOFF_STATUS, "CUTOFF_BARRIER_ORDER"),
            (_CONTRACT_STATUS, "CONTRACT_REFERENCE_MISMATCH"),
        }
        if (self.status, self.failure_kind) not in allowed:
            raise ValueError("mapped failure must use an existing Gate A status mapping")


@dataclass(frozen=True, slots=True, kw_only=True)
class GateASchemaConstructionFailure:
    """Typed detail for a construction failure, with no ACR8 status member."""

    reason: str
    field_name: str | None

    def __post_init__(self) -> None:
        if type(self.reason) is not str or self.reason not in _CONSTRUCTION_REASONS:
            raise ValueError("reason must be an approved diagnostic-only construction label")
        _validate_field_name(self.field_name)


class GateASchemaValidationError(Exception):
    """Validation exception whose supported caller surface is its typed detail."""

    __slots__ = ("_detail",)

    def __init__(
        self,
        detail: GateASchemaMappedFailure | GateASchemaConstructionFailure,
    ) -> None:
        if type(detail) not in (GateASchemaMappedFailure, GateASchemaConstructionFailure):
            raise TypeError("detail must be a Gate A typed failure detail")
        Exception.__init__(self)
        object.__setattr__(self, "_detail", detail)

    @property
    def detail(self) -> GateASchemaMappedFailure | GateASchemaConstructionFailure:
        return self._detail

    def __setattr__(self, name: str, value: object) -> None:
        if name in {"detail", "_detail"} and hasattr(self, "_detail"):
            raise AttributeError(f"{name} is read-only after construction")
        super().__setattr__(name, value)


def _raise_construction(reason: str, field_name: str | None) -> None:
    raise GateASchemaValidationError(
        GateASchemaConstructionFailure(reason=reason, field_name=field_name)
    )


def _raise_mapped(
    status: str,
    failure_kind: str,
    field_name: str | None,
) -> None:
    raise GateASchemaValidationError(
        GateASchemaMappedFailure(
            status=status,
            failure_kind=failure_kind,
            field_name=field_name,
        )
    )


_MODEL_FIELDS: dict[type[object], tuple[str, ...]] = {}


class _StrictStructuralValue:
    """Shared call-shape checks without defaults or coercive initialization."""

    __slots__ = ()

    def __new__(cls, *args: object, **kwargs: object) -> _StrictStructuralValue:
        field_names = _MODEL_FIELDS.get(cls)
        if field_names is None:
            _raise_construction("WRONG_TYPE", None)

        # The generated dataclass initializer rejects positional arguments.
        # Their exact TypeError behavior is not part of this public contract.
        if args:
            return object.__new__(cls)

        allowed = set(field_names)
        supplied = set(kwargs)
        unknown = supplied - allowed
        missing = allowed - supplied

        # A simultaneous unknown+missing call has no approved error precedence.
        # Leave that combined call-shape failure to the generated initializer.
        if unknown and missing:
            return object.__new__(cls)
        if unknown:
            _raise_construction("UNKNOWN_FIELD", None)
        if missing:
            field_name = next(iter(missing)) if len(missing) == 1 else None
            _raise_construction("MISSING_FIELD", field_name)
        return object.__new__(cls)


def _expect_exact_str(value: object, field_name: str) -> None:
    if type(value) is not str:
        _raise_construction("WRONG_TYPE", field_name)
    if not value:
        _raise_construction("EMPTY_STRING", field_name)


def _expect_exact_nonnegative_int(value: object, field_name: str) -> None:
    if type(value) is bool:
        _raise_construction("BOOL_AS_INT", field_name)
    if type(value) is not int:
        _raise_construction("WRONG_TYPE", field_name)
    if value < 0:
        _raise_construction("NEGATIVE_VALUE", field_name)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationCutoffV3(_StrictStructuralValue):
    """Caller-supplied cutoff and barrier facts in one profile time domain."""

    lifecycle_identity: str
    epoch: int
    generation: int
    time_domain: str
    cutoff_time_ns: int
    action_barrier_time_ns: int
    reset_barrier_time_ns: int

    _SCHEMA_FIELDS: ClassVar[tuple[str, ...]] = (
        "lifecycle_identity",
        "epoch",
        "generation",
        "time_domain",
        "cutoff_time_ns",
        "action_barrier_time_ns",
        "reset_barrier_time_ns",
    )

    def __post_init__(self) -> None:
        if type(self) is not ObservationCutoffV3:
            _raise_construction("WRONG_TYPE", None)
        _expect_exact_str(self.lifecycle_identity, "lifecycle_identity")
        _expect_exact_nonnegative_int(self.epoch, "epoch")
        _expect_exact_nonnegative_int(self.generation, "generation")
        _expect_exact_str(self.time_domain, "time_domain")
        _expect_exact_nonnegative_int(self.cutoff_time_ns, "cutoff_time_ns")
        _expect_exact_nonnegative_int(self.action_barrier_time_ns, "action_barrier_time_ns")
        _expect_exact_nonnegative_int(self.reset_barrier_time_ns, "reset_barrier_time_ns")
        if (
            self.cutoff_time_ns <= self.action_barrier_time_ns
            or self.cutoff_time_ns <= self.reset_barrier_time_ns
        ):
            _raise_mapped(_CUTOFF_STATUS, "CUTOFF_BARRIER_ORDER", None)


@dataclass(frozen=True, slots=True, kw_only=True)
class ContractReferenceV3(_StrictStructuralValue):
    """Opaque, exact contract ID/SHA pair; it does not resolve external files."""

    contract_id: str
    contract_sha256: str

    _SCHEMA_FIELDS: ClassVar[tuple[str, ...]] = ("contract_id", "contract_sha256")

    def __post_init__(self) -> None:
        if type(self) is not ContractReferenceV3:
            _raise_construction("WRONG_TYPE", None)
        _expect_exact_str(self.contract_id, "contract_id")
        _expect_exact_str(self.contract_sha256, "contract_sha256")


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationInputContractV3(_StrictStructuralValue):
    """Reference-only Gate A input contract for the two selected ID/SHA pairs."""

    s2_provenance_reference: ContractReferenceV3
    receipt_interface_reference: ContractReferenceV3

    _SCHEMA_FIELDS: ClassVar[tuple[str, ...]] = (
        "s2_provenance_reference",
        "receipt_interface_reference",
    )

    def __post_init__(self) -> None:
        if type(self) is not ObservationInputContractV3:
            _raise_construction("WRONG_TYPE", None)

        s2_reference = self.s2_provenance_reference
        if type(s2_reference) is not ContractReferenceV3:
            _raise_construction("WRONG_TYPE", "s2_provenance_reference")
        receipt_reference = self.receipt_interface_reference
        if type(receipt_reference) is not ContractReferenceV3:
            _raise_construction("WRONG_TYPE", "receipt_interface_reference")

        mismatches: list[str] = []
        if (
            s2_reference.contract_id != _S2_CONTRACT_ID
            or s2_reference.contract_sha256 != _S2_CONTRACT_SHA256
        ):
            mismatches.append("s2_provenance_reference")
        if (
            receipt_reference.contract_id != _RECEIPT_CONTRACT_ID
            or receipt_reference.contract_sha256 != _RECEIPT_CONTRACT_SHA256
        ):
            mismatches.append("receipt_interface_reference")
        if mismatches:
            field_name = mismatches[0] if len(mismatches) == 1 else None
            _raise_mapped(
                _CONTRACT_STATUS,
                "CONTRACT_REFERENCE_MISMATCH",
                field_name,
            )


_MODEL_FIELDS.update(
    {
        ObservationCutoffV3: ObservationCutoffV3._SCHEMA_FIELDS,
        ContractReferenceV3: ContractReferenceV3._SCHEMA_FIELDS,
        ObservationInputContractV3: ObservationInputContractV3._SCHEMA_FIELDS,
    }
)


__all__ = [
    "ContractReferenceV3",
    "GateASchemaConstructionFailure",
    "GateASchemaMappedFailure",
    "GateASchemaValidationError",
    "ObservationCutoffV3",
    "ObservationInputContractV3",
]
