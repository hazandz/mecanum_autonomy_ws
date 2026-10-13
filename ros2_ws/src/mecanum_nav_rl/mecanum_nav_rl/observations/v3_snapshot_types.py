"""Immutable, dependency-free value types for the bounded Observation V3 seam."""

from dataclasses import dataclass
import math
import re


LIDAR_CONTRACT_ID = "mecanum.observation.lidar-snapshot/v3"
LOCAL_REFERENCE_CONTRACT_ID = "mecanum.observation.local-reference/v3"
MEASURED_TWIST_CONTRACT_ID = "mecanum.observation.measured-twist/v3"
FRAME_TF_CONTRACT_ID = "mecanum.observation.frame-tf-binding/v3"
LIFECYCLE_BARRIER_CONTRACT_ID = "mecanum.observation.lifecycle-barrier/v3"

LIDAR_FRAME = "lidar_frame"
BASE_FRAME = "base_link"
_CONFIG_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")


def _identity_fields(contract_id, episode_generation, reset_epoch, runtime_generation, config_hash):
    if type(contract_id) is not str or not contract_id:
        raise TypeError("contract_id must be a non-empty exact str")
    if type(episode_generation) is not int or not 0 <= episode_generation < 2**64:
        raise TypeError("episode_generation must be an exact uint64-compatible int")
    for name, value in (("reset_epoch", reset_epoch), ("runtime_generation", runtime_generation)):
        if type(value) is not int or not 0 <= value < 2**32:
            raise TypeError(f"{name} must be an exact uint32-compatible int")
    if type(config_hash) is not str or _CONFIG_HASH_RE.fullmatch(config_hash) is None:
        raise ValueError("config_hash must be 64 lowercase hexadecimal characters")


def _frame(value):
    if type(value) is not str or not value:
        raise TypeError("frame_id must be a non-empty exact str")


def _optional_claim(name, value):
    if value is not None and (type(value) is not str or not value):
        raise TypeError(f"{name} must be None or a non-empty exact str")


def _float_tuple(name, values, length):
    if type(values) is not tuple or len(values) != length:
        raise TypeError(f"{name} must be an immutable tuple of length {length}")
    for value in values:
        if type(value) is not float or not math.isfinite(value):
            raise TypeError(f"{name} values must be finite exact floats")


@dataclass(frozen=True, slots=True)
class ActiveLifecycleConfigContext:
    contract_id: str
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str

    def __post_init__(self):
        _identity_fields(self.contract_id, self.episode_generation, self.reset_epoch,
                         self.runtime_generation, self.config_hash)


@dataclass(frozen=True, slots=True)
class LidarSnapshot:
    contract_id: str
    frame_contract_id: str
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str
    frame_id: str
    sectors: tuple[float, ...]
    topic_claim: str | None = None
    type_claim: str | None = None

    def __post_init__(self):
        _identity_fields(self.contract_id, self.episode_generation, self.reset_epoch,
                         self.runtime_generation, self.config_hash)
        _frame(self.frame_contract_id)
        _frame(self.frame_id)
        _float_tuple("sectors", self.sectors, 72)
        _optional_claim("topic_claim", self.topic_claim)
        _optional_claim("type_claim", self.type_claim)


@dataclass(frozen=True, slots=True)
class LocalReferenceSnapshot:
    contract_id: str
    frame_contract_id: str
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str
    frame_id: str
    features: tuple[float, float, float]
    topic_claim: str | None = None
    type_claim: str | None = None

    def __post_init__(self):
        _identity_fields(self.contract_id, self.episode_generation, self.reset_epoch,
                         self.runtime_generation, self.config_hash)
        _frame(self.frame_contract_id)
        _frame(self.frame_id)
        _float_tuple("features", self.features, 3)
        _optional_claim("topic_claim", self.topic_claim)
        _optional_claim("type_claim", self.type_claim)


@dataclass(frozen=True, slots=True)
class MeasuredTwistSnapshot:
    contract_id: str
    frame_contract_id: str
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str
    frame_id: str
    components: tuple[float, float, float]
    topic_claim: str | None = None
    type_claim: str | None = None

    def __post_init__(self):
        _identity_fields(self.contract_id, self.episode_generation, self.reset_epoch,
                         self.runtime_generation, self.config_hash)
        _frame(self.frame_contract_id)
        _frame(self.frame_id)
        _float_tuple("components", self.components, 3)
        _optional_claim("topic_claim", self.topic_claim)
        _optional_claim("type_claim", self.type_claim)


@dataclass(frozen=True, slots=True)
class FinalIssuedReceiptContext:
    """Already-admitted receipt facts; not a receipt message or transport model."""

    contract_id: str
    frame_contract_id: str
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str
    frame_id: str
    final_command: tuple[float, float, float]
    topic_claim: str | None = None
    type_claim: str | None = None

    def __post_init__(self):
        _identity_fields(self.contract_id, self.episode_generation, self.reset_epoch,
                         self.runtime_generation, self.config_hash)
        _frame(self.frame_contract_id)
        _frame(self.frame_id)
        _float_tuple("final_command", self.final_command, 3)
        _optional_claim("topic_claim", self.topic_claim)
        _optional_claim("type_claim", self.type_claim)
