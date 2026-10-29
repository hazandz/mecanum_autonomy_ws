"""Pure selection of the final command receipt at an observation cutoff.

The input values are copied scalar views of receipt-v2 and CommandEnvelope
facts.  They are not ROS messages and do not assert actuator acknowledgement.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real
import re
from .lifecycle_types import EpisodeLifecycleIdentity

class ReceiptSource(str, Enum):
    POLICY = 'POLICY'
    NAV2 = 'NAV2'
    TELEOP = 'TELEOP'
    SAFE_STOP = 'SAFE_STOP'

class CutoffStatus(str, Enum):
    READY = 'ready'
    PENDING = 'pending'
    REJECTED = 'rejected'

@dataclass(frozen=True, slots=True)

class ReceiptStreamBinding:
    final_publisher_instance_id: int
    session_id: str
    config_hash: str
    lifecycle: EpisodeLifecycleIdentity

    def __post_init__(self) -> None:
        _uint('final_publisher_instance_id', self.final_publisher_instance_id)
        _nonempty('session_id', self.session_id)
        if type(self.config_hash) is not str or re.fullmatch('[0-9a-f]{64}',
            self.config_hash) is None:
            raise ValueError('config_hash must be a lowercase SHA-256 identity')
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')

@dataclass(frozen=True, slots=True)

class IssuedCommandReceiptView:
    """Copied receipt-v2 values plus separately bound session/config identity."""
    publish_stamp_ns: int
    final_publisher_instance_id: int
    final_publish_sequence: int
    source: ReceiptSource
    source_instance_id: int
    source_sequence: int
    step_index: int
    transition_id: str
    lifecycle: EpisodeLifecycleIdentity
    session_id: str
    ingress_config_hash: str
    final_command: tuple[float, float, float]
    admission_valid: bool = True

    def __post_init__(self) -> None:
        for name in ('publish_stamp_ns', 'final_publisher_instance_id',
            'final_publish_sequence', 'source_instance_id', 'source_sequence', 'step_index'):
            _uint(name, getattr(self, name))
        if self.final_publish_sequence == 0:
            raise ValueError('final_publish_sequence starts at one')
        if not isinstance(self.source, ReceiptSource):
            raise TypeError('source must be ReceiptSource')
        if type(self.admission_valid) is not bool:
            raise TypeError('admission_valid must be bool')
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')
        _nonempty('session_id', self.session_id)
        _nonempty('transition_id', self.transition_id)
        if len(self.transition_id) > 36 or self.step_index == 0:
            raise ValueError('transition identity must fit receipt-v2')
        if type(self.ingress_config_hash) is not str or re.fullmatch('[0-9a-f]{64}', self.ingress_config_hash) is None:
            raise ValueError('ingress_config_hash must be a lowercase SHA-256')
        if type(self.final_command) is not tuple or len(self.final_command) != 3:
            raise TypeError('final_command must be a three-value tuple')
        copied = tuple((_finite(name, value) for name, value in zip(('vx',
            'vy', 'wz'), self.final_command, strict=True)))
        object.__setattr__(self, 'final_command', copied)

    @property
    def receipt_key(self) -> str:
        """Stable scalar identity composed only from existing receipt-v2 fields."""
        return f'{self.final_publisher_instance_id}:{self.final_publish_sequence}'

@dataclass(frozen=True, slots=True)

class PolicyActionIssuance:
    """Proof key that this step's POLICY candidate reached final publication."""
    source_instance_id: int
    source_sequence: int
    lifecycle: EpisodeLifecycleIdentity
    step_index: int
    transition_id: str

    def __post_init__(self) -> None:
        _uint('source_instance_id', self.source_instance_id)
        _uint('source_sequence', self.source_sequence)
        _uint('step_index', self.step_index)
        if self.step_index == 0 or type(self.transition_id) is not str or (not self.transition_id) or (len(self.transition_id) > 36):
            raise ValueError('issuance step identity must fit receipt-v2')
        if not isinstance(self.lifecycle, EpisodeLifecycleIdentity):
            raise TypeError('lifecycle must be EpisodeLifecycleIdentity')

@dataclass(frozen=True, slots=True)

class CutoffSelection:
    status: CutoffStatus
    reason: str | None = None
    receipt: IssuedCommandReceiptView | None = None
    normalized_command: tuple[float, float, float] | None = None
    physical_scales: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CutoffStatus):
            raise TypeError('status must be CutoffStatus')
        if self.status is CutoffStatus.READY:
            if self.receipt is None or self.normalized_command is None or self.physical_scales is None:
                raise ValueError('ready selection requires a receipt and command')
            if type(self.normalized_command) is not tuple or type(self.physical_scales) is not tuple or len(self.normalized_command) != 3 or (len(self.physical_scales) != 3):
                raise ValueError('ready selection requires three axis values')
            for i, (norm, scale,
                physical) in enumerate(zip(self.normalized_command,
                self.physical_scales, self.receipt.final_command, strict=True)):
                n = _finite(f'normalized_command[{i}]', norm)
                s = _positive_finite(f'physical_scales[{i}]', scale)
                if n < -1.0 or n > 1.0 or abs(n * s - physical) > 1e-12:
                    raise ValueError('normalized command must match the selected physical receipt')
        elif self.receipt is not None or self.normalized_command is not None or self.physical_scales is not None:
            raise ValueError('pending/rejected selection cannot carry command data')

