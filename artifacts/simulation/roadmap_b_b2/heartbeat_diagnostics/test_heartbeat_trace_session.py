"""Offline tests for HBTRACE1 pair ownership and post-join reading."""
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from heartbeat_diagnostics import Cause

from heartbeat_trace_session import (
    CAPACITY, HEADER_MARKER, HEADER_SIZE, MAX_FILE_SIZE, RECORD_SIZE,
    clock_context, prepare_trace_pair, read_trace_pair,
)


def _field(buffer, start, size, value):
    raw = value.encode('ascii')
    if len(raw) > size:
        raise ValueError(value)
    buffer[start:start + len(raw)] = raw


def _write_fixture(path, *, role, backend=42, session='session-1',
                   config='a' * 64, world='b2_training_arena',
                   provenance='c' * 64, records=((1, 100), (3, 400))):
    raw = bytearray(MAX_FILE_SIZE)
    raw[:8] = b'HBTRACE1'
    struct.pack_into('<IIII', raw, 8, 1, HEADER_SIZE, RECORD_SIZE, CAPACITY)
    _field(raw, 24, 36, 'collection-1')
    _field(raw, 60, 36, session)
    struct.pack_into('<Q', raw, 96, backend)
    _field(raw, 104, 64, config)
    _field(raw, 168, 32, world)
    _field(raw, 200, 32, 'CLOCK_MONOTONIC')
    _field(raw, 232, 8, role)
    _field(raw, 240, 64, provenance)
    struct.pack_into('<I', raw, 308, zlib.crc32(raw[:304]))
    struct.pack_into('<I', raw, 312, HEADER_MARKER)
    for index, item in enumerate(records):
        kind, timestamp = item[:2]
        status_sequence = item[2] if len(item) > 2 else 0
        payload = item[3] if len(item) > 3 else b''
        start = HEADER_SIZE + index * RECORD_SIZE
        struct.pack_into('<QIIQQ', raw, start, index + 1, kind, len(payload),
                         timestamp, status_sequence)
        raw[start + 32:start + 32 + len(payload)] = payload
        struct.pack_into('<I', raw, start + 88,
                         zlib.crc32(raw[start:start + 88]))
        struct.pack_into('<I', raw, start + 92, 0x434F4D54)
    path.write_bytes(raw)
    os.chmod(path, 0o600)


def _allocation(path, role):
    info = os.stat(path, follow_symlinks=False)
    return {
        'role': role, 'path': str(path), 'device': info.st_dev,
        'inode': info.st_ino,
        'size': info.st_size,
    }


def _join_evidence():
    return {
        'server_exit_status': 0, 'server_process_joined': True,
        'server_group_absent': True,
        'observer_process_identity': {
            'pid': 123, 'process_group_id': 123, 'session_id': 123,
            'start_ticks': 456,
        },
        'observer_process_identity_verified': True,
        'observer_process_joined': True,
        'observer_process_group_absent': True,
        'observer_exit_status': 0, 'observer_stop_acknowledged': True,
        'observer_end_written': True,
        'observer_handle_closed': True,
        'observer_writer_closed': True,
        'observer_termination': 'CLEAN_COOPERATIVE',
        'task_residue': 'NONE',
    }


def _readiness_binding():
    return {
        'world_id': 'b2_training_arena', 'session_id': 'session-1',
        'config_hash': 'a' * 64, 'backend_instance_id': 42,
        'status_sequence': 7, 'fault_flags': 0,
        'actuator_inhibited': True,
    }


def _clock_certificate(context, *, width=0):
    sample = {
        'python_before_ns': 100, 'native_ns': 100 + width // 2,
        'python_after_ns': 100 + width,
    }
    return {
        'schema_id': 'b2_clock_domain_check/v1',
        'clock': 'CLOCK_MONOTONIC', 'provenance': context['provenance'],
        'boot_id': context['boot_id'],
        'time_namespace_device': context['time_namespace_device'],
        'time_namespace_inode': context['time_namespace_inode'],
        'time_namespace_offsets': context['time_namespace_offsets'],
        'source': 'hbtrace_clock_monotonic_ns',
        'method': 'python_bracket_around_native_read',
        'binary_sha256': 'd' * 64, 'samples': [sample, sample, sample],
        'observed_max_bracket_width_ns': width,
    }


