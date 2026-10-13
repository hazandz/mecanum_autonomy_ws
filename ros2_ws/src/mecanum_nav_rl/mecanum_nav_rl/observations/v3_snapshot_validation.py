"""Strict validation for typed Observation V3 inputs; no runtime adapters."""

from dataclasses import dataclass

from .v3_snapshot_types import (
    BASE_FRAME,
    FRAME_TF_CONTRACT_ID,
    LIDAR_CONTRACT_ID,
    LIDAR_FRAME,
    LIFECYCLE_BARRIER_CONTRACT_ID,
    LOCAL_REFERENCE_CONTRACT_ID,
    MEASURED_TWIST_CONTRACT_ID,
    ActiveLifecycleConfigContext,
    FinalIssuedReceiptContext,
    LidarSnapshot,
    LocalReferenceSnapshot,
    MeasuredTwistSnapshot,
)


@dataclass(frozen=True, slots=True)
class FixtureBindingClaims:
    """Optional exact expectations supplied by an isolated test fixture."""

    lidar_topic: str | None = None
    lidar_type: str | None = None
    local_reference_topic: str | None = None
    local_reference_type: str | None = None
    measured_twist_topic: str | None = None
    measured_twist_type: str | None = None
    receipt_topic: str | None = None
    receipt_type: str | None = None

    def __post_init__(self):
        for name in self.__slots__:
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value):
                raise TypeError(f"{name} must be None or a non-empty exact str")


@dataclass(frozen=True, slots=True)
class ValidatedObservationInputs:
    """Validation token consumed by the pure-core assembler."""

    context: ActiveLifecycleConfigContext
    lidar: LidarSnapshot
    local_reference: LocalReferenceSnapshot
    measured_twist: MeasuredTwistSnapshot
    receipt: FinalIssuedReceiptContext
    fixture_claims: FixtureBindingClaims | None


def _claims_match(actual, expected):
    if actual is None and expected is None:
        return True
    return type(actual) is str and type(expected) is str and actual == expected


def _snapshot_matches_context(snapshot, context):
    return (
        snapshot.episode_generation == context.episode_generation
        and snapshot.reset_epoch == context.reset_epoch
        and snapshot.runtime_generation == context.runtime_generation
        and snapshot.config_hash == context.config_hash
    )


def validate_observation_inputs(*, context, lidar, local_reference, measured_twist,
                                receipt, fixture_claims=None):
    """Return a complete validation token, or None; never coerce or partially accept."""
    if type(context) is not ActiveLifecycleConfigContext:
        return None
    if context.contract_id != LIFECYCLE_BARRIER_CONTRACT_ID:
        return None
    expected_types = (LidarSnapshot, LocalReferenceSnapshot, MeasuredTwistSnapshot,
                      FinalIssuedReceiptContext)
    values = (lidar, local_reference, measured_twist, receipt)
    if any(type(value) is not expected for value, expected in zip(values, expected_types)):
        return None
    if fixture_claims is not None and type(fixture_claims) is not FixtureBindingClaims:
        return None
    claims = fixture_claims if fixture_claims is not None else FixtureBindingClaims()

    expected_contracts = (LIDAR_CONTRACT_ID, LOCAL_REFERENCE_CONTRACT_ID,
                          MEASURED_TWIST_CONTRACT_ID, LIFECYCLE_BARRIER_CONTRACT_ID)
    if any(value.contract_id != expected for value, expected in zip(values, expected_contracts)):
        return None
    if any(value.frame_contract_id != FRAME_TF_CONTRACT_ID for value in values):
        return None
    if any(not _snapshot_matches_context(value, context) for value in values):
        return None
    if lidar.frame_id != LIDAR_FRAME:
        return None
    if (local_reference.frame_id != BASE_FRAME or measured_twist.frame_id != BASE_FRAME
            or receipt.frame_id != BASE_FRAME):
        return None

    actual_expected_pairs = (
        (lidar.topic_claim, claims.lidar_topic), (lidar.type_claim, claims.lidar_type),
        (local_reference.topic_claim, claims.local_reference_topic),
        (local_reference.type_claim, claims.local_reference_type),
        (measured_twist.topic_claim, claims.measured_twist_topic),
        (measured_twist.type_claim, claims.measured_twist_type),
        (receipt.topic_claim, claims.receipt_topic), (receipt.type_claim, claims.receipt_type),
    )
    if any(not _claims_match(actual, expected) for actual, expected in actual_expected_pairs):
        return None

    return ValidatedObservationInputs(context, lidar, local_reference, measured_twist,
                                      receipt, fixture_claims)


def revalidate_inputs(inputs):
    """Recheck even a manually constructed token before any assembly."""
    if type(inputs) is not ValidatedObservationInputs:
        return None
    return validate_observation_inputs(
        context=inputs.context,
        lidar=inputs.lidar,
        local_reference=inputs.local_reference,
        measured_twist=inputs.measured_twist,
        receipt=inputs.receipt,
        fixture_claims=inputs.fixture_claims,
    )
