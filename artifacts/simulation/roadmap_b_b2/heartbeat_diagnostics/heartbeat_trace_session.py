"""Bounded HBTRACE1 session ownership and post-join recovery helpers."""
from __future__ import annotations

import hashlib
import os
import stat
import struct
import time
import zlib
from pathlib import Path

HEADER_SIZE = 320
RECORD_SIZE = 96
CAPACITY = 4096
MAX_FILE_SIZE = HEADER_SIZE + CAPACITY * RECORD_SIZE
HEADER_MARKER = 0x48445231
ROLE_BACKEND = 'backend'
ROLE_OBSERVER = 'observer'


def clock_context():
    """Return a host monotonic identity; clock resolution is metadata only."""
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    namespace = os.stat('/proc/self/ns/time')
    offsets = Path('/proc/self/timens_offsets').read_text()
    material = (
        f'{boot_id}|{namespace.st_dev}|{namespace.st_ino}|{offsets}'
    ).encode('ascii')
    return {
        'clock': 'CLOCK_MONOTONIC',
        'provenance': hashlib.sha256(material).hexdigest(),
        'boot_id': boot_id,
        'time_namespace_device': namespace.st_dev,
        'time_namespace_inode': namespace.st_ino,
        'time_namespace_offsets': offsets,
        'clock_resolution_ns': int(
            time.clock_getres(time.CLOCK_MONOTONIC) * 1_000_000_000
        ),
        'clock_error_bound_ns': None,
    }


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError('short file initialization write')
        view = view[written:]


def prepare_trace_pair(directory: Path, *, collection_id: str):
    """Exclusively prepare files in an existing private directory."""
    directory = Path(directory)
    if (
        not directory.is_absolute()
        or directory.resolve(strict=True) != directory.absolute()
    ):
        raise ValueError('trace directory path must not traverse symlinks')
    info = directory.stat(follow_symlinks=False)
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError('trace directory must be an owned 0700 directory')
    if not collection_id or len(collection_id.encode('ascii')) > 36:
        raise ValueError('collection id must be 1..36 ASCII bytes')
    created = []
    try:
        for role in (ROLE_BACKEND, ROLE_OBSERVER):
            path = directory / f'{role}.hbtrace'
            fd = os.open(
                path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW
                | os.O_CLOEXEC, 0o600,
            )
            try:
                os.fchmod(fd, 0o600)
                os.ftruncate(fd, MAX_FILE_SIZE)
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_nlink != 1
                ):
                    raise ValueError('trace file identity/mode is invalid')
                created.append({
                    'role': role, 'path': str(path), 'device': info.st_dev,
                    'inode': info.st_ino, 'size': info.st_size,
                })
            finally:
                os.close(fd)
        return tuple(created)
    except BaseException:
        # Retain partial files after setup failure; never replace them.
        raise


def _header_identity_fd(fd):
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_size < HEADER_SIZE
        or info.st_size > MAX_FILE_SIZE
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ValueError('trace header file identity/size invalid')
    header = os.pread(fd, HEADER_SIZE, 0)
    if len(header) != HEADER_SIZE or header[:8] != b'HBTRACE1':
        raise ValueError('trace header missing or incomplete')
    version, hsize, rsize, capacity = struct.unpack_from('<IIII', header, 8)
    overflow, checksum, marker = struct.unpack_from('<III', header, 304)
    if (version != 1 or hsize != HEADER_SIZE or rsize != RECORD_SIZE
            or not 1 <= capacity <= CAPACITY
            or info.st_size != HEADER_SIZE + capacity * RECORD_SIZE
            or marker != HEADER_MARKER
            or checksum != zlib.crc32(header[:304])):
        raise ValueError('trace header dimensions/checksum/marker invalid')

    def text(start, end):
        raw = header[start:end].split(b'\0', 1)[0]
        if not raw:
            raise ValueError('empty trace identity field')
        return raw.decode('ascii')

    return {
        'collection': text(24, 60), 'session': text(60, 96),
        'backend': struct.unpack_from('<Q', header, 96)[0],
        'config': text(104, 168), 'world': text(168, 200),
        'clock': text(200, 232), 'role': text(232, 240),
        'provenance': text(240, 304), 'overflow': overflow,
        'device': info.st_dev, 'inode': info.st_ino,
        'size': info.st_size,
    }


def _open_trace(path, allocated):
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (str(Path(path)) != allocated.get('path')
                or info.st_dev != allocated.get('device')
                or info.st_ino != allocated.get('inode')
                or info.st_size != allocated.get('size')
                or info.st_nlink != 1):
            raise ValueError('allocated_file_identity_mismatch')
        header = _header_identity_fd(fd)
        return fd, header
    except BaseException:
        os.close(fd)
        raise