def _clock_proof(context, *, bound=0):
    """Fixture for a separately supplied, scoped uncertainty proof."""
    return {
        'schema_id': 'b2_clock_uncertainty_proof/v1',
        'clock': 'CLOCK_MONOTONIC',
        'provenance': context['provenance'],
        'boot_id': context['boot_id'],
        'time_namespace_device': context['time_namespace_device'],
        'time_namespace_inode': context['time_namespace_inode'],
        'time_namespace_offsets': context['time_namespace_offsets'],
        'scope': 'trace_timestamp_and_window_boundary',
        'source_verified': True,
        'evidence_sha256': 'e' * 64,
        'error_bound_ns': bound,
    }


def _legacy_setup_bracket(context, *, width=0):
    """Model the old setup bracket mistakenly treated as an error bound."""
    sample = {
        'python_before_ns': 100, 'native_ns': 100 + width // 2,
        'python_after_ns': 100 + width,
    }
    return {
        'schema_id': 'b2_monotonic_error_bound/v1',
        'clock': 'CLOCK_MONOTONIC', 'provenance': context['provenance'],
        'boot_id': context['boot_id'],
        'time_namespace_device': context['time_namespace_device'],
        'time_namespace_inode': context['time_namespace_inode'],
        'time_namespace_offsets': context['time_namespace_offsets'],
        'source': 'hbtrace_clock_monotonic_ns',
        'method': 'python_bracket_around_native_read',
        'binary_sha256': 'd' * 64, 'samples': [sample, sample, sample],
        'error_bound_ns': width,
    }


