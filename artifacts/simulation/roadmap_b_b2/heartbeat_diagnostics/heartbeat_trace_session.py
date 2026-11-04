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


def _header_identity(path):
    path = Path(path)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
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
        header = os.read(fd, HEADER_SIZE)
    finally:
        os.close(fd)
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
    }


def read_trace_pair(
    backend_path: Path, observer_path: Path, *, session_id: str,
    config_hash: str, world: str, collection_id: str, clock_provenance: str,
    joined: bool, requested_window=None, clock_error_bound_ns=None,
):
    """Recover joined records and report coverage separately."""
    from heartbeat_trace_reader import read_after_join

    if joined is not True:
        raise ValueError('both trace writers must be joined before reading')
    issues = []
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
    clock_error_bound_valid = (
        isinstance(clock_error_bound_ns, int)
        and not isinstance(clock_error_bound_ns, bool)
        and clock_error_bound_ns >= 0
    )
    if not clock_error_bound_valid:
        issues.append('clock_error_bound_unknown')
    paths = {'backend': backend_path, 'observer': observer_path}
    headers = {}
    for role, path in paths.items():
        try:
            headers[role] = _header_identity(path)
        except (OSError, ValueError, UnicodeError) as error:
            issues.append(
                f'{role}_header_unavailable:{type(error).__name__}:'
                f'{str(error)[:120]}'
            )
    results = {}
    for role, path in paths.items():
        header = headers.get(role)
        if header is None:
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
                path, expected=expected, requested_window=requested_window,
                clock_verified=True,
            )
            results[role] = result
            issues.extend(f'{role}:{issue}' for issue in result.issues)
        except (OSError, ValueError) as error:
            issues.append(f'{role}_read_failed:{type(error).__name__}:{error}')
        try:
            after = _header_identity(path)
            if (after['device'], after['inode']) != (
                    header['device'], header['inode']):
                issues.append(f'{role}_file_identity_changed_during_read')
                results.pop(role, None)
        except (OSError, ValueError, UnicodeError):
            issues.append(f'{role}_file_identity_unavailable_after_read')
            results.pop(role, None)
    if any('file_identity_' in issue for issue in issues):
        results.clear()

    pair_identity_valid = len(headers) == 2
    if pair_identity_valid:
        backend_header = headers['backend']
        observer_header = headers['observer']
        if (backend_header['role'] != ROLE_BACKEND
                or observer_header['role'] != ROLE_OBSERVER
                or backend_header['backend'] == 0
                or observer_header['backend'] != backend_header['backend']):
            issues.append('writer_roles_or_backend_instance_mismatch')
            pair_identity_valid = False
        shared_fields = (
            'collection', 'session', 'config', 'world', 'clock', 'provenance',
        )
        if any(backend_header[field] != observer_header[field]
               for field in shared_fields):
            issues.append('writer_shared_identity_mismatch')
            pair_identity_valid = False
    else:
        issues.append('trace_pair_header_incomplete')
    return {
        'records': {role: value.records for role, value in results.items()},
        'paired_records': (
            {role: value.records for role, value in results.items()}
            if pair_identity_valid else {}
        ),
        'pair_identity_valid': pair_identity_valid,
        'coverage_complete': bool(
            pair_identity_valid and len(results) == 2
            and clock_error_bound_valid
            and all(r.structure_valid for r in results.values())
            and all(r.coverage_complete for r in results.values())
        ),
        'issues': tuple(issues),
        'backend_instance_id': headers.get('backend', {}).get('backend'),
        'clock_identity_verified': True,
        'clock_error_bound_ns': clock_error_bound_ns,
    }