def _valid_join_evidence(evidence):
    required = {
        'server_exit_status', 'server_process_joined', 'server_group_absent',
        'observer_thread_joined', 'observer_thread_alive',
        'observer_writer_closed', 'task_residue',
    }
    return (
        isinstance(evidence, dict) and set(evidence) == required
        and type(evidence['server_exit_status']) is int
        and evidence['server_process_joined'] is True
        and evidence['server_group_absent'] is True
        and evidence['observer_thread_joined'] is True
        and evidence['observer_thread_alive'] is False
        and evidence['observer_writer_closed'] is True
        and evidence['task_residue'] == 'NONE'
    )


def _valid_readiness_binding(
    status, *, verified, session_id, config_hash, world, backend_instance_id,
):
    return (
        verified is True
        and isinstance(status, dict)
        and set(status) == {
            'world_id', 'session_id', 'config_hash',
            'backend_instance_id', 'status_sequence', 'fault_flags',
            'actuator_inhibited',
        }
        and status['world_id'] == world
        and status['session_id'] == session_id
        and status['config_hash'] == config_hash
        and type(status['backend_instance_id']) is int
        and status['backend_instance_id'] == backend_instance_id
        and type(status['status_sequence']) is int
        and status['status_sequence'] > 0
        and type(status['fault_flags']) is int
        and status['fault_flags'] == 0
        and status['actuator_inhibited'] is True
    )


def _clock_error_bound(
    certificate, current_clock, expected_provenance,
    expected_binary_sha256,
):
    """Validate a paired native/Python clock bracket certificate."""
    required = {
        'schema_id', 'clock', 'provenance', 'boot_id',
        'time_namespace_device', 'time_namespace_inode',
        'time_namespace_offsets', 'source', 'method', 'binary_sha256',
        'samples', 'error_bound_ns',
    }
    if not isinstance(certificate, dict) or set(certificate) != required:
        return None
    if (
        certificate['schema_id'] != 'b2_monotonic_error_bound/v1'
        or certificate['clock'] != 'CLOCK_MONOTONIC'
        or certificate['provenance'] != expected_provenance
        or certificate['source'] != 'hbtrace_clock_monotonic_ns'
        or certificate['method'] != 'python_bracket_around_native_read'
        or not isinstance(expected_binary_sha256, str)
        or certificate['binary_sha256'] != expected_binary_sha256
        or not isinstance(certificate['binary_sha256'], str)
        or len(certificate['binary_sha256']) != 64
        or any(ch not in '0123456789abcdef'
               for ch in certificate['binary_sha256'])
    ):
        return None
    for key in (
        'boot_id', 'time_namespace_device', 'time_namespace_inode',
        'time_namespace_offsets',
    ):
        if certificate[key] != current_clock.get(key):
            return None
    samples = certificate['samples']
    if not isinstance(samples, (tuple, list)) or len(samples) < 3:
        return None
    widths = []
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) != {
            'python_before_ns', 'native_ns', 'python_after_ns',
        }:
            return None
        before, native, after = (
            sample['python_before_ns'], sample['native_ns'],
            sample['python_after_ns'],
        )
        if any(type(value) is not int or value < 0
               for value in (before, native, after)):
            return None
        if before > native or native > after:
            return None
        widths.append(after - before)
    bound = max(widths)
    if (type(certificate['error_bound_ns']) is not int
            or certificate['error_bound_ns'] != bound):
        return None
    return bound


