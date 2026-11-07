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
CAPACITY = 524288
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
        'observer_process_identity', 'observer_process_identity_verified',
        'observer_process_joined', 'observer_process_group_absent',
        'observer_exit_status', 'observer_stop_acknowledged',
        'observer_end_written', 'observer_handle_closed',
        'observer_writer_closed', 'observer_termination', 'task_residue',
    }
    identity = evidence.get('observer_process_identity') if isinstance(
        evidence, dict,
    ) else None
    identity_valid = (
        isinstance(identity, dict)
        and set(identity) == {
            'pid', 'process_group_id', 'session_id', 'start_ticks',
        }
        and all(type(identity[key]) is int and identity[key] > 0
                for key in identity)
        and identity['pid'] == identity['process_group_id']
        and identity['pid'] == identity['session_id']
    )
    dispatches = evidence.get('observer_signal_dispatches', ()) if isinstance(evidence, dict) else None
    dispatches_valid = isinstance(dispatches, (list, tuple))
    if dispatches_valid:
        for item in dispatches:
            fields = {'signal', 'identity_verified', 'raw_exit_status_before_dispatch', 'outcome'}
            if (not isinstance(item, dict) or not fields <= set(item)
                    or not set(item) <= fields | {'error_type'}
                    or item['signal'] not in ('SIGTERM', 'SIGKILL')
                    or type(item['identity_verified']) is not bool
                    or item['outcome'] not in ('DISPATCHED', 'DISPATCH_FAILED', 'IDENTITY_UNKNOWN')
                    or (item['outcome'] == 'DISPATCHED' and not item['identity_verified'])
                    or (item['raw_exit_status_before_dispatch'] is not None
                        and type(item['raw_exit_status_before_dispatch']) is not int)):
                dispatches_valid = False
                break
    return (
        isinstance(evidence, dict)
        and set(evidence) in (required, required | {'observer_signal_dispatches'})
        and dispatches_valid
        and type(evidence['server_exit_status']) is int
        and evidence['server_process_joined'] is True
        and evidence['server_group_absent'] is True
        and evidence['observer_process_identity_verified'] is True
        and identity_valid
        and evidence['observer_process_joined'] is True
        and evidence['observer_process_group_absent'] is True
        and type(evidence['observer_exit_status']) is int
        and type(evidence['observer_stop_acknowledged']) is bool
        and type(evidence['observer_end_written']) is bool
        and type(evidence['observer_handle_closed']) is bool
        and type(evidence['observer_writer_closed']) is bool
        and evidence['observer_writer_closed'] is (
            evidence['observer_end_written']
            and evidence['observer_handle_closed']
        )
        and evidence['observer_termination'] in {
            'CLEAN_COOPERATIVE', 'SIGTERM', 'SIGKILL', 'UNCONFIRMED_EXIT',
        }
        and evidence['task_residue'] == 'NONE'
    )