def select_final_issued_at_cutoff(receipts: tuple[IssuedCommandReceiptView,
    ...], *, binding: ReceiptStreamBinding, issuance: PolicyActionIssuance, cutoff_ros_ns: int, evaluation_ros_now_ns: int, physical_scales: tuple[float, float, float]) -> CutoffSelection:
    """Select max publish sequence at/before cutoff with its adjacent r_plus.

    Receipt config identity is supplied by ``binding``; receipt-v2 has no
    config-hash field.  Arrival order is ignored, but sequence/stamp rollback,
    conflicting duplicates, and any incompatible item fail closed.
    """
    try:
        _uint('cutoff_ros_ns', cutoff_ros_ns)
        _uint('evaluation_ros_now_ns', evaluation_ros_now_ns)
        if cutoff_ros_ns > evaluation_ros_now_ns:
            raise ValueError('cutoff is future relative to evaluation ROS time')
        if not isinstance(binding, ReceiptStreamBinding):
            raise TypeError('binding must be ReceiptStreamBinding')
        if not isinstance(issuance, PolicyActionIssuance):
            raise TypeError('issuance must be PolicyActionIssuance')
        if issuance.lifecycle != binding.lifecycle:
            raise ValueError('issuance lifecycle does not match stream binding')
        if type(receipts) is not tuple:
            raise TypeError('receipts must be an immutable tuple')
        if type(physical_scales) is not tuple or len(physical_scales) != 3:
            raise TypeError('physical_scales must be a three-value tuple')
        scales = tuple((_positive_finite(f'scale[{i}]', x) for i,
            x in enumerate(physical_scales)))
        by_sequence: dict[int, IssuedCommandReceiptView] = {}
        for receipt in receipts:
            if type(receipt) is not IssuedCommandReceiptView:
                raise TypeError('receipt must be an IssuedCommandReceiptView')
            if receipt.final_publisher_instance_id != binding.final_publisher_instance_id:
                raise ValueError('wrong final publisher instance')
            if receipt.session_id != binding.session_id:
                raise ValueError('wrong session')
            if receipt.ingress_config_hash != binding.config_hash:
                raise ValueError('wrong ingress-bound config identity')
            if receipt.lifecycle != binding.lifecycle:
                raise ValueError('wrong lifecycle identity')
            if not receipt.admission_valid:
                raise ValueError('invalid latest receipt cannot be skipped for fallback')
            prior = by_sequence.get(receipt.final_publish_sequence)
            if prior is not None and prior != receipt:
                raise ValueError('conflicting duplicate final_publish_sequence')
            by_sequence[receipt.final_publish_sequence] = receipt
        ordered = tuple((by_sequence[key] for key in sorted(by_sequence)))
        if any((a.publish_stamp_ns > b.publish_stamp_ns for a,
            b in zip(ordered, ordered[1:]))):
            raise ValueError('receipt publish timestamps rolled back')
        if any((r.publish_stamp_ns > evaluation_ros_now_ns for r in ordered)):
            raise ValueError('receipt has a future timestamp')
        issuance_receipt = next((r for r in ordered if r.source is ReceiptSource.POLICY and r.source_instance_id == issuance.source_instance_id and (r.source_sequence == issuance.source_sequence) and (r.step_index == issuance.step_index) and (r.transition_id == issuance.transition_id) and (r.lifecycle == issuance.lifecycle)), None)
        if issuance_receipt is None:
            raise ValueError('the step has no matching successfully issued POLICY receipt')
        if issuance_receipt.publish_stamp_ns > cutoff_ros_ns:
            raise ValueError('POLICY issuance is after this observation cutoff')
        eligible = tuple((r for r in ordered if r.publish_stamp_ns <= cutoff_ros_ns))
        if not eligible:
            return CutoffSelection(CutoffStatus.PENDING,
                'no receipt at/before cutoff')
        selected = max(eligible, key=lambda r: r.final_publish_sequence)
        if selected.publish_stamp_ns > cutoff_ros_ns:
            raise ValueError('selected receipt is after cutoff')
        adjacent = next((r for r in ordered if r.final_publish_sequence == selected.final_publish_sequence + 1), None)
        if adjacent is None:
            return CutoffSelection(CutoffStatus.PENDING,
                'adjacent trailing receipt is missing')
        if not cutoff_ros_ns < adjacent.publish_stamp_ns <= evaluation_ros_now_ns:
            if adjacent.publish_stamp_ns <= cutoff_ros_ns:
                raise ValueError('receipt sequence gap at cutoff boundary')
            return CutoffSelection(CutoffStatus.PENDING,
                'adjacent receipt is not yet observable')
        normalized = tuple((_normalize_axis(v, s) for v,
            s in zip(selected.final_command, scales, strict=True)))
        return CutoffSelection(CutoffStatus.READY, receipt=selected,
            normalized_command=normalized, physical_scales=scales)
    except (TypeError, ValueError, OverflowError) as error:
        return CutoffSelection(CutoffStatus.REJECTED, reason=str(error))

def _uint(name: str, value: object) -> int:
    if type(value) is not int or value < 0 or value >= 2 ** 64:
        raise ValueError(f'{name} must be an unsigned integer')
    return value

def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value,
        Real) or (not isfinite(float(value))):
        raise ValueError(f'{name} must be finite')
    return float(value)

def _positive_finite(name: str, value: object) -> float:
    result = _finite(name, value)
    if result <= 0:
        raise ValueError(f'{name} must be positive')
    return result

def _normalize_axis(value: float, scale: float) -> float:
    normalized = value / scale
    if not isfinite(normalized) or normalized < -1.0 or normalized > 1.0:
        raise ValueError('final command is outside the physical envelope')
    return normalized

def _nonempty(name: str, value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f'{name} must be a non-empty trimmed string')
__all__ = ('CutoffSelection', 'CutoffStatus', 'IssuedCommandReceiptView',
    'PolicyActionIssuance', 'ReceiptSource', 'ReceiptStreamBinding', 'select_final_issued_at_cutoff')