def _decode_analyzer_events(records, *, binding, provenance, bound_ns):
    """Decode only event meanings actually present in HBTRACE1 payloads."""
    from heartbeat_diagnostics import DiagnosticEvent, EventKind

    decoded = []
    issues = []
    for role, result in records.items():
        for (
            _record_sequence, kind, timestamp, status_sequence, payload
        ) in result:
            if kind != 2:
                continue
            if role == ROLE_BACKEND:
                if len(payload) == 1 and payload[0] == 3:
                    issues.append(
                        f'backend_publish_exception:status_sequence='
                        f'{status_sequence}'
                    )
                    continue
                if len(payload) != 1 or payload[0] not in (1, 2):
                    issues.append(
                        f'backend_event_payload_unsupported:record='
                        f'{_record_sequence}'
                    )
                    continue
                event_kind = (
                    EventKind.PUBLISH_BEGIN if payload[0] == 1
                    else EventKind.PUBLISH_RETURN
                )
                accepted = None
            else:
                if len(payload) != 2:
                    issues.append(
                        f'observer_event_payload_unsupported:record='
                        f'{_record_sequence}'
                    )
                    continue
                code, flags = payload
                if code == 9:
                    label = {1: 'duplicate', 2: 'out_of_order'}.get(
                        flags, 'unknown',
                    )
                    issues.append(
                        f'observer_sequence_{label}:status_sequence='
                        f'{status_sequence}'
                    )
                    continue
                mapping = {
                    6: EventKind.CALLBACK_ENTRY,
                    7: EventKind.STATUS_VALIDATION,
                    8: EventKind.HEARTBEAT_CHECK,
                }
                event_kind = mapping.get(code)
                if event_kind is None:
                    issues.append(
                        f'observer_event_code_unsupported:record='
                        f'{_record_sequence}:code={code}'
                    )
                    continue
                accepted = bool(flags) if code == 7 else None
            decoded.append(DiagnosticEvent(
                kind=event_kind, session_id=binding['session'],
                backend_instance_id=binding['backend'],
                status_sequence=status_sequence,
                config_hash=binding['config'], world=binding['world'],
                timestamp_ns=timestamp, clock_domain='CLOCK_MONOTONIC',
                provenance=provenance, source_verified=True,
                uncertainty_ns=bound_ns, status_accepted=accepted,
            ))
    return tuple(decoded), tuple(issues)