class HeartbeatTraceSessionTests(unittest.TestCase):
    """Exercise bounded trace pair preparation and recovery."""

    def setUp(self):
        """Create a private temporary directory for each test."""
        self.temp = tempfile.TemporaryDirectory(prefix='hbtrace-session-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        os.chmod(self.directory, 0o700)
        self.provenance = clock_context()['provenance']

    def test_clock_context_is_linux_monotonic_with_separate_resolution(self):
        """Keep resolution separate from the clock error bound."""
        context = clock_context()
        self.assertEqual(context['clock'], 'CLOCK_MONOTONIC')
        self.assertEqual(len(context['provenance']), 64)
        self.assertGreater(context['clock_resolution_ns'], 0)
        self.assertTrue(context['boot_id'])
        self.assertTrue(context['time_namespace_inode'])

    def test_prepare_pair_is_exclusive_private_and_fixed_size(self):
        """Create each trace file once with fixed private dimensions."""
        files = prepare_trace_pair(
            self.directory, collection_id='collection-1',
        )
        self.assertEqual(
            [item['role'] for item in files], ['backend', 'observer'],
        )
        for item in files:
            info = os.stat(item['path'], follow_symlinks=False)
            self.assertEqual(info.st_ino, item['inode'])
            self.assertEqual(info.st_dev, item['device'])
            self.assertEqual(info.st_size, MAX_FILE_SIZE)
            self.assertEqual(os.stat(item['path']).st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            prepare_trace_pair(self.directory, collection_id='collection-1')

    def test_pair_requires_both_joined_and_exact_bound_identity(self):
        """Require joined writers and a matching pair binding."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        kwargs = {
            'session_id': 'session-1', 'config_hash': 'a' * 64,
            'world': 'b2_training_arena', 'collection_id': 'collection-1',
            'clock_provenance': self.provenance,
            'expected_backend_instance_id': 42,
            'allocated_files': (
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ),
            'join_evidence': _join_evidence(),
            'clock_domain_certificate': _clock_certificate(clock_context()),
            'clock_error_bound_proof': _clock_proof(clock_context()),
            'expected_clock_library_sha256': 'd' * 64,
            'readiness_backend_status': _readiness_binding(),
            'readiness_binding_verified': True,
        }
        with self.assertRaisesRegex(ValueError, 'joined'):
            read_trace_pair(backend, observer, joined=False, **kwargs)
        result = read_trace_pair(
            backend, observer, joined=True, requested_window=(100, 400),
            **kwargs,
        )
        self.assertTrue(result['trace_files_complete'], result['issues'])
        self.assertFalse(result['coverage_complete'])
        self.assertIsNone(result['analysis'])
        self.assertEqual(result['backend_instance_id'], 42)
        self.assertEqual(result['records']['backend'][0], (1, 1, 100, 0, b''))

    def test_instance_mismatch_returns_no_cross_session_records(self):
        """Reject records when the writers identify different instances."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', backend=42,
                       provenance=self.provenance)
        _write_fixture(observer, role='observer', backend=43,
                       provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            clock_error_bound_proof=_clock_proof(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['paired_records'], {})
        self.assertFalse(result['records'])
        self.assertTrue(result['raw_recovery_records']['backend'])
        self.assertTrue(result['raw_recovery_records']['observer'])
        self.assertIn(
            'writer_roles_or_backend_instance_mismatch', result['issues'],
        )

    def test_missing_window_keeps_structure_but_not_coverage(self):
        """Keep recoverable structure separate from window coverage."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            clock_error_bound_ns=0,
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['coverage_complete'])
        self.assertTrue(result['records']['backend'])
        self.assertTrue(any('coverage_window_missing' in issue
                            for issue in result['issues']))

    def test_cpp_header_roundtrips_through_existing_reader(self):
        """Read bytes emitted by the production C++ header."""
        compiler = shutil.which('g++')
        self.assertIsNotNone(compiler)
        repo = Path(__file__).resolve().parents[4]
        include = repo / 'ros2_ws/src/mecanum_sim_backend/include'
        source = self.directory / 'writer.cpp'
        binary = self.directory / 'writer'
        source.write_text(r"""#include \
<mecanum_sim_backend/heartbeat_trace_writer.hpp>
#include <fcntl.h>
#include <string>
#include <unistd.h>
int main(int argc, char **argv) {
  if (argc != 5) return 2;
  int fd = open(argv[1], O_RDWR | O_NOFOLLOW | O_CLOEXEC);
  if (fd < 0) return 3;
  const std::string uuid = "00000000-0000-0000-0000-000000000001";
  mecanum_sim_backend::heartbeat_trace::Writer writer(
      fd, 4, uuid, uuid, 42, std::string(64, 'a'), "b2_training_arena",
      "CLOCK_MONOTONIC", "backend", argv[4],
      std::stoull(argv[2]), std::stoull(argv[3]));
  if (!writer.append(1, 100, 0, nullptr, 0)) return 4;
  const unsigned char code = 1;
  if (!writer.append(2, 200, 7, &code, 1)) return 5;
  if (!writer.append(3, 400, 0, nullptr, 0)) return 6;
  close(fd);
  return 0;
}
        """, encoding='utf-8')
        subprocess.run([
            compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
            '-I', str(include), str(source), '-o', str(binary),
        ], check=True, capture_output=True, timeout=30)
        path = self.directory / 'production.hbtrace'
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                     0o600)
        try:
            os.fchmod(fd, 0o600)
            os.ftruncate(fd, HEADER_SIZE + 4 * RECORD_SIZE)
            info = os.fstat(fd)
        finally:
            os.close(fd)
        child = subprocess.run([
            str(binary), str(path), str(info.st_dev), str(info.st_ino),
            self.provenance,
        ], check=False, capture_output=True, timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr)
        result = read_trace_pair(
            path, self.directory / 'missing-observer.hbtrace',
            session_id='00000000-0000-0000-0000-000000000001',
            config_hash='a' * 64, world='b2_training_arena',
            collection_id='00000000-0000-0000-0000-000000000001',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(_allocation(path, 'backend'),),
            expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
        )
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(
            result.get('raw_recovery_records', {}).get('backend'),
            ((1, 1, 100, 0, b''), (2, 2, 200, 7, b'\x01'),
             (3, 3, 400, 0, b'')),
            result,
        )

    def test_header_agreement_is_not_independent_backend_identity(self):
        """Both writers agreeing cannot establish the accepted backend ID."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400), clock_error_bound_ns=0,
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=None,
            join_evidence=_join_evidence(),
        )
        self.assertEqual(result['paired_records'], {})
        self.assertFalse(result['coverage_complete'])

    def test_join_evidence_and_independent_instance_are_required(self):
        """Reject a pair without independently verified writer joins."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            clock_domain_certificate=_clock_certificate(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['coverage_complete'])
        self.assertIn(
            'observer_process_reap_or_group_absence_unverified',
            result['issues'],
        )

    def test_killed_observer_allows_only_raw_recovery_after_group_reap(self):
        """Reaped forced termination exposes raw bytes, not clean coverage."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        evidence = _join_evidence()
        evidence.update({
            'observer_exit_status': -9,
            'observer_stop_acknowledged': False,
            'observer_end_written': False,
            'observer_handle_closed': False,
            'observer_writer_closed': False,
            'observer_termination': 'SIGKILL',
        })
        kwargs = {
            'session_id': 'session-1', 'config_hash': 'a' * 64,
            'world': 'b2_training_arena', 'collection_id': 'collection-1',
            'clock_provenance': self.provenance,
            'expected_backend_instance_id': 42,
            'allocated_files': (
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ),
            'join_evidence': evidence,
            'clock_domain_certificate': _clock_certificate(clock_context()),
            'clock_error_bound_proof': _clock_proof(clock_context()),
            'expected_clock_library_sha256': 'd' * 64,
            'readiness_backend_status': _readiness_binding(),
            'readiness_binding_verified': True,
        }
        result = read_trace_pair(
            backend, observer, joined=True, requested_window=(100, 400),
            **kwargs,
        )
        self.assertTrue(result['raw_recovery_allowed'])
        self.assertTrue(result['raw_recovery_records']['backend'])
        self.assertTrue(result['raw_recovery_records']['observer'])
        self.assertEqual(result['records'], {})
        self.assertFalse(result['clean_close_verified'])
        self.assertFalse(result['trace_files_complete'])
        self.assertFalse(result['coverage_complete'])

    def test_inconsistent_end_and_handle_facts_block_raw_recovery(self):
        """A contradictory close summary cannot authorize trace recovery."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        evidence = _join_evidence()
        evidence.update({
            'observer_end_written': False,
            'observer_handle_closed': True,
            'observer_writer_closed': True,
        })
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=evidence,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['raw_recovery_allowed'])
        self.assertFalse(result['clean_close_verified'])
        self.assertFalse(result['coverage_complete'])

    def test_live_or_unreaped_observer_is_not_read(self):
        """Do not expose records until the process and group are reaped."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        evidence = _join_evidence()
        evidence['observer_process_joined'] = False
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=evidence,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['raw_recovery_allowed'])
        self.assertEqual(result['raw_recovery_records'], {})
        self.assertFalse(result['coverage_complete'])

    def test_substituted_inode_is_not_usable_even_with_matching_header(self):
        """Reject content read through a path with a substituted inode."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        allocated = (
            _allocation(backend, 'backend'),
            _allocation(observer, 'observer'),
        )
        replacement = self.directory / 'replacement.hbtrace'
        _write_fixture(
            replacement, role='observer', provenance=self.provenance,
        )
        result = read_trace_pair(
            backend, replacement, session_id='session-1',
            config_hash='a' * 64, world='b2_training_arena',
            collection_id='collection-1', clock_provenance=self.provenance,
            joined=True, requested_window=(100, 400),
            allocated_files=allocated, expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['coverage_complete'])
        self.assertFalse(result['records'])
        self.assertTrue(any('allocated_file_identity_mismatch' in issue
                            for issue in result['issues']))

    def test_replaced_matching_headers_fail_allocation_binding(self):
        """Reject two mutually matching files that lack allocated identity."""
        original_backend = self.directory / 'backend.hbtrace'
        original_observer = self.directory / 'observer.hbtrace'
        _write_fixture(
            original_backend, role='backend', provenance=self.provenance,
        )
        _write_fixture(
            original_observer, role='observer', provenance=self.provenance,
        )
        allocated = (
            _allocation(original_backend, 'backend'),
            _allocation(original_observer, 'observer'),
        )
        replacement_backend = self.directory / 'replacement-backend.hbtrace'
        replacement_observer = self.directory / 'replacement-observer.hbtrace'
        _write_fixture(
            replacement_backend, role='backend', backend=99,
            provenance=self.provenance,
        )
        _write_fixture(
            replacement_observer, role='observer', backend=99,
            provenance=self.provenance,
        )
        result = read_trace_pair(
            replacement_backend, replacement_observer,
            session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400), allocated_files=allocated,
            expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['coverage_complete'])
        self.assertFalse(result['records'])
        self.assertFalse(result['paired_records'])

    def test_wrong_session_headers_are_raw_recovery_only(self):
        """Keep stale-session data out of the usable record set."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', session='stale-session',
                       provenance=self.provenance)
        _write_fixture(observer, role='observer', session='stale-session',
                       provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['records'])
        self.assertFalse(result['coverage_complete'])

    def test_hbtrace_bytes_decode_to_analyzer_without_fabricated_receive(self):
        """Decode supported HBTRACE1 facts without inventing receive events."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(
            backend, role='backend', provenance=self.provenance,
            records=((1, 100), (2, 120, 8, b'\x01'),
                     (2, 130, 8, b'\x02'), (3, 1_000_000_500)),
        )
        _write_fixture(
            observer, role='observer', provenance=self.provenance,
            records=((1, 100), (2, 140, 8, b'\x06\x00'),
                     (2, 150, 8, b'\x07\x01'),
                     (2, 151, 8, b'\x0a\x01'),
                     (2, 1_000_000_500, 8, b'\x08\x01'),
                     (3, 1_000_000_600)),
        )
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 1_000_000_500),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            clock_error_bound_proof=_clock_proof(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertEqual(len(result['analyzer_events']), 5)
        self.assertIsNotNone(result['analysis'])
        self.assertEqual(result['analysis'].cause.value, 'unknown')

    def test_clock_uncertainty_must_fit_both_coverage_edges(self):
        """Require certified uncertainty to fit each requested window edge."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        kwargs = {
            'session_id': 'session-1', 'config_hash': 'a' * 64,
            'world': 'b2_training_arena', 'collection_id': 'collection-1',
            'clock_provenance': self.provenance, 'joined': True,
            'allocated_files': (
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), 'expected_backend_instance_id': 42,
            'join_evidence': _join_evidence(),
            'clock_domain_certificate': _clock_certificate(
                clock_context(), width=10,
            ),
            'clock_error_bound_proof': _clock_proof(
                clock_context(), bound=10,
            ),
            'expected_clock_library_sha256': 'd' * 64,
            'readiness_backend_status': _readiness_binding(),
            'readiness_binding_verified': True,
        }
        begin_overlap = read_trace_pair(
            backend, observer, requested_window=(100, 390), **kwargs,
        )
        self.assertFalse(begin_overlap['coverage_complete'])
        self.assertIn(
            'coverage_uncertainty_overlaps_requested_window_edge',
            begin_overlap['issues'],
        )
        end_overlap = read_trace_pair(
            backend, observer, requested_window=(90, 400), **kwargs,
        )
        self.assertFalse(end_overlap['coverage_complete'])

    def test_setup_bracket_alone_is_not_a_record_timestamp_error_bound(self):
        """Preserve raw bytes but do not promote observed setup jitter."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_legacy_setup_bracket(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(result['coverage_complete'])
        self.assertIsNone(result['clock_error_bound_ns'])
        self.assertTrue(result['raw_recovery_records']['backend'])

    def test_clock_context_mismatch_keeps_raw_recovery_without_coverage(self):
        """Clock mismatch preserves raw bytes but blocks diagnosis."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        foreign_clock = {
            **clock_context(), 'provenance': 'f' * 64,
            'boot_id': 'foreign-boot',
        }
        with patch('heartbeat_trace_session.clock_context',
                   return_value=foreign_clock):
            result = read_trace_pair(
                backend, observer, session_id='session-1',
                config_hash='a' * 64, world='b2_training_arena',
                collection_id='collection-1',
                clock_provenance=self.provenance, joined=True,
                requested_window=(100, 400),
                allocated_files=(
                    _allocation(backend, 'backend'),
                    _allocation(observer, 'observer'),
                ), expected_backend_instance_id=42,
                join_evidence=_join_evidence(),
                readiness_backend_status=_readiness_binding(),
                readiness_binding_verified=True,
            )
        self.assertFalse(result['clock_domain_verified'])
        self.assertFalse(result['coverage_complete'])
        self.assertTrue(result['raw_recovery_records']['backend'])
        self.assertTrue(result['raw_recovery_records']['observer'])

    def test_hbtrace_bytes_prove_no_publish_only_inside_window(self):
        """Derive an in-window diagnosis from complete trace bytes."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        baseline = 100
        check = baseline + 1_000_000_001
        _write_fixture(
            backend, role='backend', provenance=self.provenance,
            records=((1, 1), (3, check + 100)),
        )
        _write_fixture(
            observer, role='observer', provenance=self.provenance,
            records=(
                (1, 1), (2, baseline, 3, b'\x06\x00'),
                (2, baseline + 1, 3, b'\x07\x01'),
                (2, baseline + 1, 3, b'\x0a\x01'),
                (2, check, 3, b'\x08\x01'), (3, check + 100),
            ),
        )
        result = self._read_bound_pair(
            backend, observer, requested_window=(baseline, check),
        )
        self.assertTrue(result['coverage_complete'], result['issues'])
        self.assertEqual(result['analysis'].cause, Cause.NO_PUBLISH_ATTEMPT)
        self.assertEqual(len(result['analysis'].supporting_events), 3)

    def test_out_of_window_check_and_publish_cannot_prove_absence(self):
        """Do not let out-of-window checks prove publish absence."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        baseline = 100
        check = baseline + 1_000_000_001
        _write_fixture(
            backend, role='backend', provenance=self.provenance,
            records=(
                (1, 1), (2, baseline + 10, 4, b'\x01'),
                (2, baseline + 11, 4, b'\x02'), (3, check + 100),
            ),
        )
        _write_fixture(
            observer, role='observer', provenance=self.provenance,
            records=(
                (1, 1), (2, baseline, 3, b'\x06\x00'),
                (2, baseline + 1, 3, b'\x07\x01'),
                (2, baseline + 1, 3, b'\x0a\x01'),
                (2, check + 1, 3, b'\x08\x01'), (3, check + 100),
            ),
        )
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(baseline, check),
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            clock_error_bound_proof=_clock_proof(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )
        self.assertFalse(any(
            event.kind.value == 'heartbeat_check'
            for event in result['analyzer_events']
        ))
        self.assertEqual(result['analysis'].cause, Cause.UNKNOWN)
        self.assertIn(
            'heartbeat check is missing', result['analysis'].reason,
        )

    def _read_bound_pair(self, backend, observer, *, requested_window):
        return read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=requested_window,
            allocated_files=(
                _allocation(backend, 'backend'),
                _allocation(observer, 'observer'),
            ), expected_backend_instance_id=42,
            join_evidence=_join_evidence(),
            clock_domain_certificate=_clock_certificate(clock_context()),
            clock_error_bound_proof=_clock_proof(clock_context()),
            expected_clock_library_sha256='d' * 64,
            readiness_backend_status=_readiness_binding(),
            readiness_binding_verified=True,
        )

    def test_plain_integer_is_not_clock_error_bound_evidence(self):
        """A caller-supplied integer does not prove either coverage edge."""
        backend = self.directory / 'backend.hbtrace'
        observer = self.directory / 'observer.hbtrace'
        _write_fixture(backend, role='backend', provenance=self.provenance)
        _write_fixture(observer, role='observer', provenance=self.provenance)
        result = read_trace_pair(
            backend, observer, session_id='session-1', config_hash='a' * 64,
            world='b2_training_arena', collection_id='collection-1',
            clock_provenance=self.provenance, joined=True,
            requested_window=(100, 400), clock_error_bound_ns=0,
        )
        self.assertIn('clock_error_bound_unverified', result['issues'])
        self.assertFalse(result['coverage_complete'])


if __name__ == '__main__':
    unittest.main()


class CurrentSupervisorJoinSchemaTests(unittest.TestCase):
    def test_known_empty_signal_history_preserves_clean_join(self):
        from heartbeat_trace_session import _valid_clean_join_evidence
        evidence = {**_join_evidence(), 'observer_signal_dispatches': []}
        self.assertTrue(_valid_clean_join_evidence(evidence))
        self.assertFalse(_valid_clean_join_evidence({**evidence, 'unknown': True}))
        self.assertFalse(_valid_clean_join_evidence({**evidence, 'observer_signal_dispatches': False}))

    def test_dispatched_signal_cannot_be_claimed_as_cooperative_clean_join(self):
        from heartbeat_trace_session import _valid_clean_join_evidence
        evidence = {**_join_evidence(), 'observer_signal_dispatches': [{
            'signal': 'SIGTERM', 'identity_verified': True,
            'raw_exit_status_before_dispatch': None, 'outcome': 'DISPATCHED',
        }]}
        self.assertFalse(_valid_clean_join_evidence(evidence))
