"""Isolated ROS/Gazebo worker for bounded B2 server scene readiness.

The parent communicates only through a bounded JSON-lines protocol. Middleware
imports and participants are created only by :func:`main`, never at import.
"""
from __future__ import annotations

import gc
import hashlib
import json
import os
import signal
import sys
import time
import uuid


REQUEST_SCHEMA = 'mecanum_b2_scene_readiness_request/v1'
EVENT_SCHEMA = 'mecanum_b2_scene_readiness_event/v1'
MAX_REQUEST_BYTES = 16 * 1024
MAX_RECORD_BYTES = 4 * 1024
MAX_STDOUT_BYTES = 64 * 1024
MAX_STDERR_BYTES = 64 * 1024
REQUEST_FIELDS = {
    'schema_id', 'request_id', 'session_id', 'config_hash',
    'asset_manifest_sha256', 'coordinator_ingress_instance_id',
    'world_id', 'model_id', 'gz_partition', 'ros_domain_id',
    'deadline_monotonic_ns',
}
EVENTS = {
    'worker_started', 'status_wait_started', 'status_matched',
    'scene_query_started', 'scene_query_finished', 'worker_result',
}


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f'invalid JSON constant: {value}')


def strict_json_loads(data: bytes):
    """Parse one bounded UTF-8 request and reject ambiguous JSON."""
    if len(data) > MAX_REQUEST_BYTES:
        raise ValueError('readiness request exceeds 16 KiB')
    text = data.decode('utf-8', errors='strict')
    return json.loads(
        text, object_pairs_hook=_pairs_no_duplicates,
        parse_constant=_reject_constant,
    )


def validate_request(request, environ):
    """Validate request fields and exact process environment bindings."""
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise ValueError('readiness request schema fields mismatch')
    if request['schema_id'] != REQUEST_SCHEMA:
        raise ValueError('readiness request schema mismatch')
    for field in ('request_id', 'session_id'):
        value = request[field]
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError(f'{field} must be canonical UUID')
    for field in ('config_hash', 'asset_manifest_sha256'):
        value = request[field]
        if (not isinstance(value, str) or len(value) != 64
                or any(c not in '0123456789abcdef' for c in value)):
            raise ValueError(f'{field} must be lowercase SHA-256')
    coordinator = request['coordinator_ingress_instance_id']
    if type(coordinator) is not int or not 0 < coordinator < 2**64:
        raise ValueError('coordinator identity must be nonzero uint64')
    deadline = request['deadline_monotonic_ns']
    if type(deadline) is not int or deadline <= 0:
        raise ValueError('deadline must be positive monotonic nanoseconds')
    if request['world_id'] != 'b2_training_arena':
        raise ValueError('unexpected world binding')
    if request['model_id'] != 'mecanum_b2':
        raise ValueError('unexpected model binding')
    if not isinstance(request['gz_partition'], str) or not request[
        'gz_partition'
    ]:
        raise ValueError('missing Gazebo partition binding')
    domain = request['ros_domain_id']
    if not isinstance(domain, str) or not domain.isdecimal():
        raise ValueError('ROS domain must be decimal text')
    if environ.get('GZ_PARTITION') != request['gz_partition']:
        raise ValueError('Gazebo partition does not match request')
    if environ.get('ROS_DOMAIN_ID') != domain:
        raise ValueError('ROS domain does not match request')
    return request


def canonical_request_bytes(request):
    """Serialize a request with the protocol's stable canonical encoding."""
    data = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')
    if len(data) > MAX_REQUEST_BYTES:
        raise ValueError('readiness request exceeds 16 KiB')
    return data


def _status_facts(message):
    return {
        'world_id': message.header.frame_id,
        'session_id': message.session_id,
        'config_hash': message.config_hash,
        'backend_instance_id': int(message.backend_instance_id),
        'status_sequence': int(message.status_sequence),
        'fault_flags': int(message.fault_flags),
        'actuator_inhibited': bool(message.actuator_inhibited),
    }


