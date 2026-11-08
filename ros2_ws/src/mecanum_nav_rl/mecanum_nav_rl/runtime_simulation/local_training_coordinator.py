"""Điều phối control B2.3: request bất biến, ACK thật và deadline chung.

Module này không tạo ROS context hoặc tự cấp runtime authority. Runner sở hữu
node/client, lifecycle, guard và sink; port nhận đúng generated interface.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import time
from typing import Callable

from rclpy.serialization import deserialize_message, serialize_message
from mecanum_nav_rl_interfaces.msg import SafetyLifecycleState
from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort


@dataclass(frozen=True)
class BackendSessionIdentity:
    session_id: str
    config_hash: str
    asset_manifest_sha256: str
    coordinator_ingress_instance_id: int
    backend_instance_id: int

    def __post_init__(self):
        if (not isinstance(self.session_id, str) or not self.session_id
                or self.session_id != self.session_id.strip() or len(self.session_id) > 64):
            raise ValueError('B23 session identity invalid')
        for digest in (self.config_hash, self.asset_manifest_sha256):
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('B23 config/asset digest invalid')
        for value in (self.coordinator_ingress_instance_id, self.backend_instance_id):
            if type(value) is not int or not 0 < value < 2**64:
                raise ValueError('B23 instance identity invalid')


@dataclass(frozen=True)
class BackendControlAck:
    request_bytes: bytes
    response_bytes: bytes
    observed_steady_ns: int

    @property
    def response(self):
        return deserialize_message(self.response_bytes, Control.Response)

    @property
    def request(self):
        return deserialize_message(self.request_bytes, Control.Request)


def lifecycle_request_fields(snapshot: SafetyLifecycleState) -> dict:
    """Sao chép facts nguồn, gồm motion_permitted; không đổi READY thành hold giả."""
    if not isinstance(snapshot, SafetyLifecycleState):
        raise TypeError('actual SafetyLifecycleState is required')
    return {
        'episode_generation': snapshot.episode_generation,
        'reset_epoch': snapshot.reset_epoch,
        'runtime_generation': snapshot.runtime_generation,
        'lifecycle_sequence': snapshot.sequence,
        'primary_state': snapshot.primary_state,
        'barrier_state': snapshot.barrier_state,
        'lifecycle_header_stamp': snapshot.header.stamp,
        'lifecycle_frame_id': snapshot.header.frame_id,
        'barrier_stamp': snapshot.barrier_stamp,
        'motion_permitted': snapshot.motion_permitted,
    }


class BackendControlError(RuntimeError):
    def __init__(self, message: str, ack: BackendControlAck | None = None):
        super().__init__(message)
        self.ack = ack


class BackendControlSession:
    """Một sequence/revision owner cho backend service trong đúng phiên."""

    MUTATION_NS = 1_000_000_000
    POLL_NS = 5_000_000
    _PINNED = frozenset((
        'schema_version', 'coordinator_ingress_instance_id', 'request_sequence',
        'expected_binding_revision', 'expected_backend_instance_id',
        'session_id', 'config_hash', 'asset_manifest_sha256',
    ))

    def __init__(self, port: LocalTrainingBackendControlPort,
                 identity: BackendSessionIdentity, *, emit: Callable[[str, dict], None],
                 now_ns: Callable[[], int] = time.monotonic_ns,
                 pause: Callable = asyncio.sleep):
        if (Control.Request.SCHEMA_VERSION != 2
                or Control.Response.RESPONSE_SCHEMA_VERSION != 2):
            raise ValueError('B23 requires schema 2 at both control endpoints')
        if not isinstance(identity, BackendSessionIdentity) or not callable(emit):
            raise TypeError('B23 identity/evidence sink required')
        self.identity = identity
        self._port, self._emit = port, emit
        self._now_ns, self._pause = now_ns, pause
        self._sequence = 0
        self._revision = 0
        self._last_clock_ns = -1
        self._faulted = False
        self._lock = asyncio.Lock()
        self._futures = []
        self._active_task = None
        self.evidence_errors = []

    @property
    def revision(self):
        return self._revision

    @property
    def owned_calls(self):
        return tuple(self._futures)

    def _now(self):
        now = self._now_ns()
        if type(now) is not int or now < 0 or now < self._last_clock_ns:
            self._faulted = True
            raise BackendControlError('control monotonic clock invalid')
        self._last_clock_ns = now
        return now

    async def _bounded_pause(self, deadline):
        before = self._now()
        remaining = deadline - before
        if remaining <= 0:
            raise TimeoutError('backend control deadline expired')
        await self._pause(min(self.POLL_NS, remaining) / 1_000_000_000)
        if self._now() <= before:
            raise BackendControlError('control pause did not advance monotonic clock')

    def _request_bytes(self, operation, fields):
        if self._PINNED.intersection(fields):
            raise ValueError('cannot override pinned backend identity/revision')
        request = Control.Request()
        request.schema_version = request.SCHEMA_VERSION
        request.operation = operation
        request.coordinator_ingress_instance_id = self.identity.coordinator_ingress_instance_id
        request.expected_backend_instance_id = self.identity.backend_instance_id
        request.session_id = self.identity.session_id
        request.config_hash = self.identity.config_hash
        request.asset_manifest_sha256 = self.identity.asset_manifest_sha256
        request.request_sequence = self._sequence + 1
        request.expected_binding_revision = self._revision
        known = request.get_fields_and_field_types()
        for key, value in fields.items():
            if key not in known:
                raise ValueError('unknown backend request field: ' + key)
            setattr(request, key, value)
        raw = serialize_message(request)
        self._sequence += 1
        return raw

    async def transact(self, operation: int, *, deadline_ns: int, **fields) -> BackendControlAck:
        if type(deadline_ns) is not int:
            raise TypeError('backend control deadline must be monotonic integer nanoseconds')
        async with self._lock:
            if self._faulted and operation != Control.Request.OP_INHIBIT:
                raise BackendControlError('backend session already uncertain/faulted')
            start = self._now()
            deadline = min(deadline_ns, start + self.MUTATION_NS)
            if deadline <= start:
                raise TimeoutError('backend control deadline expired before submit')
            raw = self._request_bytes(operation, fields)
            request = deserialize_message(raw, Control.Request)
            self._active_task = asyncio.current_task()
            try:
                self._emit('CONTROL_REQUEST', {'request_sequence': request.request_sequence,
                           'operation': operation, 'request_cdr_hex': raw.hex(),
                           'request_sha256': hashlib.sha256(raw).hexdigest(),
                           'started_ns': start, 'deadline_ns': deadline})
                while self._now() < deadline:
                    # Mỗi lần gửi lấy lại cùng bytes: QUEUED không tạo request/actor mới.
                    future = self._port.submit(deserialize_message(raw, Control.Request))
                    self._futures.append(future)
                    while not future.done():
                        await self._bounded_pause(deadline)
                    observed = self._now()
                    if observed >= deadline:
                        raise TimeoutError('backend ACK observed after deadline')
                    try:
                        response = future.result()
                    finally:
                        self._futures.remove(future)
                    if not isinstance(response, Control.Response):
                        raise BackendControlError('backend ACK missing/generated type mismatch')
                    ack = BackendControlAck(raw, serialize_message(response), observed)
                    self._emit('CONTROL_RESPONSE', {'request_sequence': request.request_sequence,
                               'observed_ns': observed, 'response_cdr_hex': ack.response_bytes.hex(),
                               'result': response.result, 'reason': response.reason_code})
                    if (response.schema_version != response.RESPONSE_SCHEMA_VERSION
                            or response.request_sequence != request.request_sequence
                            or response.backend_instance_id != self.identity.backend_instance_id):
                        raise BackendControlError('backend ACK identity/schema mismatch', ack)
                    if response.result == response.RESULT_QUEUED:
                        if response.reason_code != response.REASON_NONE or any(response.pending_admission_token):
                            raise BackendControlError('QUEUED ACK contains reason or admission token', ack)
                        await self._bounded_pause(deadline)
                        continue
                    if response.result != response.RESULT_APPLIED or response.reason_code != response.REASON_NONE:
                        raise BackendControlError('backend control rejected: ' + str(response.reason_code), ack)
                    mutates = operation != Control.Request.OP_VERIFY_CONTACT_CAPABILITY
                    expected = request.expected_binding_revision + int(mutates)
                    if (response.binding_revision != expected
                            or response.applied_binding_revision != expected
                            or response.applied_physics_iteration == 0
                            or response.applied_sim_stamp.sec < 0
                            or not 0 <= response.applied_sim_stamp.nanosec < 1_000_000_000):
                        raise BackendControlError('backend APPLIED revision/application fact invalid', ack)
                    token = bytes(response.pending_admission_token)
                    if operation == Control.Request.OP_BIND_PENDING_STEP and not any(token):
                        raise BackendControlError('pending step APPLIED without admission token', ack)
                    if operation != Control.Request.OP_BIND_PENDING_STEP and any(token):
                        raise BackendControlError('non-pending ACK carries admission token', ack)
                    self._revision = response.applied_binding_revision
                    self._emit('ACK_OBSERVED', {'request_sequence': request.request_sequence,
                               'revision': self._revision, 'observed_ns': observed,
                               'admission_token_hex': token.hex()})
                    return ack
                raise TimeoutError('backend control mutation did not apply within deadline')
            except BaseException as error:
                self._faulted = True
                try:
                    self._emit('CONTROL_UNCERTAIN', {'request_sequence': request.request_sequence,
                               'at_ns': self._now_ns(), 'error': type(error).__name__, 'detail': str(error)})
                except BaseException as sink_error:
                    self.evidence_errors.append(repr(sink_error))
                raise
            finally:
                self._active_task = None
                self._futures[:] = [call for call in self._futures if not call.done()]

    async def inhibit(self, *, deadline_ns: int) -> BackendControlAck:
        """Dừng transaction chờ ở client rồi gửi INHIBIT; không đợi hết 1 s mutation.

        Cancel client không chứng minh server đã hủy mutation: chỉ ACK INHIBIT
        từ native mới là fact đóng quyền. Call chưa xong vẫn thuộc session.
        """
        self._faulted = True
        active = self._active_task
        if active is not None and active is not asyncio.current_task():
            active.cancel()
            while not active.done():
                await self._bounded_pause(deadline_ns)
        return await self.transact(Control.Request.OP_INHIBIT, deadline_ns=deadline_ns)

    def cancel_pending_calls(self):
        """Thu hồi future local sau khi ingress đã đóng; không coi đây là backend ACK."""
        for future in tuple(self._futures):
            if not future.done():
                future.cancel()
        self._futures[:] = [future for future in self._futures if not future.done()]