def read_trace_pair(
    backend_path: Path, observer_path: Path, *, session_id: str,
    config_hash: str, world: str, collection_id: str, clock_provenance: str,
    joined: bool, requested_window=None, clock_error_bound_ns=None,
    allocated_files=None, expected_backend_instance_id=None,
    join_evidence=None, clock_error_certificate=None,
    expected_clock_library_sha256=None,
    readiness_backend_status=None, readiness_binding_verified=False,
):
    """Recover joined records and report coverage separately."""
    from heartbeat_trace_reader import read_after_join

    if joined is not True:
        raise ValueError('both trace writers must be joined before reading')
    issues = []
    join_verified = _valid_join_evidence(join_evidence)
    if not join_verified:
        issues.append('writer_join_or_residue_evidence_unverified')
    try:
        current_clock = clock_context()
    except (OSError, ValueError) as error:
        return {
            'records': {'backend': (), 'observer': ()},
            'coverage_complete': False,
            'issues': (f'clock_context_unavailable:{type(error).__name__}',),
        }
    if current_clock['provenance'] != clock_provenance:
        return {
            'records': {'backend': (), 'observer': ()},
            'coverage_complete': False,
            'issues': ('clock_boot_or_time_namespace_mismatch',),
        }
    bound_ns = _clock_error_bound(
        clock_error_certificate, current_clock, clock_provenance,
        expected_clock_library_sha256,
    )
    if bound_ns is None:
        issues.append('clock_error_bound_unverified')
    if clock_error_bound_ns is not None:
        issues.append('plain_clock_error_integer_not_evidence')
    readiness_binding_valid = _valid_readiness_binding(
        readiness_backend_status, verified=readiness_binding_verified,
        session_id=session_id, config_hash=config_hash, world=world,
        backend_instance_id=expected_backend_instance_id,
    )
    if not readiness_binding_valid:
        issues.append('independent_backend_binding_missing')
    paths = {'backend': backend_path, 'observer': observer_path}
    headers = {}
    opened = {}
    allocations = tuple(allocated_files or ())
    allocation_by_role = {}
    for item in allocations:
        if (not isinstance(item, dict)
                or item.get('role') in allocation_by_role):
            issues.append('allocated_file_binding_malformed_or_duplicated')
            allocation_by_role = {}
            break
        allocation_by_role[item.get('role')] = item
    if set(allocation_by_role) != set(paths):
        issues.append('allocated_file_binding_incomplete')
    for role, path in paths.items():
        try:
            allocation = allocation_by_role.get(role)
            if allocation is None or any(
                type(allocation.get(key)) is not int
                for key in ('device', 'inode', 'size')
            ):
                raise ValueError('allocated_file_identity_missing')
            fd, header = _open_trace(path, allocation)
            opened[role] = fd
            headers[role] = header
        except (OSError, ValueError, UnicodeError) as error:
            issues.append(
                f'{role}_header_unavailable:{type(error).__name__}:'
                f'{str(error)[:120]}'
            )
    results = {}
    for role, path in paths.items():
        header = headers.get(role)
        if header is None or not join_verified:
            continue
        expected = {
            'collection': collection_id, 'session': session_id,
            'backend': header['backend'], 'config': config_hash,
            'world': world, 'clock': 'CLOCK_MONOTONIC',
            'provenance': clock_provenance,
            'role': ROLE_BACKEND if role == 'backend' else ROLE_OBSERVER,
        }
        if header['overflow'] != 0:
            issues.append(f'{role}_header_overflow')
        try:
            result = read_after_join(
                f'/proc/self/fd/{opened[role]}', expected=expected,
                requested_window=requested_window,
                clock_verified=True,
            )
            results[role] = result
            issues.extend(f'{role}:{issue}' for issue in result.issues)
        except (OSError, ValueError) as error:
            issues.append(f'{role}_read_failed:{type(error).__name__}:{error}')
        after = os.fstat(opened[role])
        if (after.st_dev, after.st_ino, after.st_size) != (
                header['device'], header['inode'], header['size']):
            issues.append(f'{role}_file_identity_changed_during_read')
            results.pop(role, None)
    for fd in opened.values():
        os.close(fd)

    pair_identity_valid = (
        readiness_binding_valid and len(headers) == 2
        and all(role in results for role in paths) and join_verified
    )
    if pair_identity_valid:
        backend_header = headers['backend']
        observer_header = headers['observer']
        if (backend_header['role'] != ROLE_BACKEND
                or observer_header['role'] != ROLE_OBSERVER
                or backend_header['backend'] == 0
                or observer_header['backend'] != backend_header['backend']
                or backend_header['backend'] != expected_backend_instance_id):
            issues.append('writer_roles_or_backend_instance_mismatch')
            pair_identity_valid = False
        shared_fields = (
            'collection', 'session', 'config', 'world', 'clock', 'provenance',
        )
        if any(backend_header[field] != observer_header[field]
               for field in shared_fields):
            issues.append('writer_shared_identity_mismatch')
            pair_identity_valid = False
        expected_fields = {
            'collection': collection_id, 'session': session_id,
            'config': config_hash, 'world': world,
            'clock': 'CLOCK_MONOTONIC', 'provenance': clock_provenance,
        }
        if any(
            header[field] != expected
            for header in (backend_header, observer_header)
            for field, expected in expected_fields.items()
        ):
            issues.append('trace_pair_does_not_match_requested_binding')
            pair_identity_valid = False
    else:
        issues.append('trace_pair_header_incomplete')
    binding = {
        'session': session_id, 'backend': expected_backend_instance_id,
        'config': config_hash, 'world': world,
    }
    raw_records = {role: value.records for role, value in results.items()}
    usable_records = raw_records if pair_identity_valid else {}
    requested_valid = (
        isinstance(requested_window, (tuple, list))
        and len(requested_window) == 2
        and all(
            type(value) is int and value >= 0 for value in requested_window
        )
        and requested_window[0] <= requested_window[1]
    )
    edge_valid = False
    if (requested_valid and bound_ns is not None and pair_identity_valid
            and len(results) == 2):
        edge_valid = all(
            value.records
            and value.records[0][1] == 1
            and value.records[-1][1] == 3
            and value.records[0][2] + bound_ns <= requested_window[0]
            and value.records[-1][2] - bound_ns >= requested_window[1]
            for value in results.values()
        )
        if not edge_valid:
            issues.append(
                'coverage_uncertainty_overlaps_requested_window_edge'
            )
    if requested_window is None:
        issues.append('coverage_window_missing')
    file_coverage_complete = bool(
        pair_identity_valid and len(results) == 2 and join_verified
        and bound_ns is not None and requested_valid and edge_valid
        and all(result.structure_valid for result in results.values())
        and all(result.coverage_complete for result in results.values())
    )
    decoded = ()
    decode_issues = ()
    analysis = None
    if file_coverage_complete:
        decoded, decode_issues = _decode_analyzer_events(
            usable_records, binding=binding, provenance=clock_provenance,
            bound_ns=bound_ns,
        )
        from heartbeat_diagnostics import (
            BoundedEventBuffer, Binding, analyze,
        )
        event_buffer = BoundedEventBuffer(max(1, len(decoded)))
        for event in decoded:
            event_buffer.append(event)
        analysis = None if decode_issues else analyze(
            event_buffer, expected=Binding(
                session_id, expected_backend_instance_id,
                config_hash, world,
            ),
        ) if decoded else None
    return {
        'records': usable_records,
        'raw_recovery_records': raw_records,
        'paired_records': (
            {role: value.records for role, value in results.items()}
            if pair_identity_valid else {}
        ),
        'pair_identity_valid': pair_identity_valid,
        'coverage_complete': file_coverage_complete,
        'issues': tuple(issues) + decode_issues,
        'backend_instance_id': headers.get('backend', {}).get('backend'),
        'clock_identity_verified': True,
        'clock_error_bound_ns': bound_ns,
        'analyzer_events': decoded,
        'analysis': analysis,
        'diagnostic_events_complete': not decode_issues,
    }