def _matches_status(message, request):
    return (
        message.header.frame_id == request['world_id']
        and message.session_id == request['session_id']
        and message.config_hash == request['config_hash']
        and type(message.backend_instance_id) is int
        and message.backend_instance_id > 0
        and type(message.status_sequence) is int
        and message.status_sequence > 0
        and message.fault_flags == 0
        and message.actuator_inhibited is True
    )


def _scene_facts(scene, request):
    if scene is None:
        return {'world_name': None, 'matching_model_count': 0}
    stack = list(scene.model)
    matching = 0
    while stack:
        model = stack.pop()
        if model.name == request['model_id']:
            matching += 1
        stack.extend(model.model)
    return {'world_name': scene.name, 'matching_model_count': matching}


class _ProtocolEmitter:
    def __init__(self, fd, request_id, request_sha256):
        self._stream = os.fdopen(fd, 'w', encoding='utf-8', buffering=1)
        self._request_id = request_id
        self._request_sha256 = request_sha256
        self._sequence = 0
        self._bytes = 0
        self._result_seen = False

    def emit(self, event, facts):
        if event not in EVENTS or self._result_seen:
            raise RuntimeError('invalid readiness protocol transition')
        self._sequence += 1
        record = {
            'schema_id': EVENT_SCHEMA,
            'request_id': self._request_id,
            'request_sha256': self._request_sha256,
            'sequence': self._sequence,
            'event': event,
            'monotonic_ns': time.monotonic_ns(),
            'facts': facts,
        }
        line = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
            allow_nan=False,
        ).encode('utf-8') + b'\n'
        if len(line) > MAX_RECORD_BYTES:
            raise RuntimeError('readiness event exceeds 4 KiB')
        self._bytes += len(line)
        if self._bytes > MAX_STDOUT_BYTES:
            raise RuntimeError('readiness protocol exceeds 64 KiB')
        self._stream.buffer.write(line)
        self._stream.flush()
        if event == 'worker_result':
            self._result_seen = True
        return record

    def close(self):
        self._stream.close()