def _valid_clean_join_evidence(evidence):
    return (
        _valid_join_evidence(evidence)
        and evidence['observer_stop_acknowledged'] is True
        and evidence['observer_end_written'] is True
        and evidence['observer_handle_closed'] is True
        and evidence['observer_writer_closed'] is True
        and evidence['observer_exit_status'] == 0
        and evidence['observer_termination'] == 'CLEAN_COOPERATIVE'
        and not evidence.get('observer_signal_dispatches', ())
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


def _clock_domain_verified(
    certificate, current_clock, expected_provenance, expected_binary_sha256,
):
    """Check clock-source agreement; setup brackets are not an error bound."""
    required = {
        'schema_id', 'clock', 'provenance', 'boot_id',
        'time_namespace_device', 'time_namespace_inode',
        'time_namespace_offsets', 'source', 'method', 'binary_sha256',
        'samples', 'observed_max_bracket_width_ns',
    }
    if not isinstance(certificate, dict) or set(certificate) != required:
        return None
    if (
        certificate['schema_id'] != 'b2_clock_domain_check/v1'
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
    if (type(certificate['observed_max_bracket_width_ns']) is not int
            or certificate['observed_max_bracket_width_ns'] != bound):
        return None
    return True


def _clock_error_bound(proof, current_clock, expected_provenance):
    """Accept only scoped, externally evidenced uncertainty, never jitter."""
    required = {
        'schema_id', 'clock', 'provenance', 'boot_id',
        'time_namespace_device', 'time_namespace_inode',
        'time_namespace_offsets', 'scope', 'source_verified',
        'evidence_sha256', 'error_bound_ns',
    }
    if not isinstance(proof, dict) or set(proof) != required:
        return None
    if (
        proof['schema_id'] != 'b2_clock_uncertainty_proof/v1'
        or proof['clock'] != 'CLOCK_MONOTONIC'
        or proof['provenance'] != expected_provenance
        or proof['scope'] != 'trace_timestamp_and_window_boundary'
        or proof['source_verified'] is not True
        or type(proof['error_bound_ns']) is not int
        or proof['error_bound_ns'] < 0
        or not isinstance(proof['evidence_sha256'], str)
        or len(proof['evidence_sha256']) != 64
        or any(char not in '0123456789abcdef'
               for char in proof['evidence_sha256'])
    ):
        return None
    for key in (
        'boot_id', 'time_namespace_device', 'time_namespace_inode',
        'time_namespace_offsets',
    ):
        if proof[key] != current_clock.get(key):
            return None
    return proof['error_bound_ns']


def _event_interval_in_window(timestamp, bound, window):
    earliest = timestamp - bound
    latest = timestamp + bound
    start, end = window
    if latest < start or earliest > end:
        return False, False
    if earliest < start or latest > end:
        return True, False
    return True, True


def _publisher_coverage(
    records, *, binding, window, bound_ns, clock_domain, provenance,
):
    """Build proof only from full boundaries and resolved publish lifetimes."""
    from heartbeat_diagnostics import Binding, PublishCoverage

    if not records:
        return None, ('backend_trace_records_missing',)
    start, end = window
    if (records[0][1] != 1 or records[-1][1] != 3
            or records[0][2] + bound_ns > start
            or records[-1][2] - bound_ns < end):
        return None, ('backend_publish_boundary_does_not_cover_window',)
    calls = {}
    issues = []
    for record_sequence, kind, timestamp, status_sequence, payload in records:
        if kind != 2:
            continue
        if (status_sequence <= 0 or len(payload) != 1
                or payload[0] not in (1, 2, 3)):
            issues.append(
                f'backend_publish_record_unsupported:{record_sequence}'
            )
            continue
        code = payload[0]
        intersects, contained = _event_interval_in_window(
            timestamp, bound_ns, window,
        )
        if intersects:
            if not contained:
                issues.append(
                    'publish_event_uncertainty_overlaps_window:'
                    f'{record_sequence}'
                )
        call = calls.setdefault(status_sequence, {'begin': [], 'terminal': []})
        if code == 1:
            call['begin'].append((timestamp, record_sequence))
        else:
            call['terminal'].append((timestamp, record_sequence, code))
    clear_at_start = True
    clear_at_end = True
    for sequence, call in calls.items():
        begins = call['begin']
        terminals = call['terminal']
        if len(begins) != 1 or len(terminals) > 1 or not begins:
            issues.append(
                f'publish_lifetime_unresolved:status_sequence={sequence}'
            )
            clear_at_start = False
            clear_at_end = False
            continue
        begin = begins[0][0]
        begin_low, begin_high = begin - bound_ns, begin + bound_ns
        terminal = terminals[0][0] if terminals else None
        terminal_low = terminal - bound_ns if terminal is not None else None
        terminal_high = terminal + bound_ns if terminal is not None else None
        if terminal is not None and begin_high >= terminal_low:
            issues.append(
                f'publish_begin_terminal_order_unverified:{sequence}'
            )
            clear_at_start = False
            clear_at_end = False
            continue
        if begin_low <= start < begin_high:
            clear_at_start = False
            issues.append(f'publish_start_state_ambiguous:{sequence}')
        elif begin_high <= start:
            if terminal is None or terminal_high > start:
                clear_at_start = False
                if terminal is not None and terminal_low <= start:
                    issues.append(f'publish_start_state_ambiguous:{sequence}')
        elif begin_low > start:
            pass
        if begin_low <= end < begin_high:
            clear_at_end = False
            issues.append(f'publish_end_state_ambiguous:{sequence}')
        elif begin_high <= end:
            if terminal is None or terminal_high > end:
                clear_at_end = False
                if terminal is not None and terminal_low <= end:
                    issues.append(f'publish_end_state_ambiguous:{sequence}')
        elif begin_low > end:
            pass
    if issues or not clear_at_start or not clear_at_end:
        return None, tuple(issues or ('publish_boundary_state_unresolved',))
    return PublishCoverage(
        binding=Binding(
            binding['session'], binding['backend'], binding['config'],
            binding['world'],
        ),
        start_ns=start, end_ns=end, clock_domain=clock_domain,
        provenance=provenance, source_verified=True, complete=True,
        in_flight_clear_at_start=True,
    ), ()


def _decode_analyzer_events(
    records, *, binding, provenance, bound_ns, requested_window,
):
    """Decode source-supported events and keep only certain in-window facts."""
    from heartbeat_diagnostics import DiagnosticEvent, EventKind

    decoded = []
    issues = []
    health = {}
    baseline = {}
    health_facts = []

    def make_event(kind, timestamp, sequence, **kwargs):
        return DiagnosticEvent(
            kind=kind, session_id=binding['session'],
            backend_instance_id=binding['backend'],
            status_sequence=sequence, config_hash=binding['config'],
            world=binding['world'], timestamp_ns=timestamp,
            clock_domain='CLOCK_MONOTONIC', provenance=provenance,
            source_verified=True, uncertainty_ns=bound_ns, **kwargs,
        )

    for role, result in records.items():
        for record_sequence, kind, timestamp, sequence, payload in result:
            if kind != 2:
                continue
            if role == ROLE_BACKEND:
                if len(payload) != 1 or payload[0] not in (1, 2, 3):
                    issues.append(
                        f'backend_event_payload_unsupported:record='
                        f'{record_sequence}'
                    )
                    continue
                if payload[0] == 3:
                    issues.append(
                        f'backend_publish_exception:status_sequence={sequence}'
                    )
                    continue
                event_kind = (
                    EventKind.PUBLISH_BEGIN if payload[0] == 1
                    else EventKind.PUBLISH_RETURN
                )
                decoded.append(make_event(event_kind, timestamp, sequence))
                continue

            if len(payload) != 2:
                issues.append(
                    f'observer_event_payload_unsupported:record='
                    f'{record_sequence}'
                )
                continue
            code, flags = payload
            if code == 9:
                if flags not in (1, 2):
                    issues.append(
                        f'observer_event_flags_unsupported:record='
                        f'{record_sequence}'
                    )
                    continue
                label = {1: 'duplicate', 2: 'out_of_order'}.get(
                    flags, 'unknown',
                )
                issues.append(
                    f'observer_sequence_{label}:status_sequence={sequence}'
                )
                continue
            if flags not in (0, 1):
                issues.append(
                    'observer_event_flags_unsupported:'
                    f'record={record_sequence}'
                )
                continue
            if code == 7:
                health.setdefault(sequence, []).append(
                    (timestamp, bool(flags)),
                )
                continue
            if code == 10:
                baseline.setdefault(sequence, []).append(
                    (timestamp, bool(flags)),
                )
                continue
            mapping = {
                6: EventKind.CALLBACK_ENTRY,
                8: EventKind.HEARTBEAT_CHECK,
            }
            event_kind = mapping.get(code)
            if event_kind is None:
                issues.append(
                    f'observer_event_code_unsupported:record='
                    f'{record_sequence}:code={code}'
                )
                continue
            decoded.append(make_event(event_kind, timestamp, sequence))

    for sequence in sorted(set(health) | set(baseline)):
        health_items = health.get(sequence, ())
        baseline_items = baseline.get(sequence, ())
        if len(health_items) != 1 or len(baseline_items) != 1:
            issues.append(
                f'status_health_or_baseline_decision_missing_or_ambiguous:'
                f'seq={sequence}'
            )
            continue
        validation_ns, health_valid = health_items[0]
        baseline_ns, baseline_used = baseline_items[0]
        if baseline_ns < validation_ns:
            issues.append(
                f'baseline_decision_precedes_validation:seq={sequence}'
            )
            continue
        health_facts.append({
            'status_sequence': sequence, 'health_valid': health_valid,
            'used_as_baseline': baseline_used,
            'validation_timestamp_ns': validation_ns,
            'baseline_decision_timestamp_ns': baseline_ns,
        })
        decoded.append(make_event(
            EventKind.STATUS_VALIDATION, validation_ns, sequence,
            status_accepted=health_valid and baseline_used,
        ))

    selected = []
    for event in decoded:
        intersects, contained = _event_interval_in_window(
            event.timestamp_ns, bound_ns, requested_window,
        )
        if not intersects:
            continue
        if not contained:
            issues.append(
                f'event_uncertainty_overlaps_requested_window:'
                f'{event.kind.value}:seq={event.status_sequence}'
            )
            continue
        selected.append(event)
    if any(issue.startswith('event_uncertainty_overlaps_requested_window')
           for issue in issues):
        return (), tuple(issues), tuple(health_facts)
    return tuple(selected), tuple(issues), tuple(health_facts)


def read_trace_pair(
    backend_path: Path, observer_path: Path, *, session_id: str,
    config_hash: str, world: str, collection_id: str, clock_provenance: str,
    joined: bool, requested_window=None, clock_error_bound_ns=None,
    allocated_files=None, expected_backend_instance_id=None,
    join_evidence=None, clock_domain_certificate=None,
    clock_error_bound_proof=None,
    expected_clock_library_sha256=None,
    readiness_backend_status=None, readiness_binding_verified=False,
):
    """Recover joined records and report coverage separately."""
    from heartbeat_trace_reader import read_after_join

    if joined is not True:
        raise ValueError('both trace writers must be joined before reading')
    issues = []
    raw_recovery_allowed = _valid_join_evidence(join_evidence)
    clean_join_verified = _valid_clean_join_evidence(join_evidence)
    if not raw_recovery_allowed:
        issues.append('observer_process_reap_or_group_absence_unverified')
    elif not clean_join_verified:
        issues.append('observer_not_cleanly_closed_raw_recovery_only')
    try:
        current_clock = clock_context()
    except (OSError, ValueError) as error:
        current_clock = {}
        issues.append(f'clock_context_unavailable:{type(error).__name__}')
    if current_clock.get('provenance') != clock_provenance:
        issues.append('clock_boot_or_time_namespace_mismatch')
    clock_domain_verified = _clock_domain_verified(
        clock_domain_certificate, current_clock, clock_provenance,
        expected_clock_library_sha256,
    ) if current_clock.get('provenance') == clock_provenance else None
    if not clock_domain_verified:
        issues.append('clock_domain_agreement_unverified')
    bound_ns = (
        _clock_error_bound(
            clock_error_bound_proof, current_clock, clock_provenance,
        ) if clock_domain_verified else None
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
        if header is None or not raw_recovery_allowed:
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
                clock_verified=clock_domain_verified,
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
        and all(role in results for role in paths) and raw_recovery_allowed
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
    recoverable_records = raw_records if raw_recovery_allowed else {}
    usable_records = (
        raw_records if pair_identity_valid and clean_join_verified else {}
    )
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
    trace_files_complete = bool(
        pair_identity_valid and len(results) == 2 and clean_join_verified
        and clock_domain_verified
        and bound_ns is not None and requested_valid and edge_valid
        and all(result.structure_valid for result in results.values())
        and all(result.coverage_complete for result in results.values())
    )
    decoded = ()
    decode_issues = ()
    health_facts = ()
    analysis = None
    publish_coverage = None
    if trace_files_complete:
        decoded, decode_issues, health_facts = _decode_analyzer_events(
            usable_records, binding=binding, provenance=clock_provenance,
            bound_ns=bound_ns, requested_window=requested_window,
        )
        if not decode_issues:
            publish_coverage, publish_issues = _publisher_coverage(
                usable_records['backend'], binding=binding,
                window=requested_window, bound_ns=bound_ns,
                clock_domain='CLOCK_MONOTONIC',
                provenance=clock_provenance,
            )
            issues.extend(publish_issues)
        if not decode_issues and decoded:
            from heartbeat_diagnostics import (
                BoundedEventBuffer, Binding, analyze,
            )
            event_buffer = BoundedEventBuffer(max(1, len(decoded)))
            for event in decoded:
                event_buffer.append(event)
            analysis = analyze(
                event_buffer, expected=Binding(
                    session_id, expected_backend_instance_id,
                    config_hash, world,
                ), publisher_coverage=publish_coverage,
            )
    diagnostic_coverage_complete = bool(
        trace_files_complete and publish_coverage is not None
        and analysis is not None and analysis.evidence_complete
    )
    return {
        'records': usable_records,
        'raw_recovery_records': recoverable_records,
        'paired_records': (
            {role: value.records for role, value in results.items()}
            if pair_identity_valid else {}
        ),
        'pair_identity_valid': pair_identity_valid,
        'raw_recovery_allowed': raw_recovery_allowed,
        'clean_close_verified': clean_join_verified,
        'trace_files_complete': trace_files_complete,
        'coverage_complete': diagnostic_coverage_complete,
        'diagnostic_coverage_complete': diagnostic_coverage_complete,
        'issues': tuple(issues) + decode_issues,
        'backend_instance_id': headers.get('backend', {}).get('backend'),
        'clock_identity_verified': bool(clock_domain_verified),
        'clock_domain_verified': bool(clock_domain_verified),
        'clock_error_bound_ns': bound_ns,
        'publish_coverage': publish_coverage,
        'analyzer_events': decoded,
        'analysis': analysis,
        'status_health_facts': health_facts,
        'diagnostic_events_complete': not decode_issues,
    }