def run_worker(
    request, *, status_source_factory=None, scene_query=None,
    emitter=None, clock_ns=time.monotonic_ns,
):
    """Execute one attempt with injectable seams for offline tests."""
    request = validate_request(request, os.environ)
    request_bytes = canonical_request_bytes(request)
    request_sha256 = hashlib.sha256(request_bytes).hexdigest()
    own_emitter = emitter is None
    if emitter is None:
        protocol_fd = os.dup(1)
        os.dup2(2, 1)  # Any native/stdout diagnostic is kept off protocol fd.
        emitter = _ProtocolEmitter(protocol_fd, request['request_id'],
                                   request_sha256)
    context = node = subscription = executor = transport_node = None
    source_status = None
    ready_facts = None
    failure = None
    interrupted = False

    def on_signal(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    old_int = signal.signal(signal.SIGINT, on_signal)
    old_term = signal.signal(signal.SIGTERM, on_signal)
    cleanup_started = None
    cleanup_deadline = None
    try:
        emitter.emit('worker_started', {
            'request_binding': {
                'session_id': request['session_id'],
                'config_hash': request['config_hash'],
                'asset_manifest_sha256': request['asset_manifest_sha256'],
                'coordinator_ingress_instance_id': request[
                    'coordinator_ingress_instance_id'
                ],
            },
        })
        if status_source_factory is None:
            from rclpy.context import Context
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.node import Node
            from mecanum_nav_rl_interfaces.msg import SimulationContactState

            context = Context()
            context.init(args=None)
            node = Node('b2_server_scene_readiness', context=context)
            executor = SingleThreadedExecutor(context=context)
            executor.add_node(node)
            messages = []
            subscription = node.create_subscription(
                SimulationContactState,
                '/mecanum/local_training/backend_state', messages.append, 50,
            )

            class StatusSource:
                def next_status(self, timeout_s):
                    executor.spin_once(timeout_sec=timeout_s)
                    return messages.pop(0) if messages else None

            source_status = StatusSource()
        else:
            source_status = status_source_factory()
            source_status.start()
        if scene_query is None:
            from gz.msgs10.empty_pb2 import Empty
            from gz.msgs10.scene_pb2 import Scene
            from gz.transport13 import Node as TransportNode
            transport_node = TransportNode()

            def scene_query(service, timeout_ms):
                success, scene = transport_node.request(
                    service, Empty(), Empty, Scene, timeout_ms,
                )
                return scene if success else None

        previous_query_start_ns = None
        while clock_ns() < request['deadline_monotonic_ns']:
            if interrupted:
                raise RuntimeError('readiness worker cancelled')
            emitter.emit('status_wait_started', {
                'topic': '/mecanum/local_training/backend_state',
                'qos_depth': 50,
            })
            status_facts = None
            while clock_ns() < request['deadline_monotonic_ns']:
                if interrupted:
                    raise RuntimeError('readiness worker cancelled')
                remaining = (
                    request['deadline_monotonic_ns'] - clock_ns()
                ) / 1e9
                status = source_status.next_status(min(remaining, 0.1))
                if status is not None and _matches_status(status, request):
                    status_facts = _status_facts(status)
                    break
            if status_facts is None:
                break
            emitter.emit('status_matched', {
                'status': status_facts,
                'request_binding': {
                    'session_id': request['session_id'],
                    'config_hash': request['config_hash'],
                    'asset_manifest_sha256': request[
                        'asset_manifest_sha256'
                    ],
                    'coordinator_ingress_instance_id': request[
                        'coordinator_ingress_instance_id'
                    ],
                },
            })
            if previous_query_start_ns is not None:
                next_query_ns = previous_query_start_ns + 1_000_000_000
                while clock_ns() < next_query_ns:
                    if interrupted:
                        raise RuntimeError('readiness worker cancelled')
                    remaining_ns = min(
                        next_query_ns - clock_ns(),
                        request['deadline_monotonic_ns'] - clock_ns(),
                    )
                    if remaining_ns <= 0:
                        break
                    time.sleep(min(remaining_ns / 1e9, 0.05))
            remaining_ns = request['deadline_monotonic_ns'] - clock_ns()
            # Floor the remaining milliseconds; never round a sub-ms
            # remainder up to a request that exceeds the absolute deadline.
            timeout_ms = min(500, int(remaining_ns / 1_000_000))
            if timeout_ms < 1:
                break
            emitter.emit('scene_query_started', {
                'service': '/world/b2_training_arena/scene/info',
                'timeout_ms': timeout_ms,
            })
            remaining_ns = (
                request['deadline_monotonic_ns'] - clock_ns()
            )
            timeout_ms = min(timeout_ms, int(remaining_ns / 1_000_000))
            if timeout_ms < 1:
                raise TimeoutError(
                    'readiness deadline expired before scene query'
                )
            query_start = time.monotonic_ns()
            previous_query_start_ns = clock_ns()
            unexpected_query_error = None
            try:
                scene = scene_query(
                    '/world/b2_training_arena/scene/info', timeout_ms,
                )
                query_error = None
            except (TimeoutError, OSError) as exc:
                scene = None
                query_error = f'{type(exc).__name__}: {exc}'[:256]
            except BaseException as exc:
                scene = None
                query_error = f'{type(exc).__name__}: {exc}'[:256]
                unexpected_query_error = exc
            duration_ns = time.monotonic_ns() - query_start
            facts = _scene_facts(scene, request)
            outcome = 'ERROR' if query_error else 'MISMATCH'
            if (not query_error
                    and facts['world_name'] == request['world_id']
                    and facts['matching_model_count'] == 1):
                outcome = 'MATCH'
            emitter.emit('scene_query_finished', {
                **facts, 'duration_ns': duration_ns,
                'outcome': outcome, 'error': query_error,
            })
            if unexpected_query_error is not None:
                raise RuntimeError(
                    f'unexpected scene query failure: {query_error}'
                ) from unexpected_query_error
            if interrupted:
                raise RuntimeError('readiness worker cancelled')
            if clock_ns() >= request['deadline_monotonic_ns']:
                raise TimeoutError('scene readiness completed after deadline')
            if outcome != 'MATCH':
                continue
            ready_facts = {
                'status': status_facts,
                'scene': facts,
                'request_binding': {
                    'session_id': request['session_id'],
                    'config_hash': request['config_hash'],
                    'asset_manifest_sha256': request['asset_manifest_sha256'],
                    'coordinator_ingress_instance_id': request[
                        'coordinator_ingress_instance_id'
                    ],
                },
            }
            break
        if ready_facts is None and failure is None:
            raise TimeoutError('backend/scene readiness deadline expired')
    except BaseException as exc:
        failure = f'{type(exc).__name__}: {exc}'[:512]
    finally:
        cleanup_started = time.monotonic()
        cleanup_deadline = cleanup_started + 3.0
        cleanup_errors = []
        if transport_node is not None:
            try:
                del transport_node
                transport_node = None
                gc.collect()
            except BaseException as exc:
                cleanup_errors.append(
                    f'transport_cleanup:{type(exc).__name__}'
                )
        if node is not None and subscription is not None:
            try:
                node.destroy_subscription(subscription)
            except BaseException as exc:
                cleanup_errors.append(
                    f'subscription_cleanup:{type(exc).__name__}'
                )
        if node is not None and executor is not None:
            try:
                # rclpy Jazzy remove_node() returns None; no exception is the
                # success indication for this operation.
                executor.remove_node(node)
            except BaseException as exc:
                cleanup_errors.append(f'remove_node:{type(exc).__name__}')
            try:
                remaining = max(0.0, cleanup_deadline - time.monotonic())
                if not executor.shutdown(timeout_sec=remaining):
                    cleanup_errors.append('executor_shutdown_timeout')
            except BaseException as exc:
                cleanup_errors.append(
                    f'executor_shutdown:{type(exc).__name__}'
                )
        if node is not None:
            try:
                node.destroy_node()
            except BaseException as exc:
                cleanup_errors.append(f'node_destroy:{type(exc).__name__}')
        if context is not None:
            try:
                context.shutdown()
            except BaseException as exc:
                cleanup_errors.append(f'context_shutdown:{type(exc).__name__}')
        if source_status is not None and status_source_factory is not None:
            try:
                source_status.close()
            except BaseException as exc:
                cleanup_errors.append(
                    f'status_source_close:{type(exc).__name__}'
                )
        if time.monotonic() > cleanup_deadline:
            cleanup_errors.append('worker_cleanup_deadline_exceeded')
        if time.monotonic_ns() >= request['deadline_monotonic_ns']:
            failure = failure or 'readiness deadline expired during cleanup'
            ready_facts = None
        try:
            if cleanup_errors:
                failure = failure or 'worker cleanup failed'
                ready_facts = None
            verdict = (
                'READY'
                if ready_facts is not None and failure is None else 'FAIL'
            )
            emitter.emit('worker_result', {
                'verdict': verdict,
                'reason': (
                    '' if verdict == 'READY'
                    else failure or 'readiness failed'
                ),
                'facts': ready_facts or {},
                'cleanup_errors': cleanup_errors,
                'cleanup_elapsed_ns': int(
                    (time.monotonic() - cleanup_started) * 1e9
                ),
            })
        except BaseException:
            failure = failure or 'unable to publish worker result'
        finally:
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
            if own_emitter:
                emitter.close()
    return 0 if ready_facts is not None and failure is None else 1


def main():
    """Read one closed stdin request and execute one worker attempt."""
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        return 2
    if raw.endswith(b'\n'):
        raw = raw[:-1]
    if b'\n' in raw or b'\r' in raw:
        return 2
    request = strict_json_loads(raw)
    return run_worker(request)


if __name__ == '__main__':
    raise SystemExit(main())
