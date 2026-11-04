"""Offline tests for HBTRACE1 pair ownership and post-join reading."""
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

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
    for index, (kind, timestamp) in enumerate(records):
        start = HEADER_SIZE + index * RECORD_SIZE
        struct.pack_into('<QIIQQ', raw, start, index + 1, kind, 0,
                         timestamp, 0)
        struct.pack_into('<I', raw, start + 88,
                         zlib.crc32(raw[start:start + 88]))
        struct.pack_into('<I', raw, start + 92, 0x434F4D54)
    path.write_bytes(raw)
    os.chmod(path, 0o600)


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
        }
        with self.assertRaisesRegex(ValueError, 'joined'):
            read_trace_pair(backend, observer, joined=False, **kwargs)
        result = read_trace_pair(
            backend, observer, joined=True, requested_window=(100, 400),
            clock_error_bound_ns=0,
            **kwargs,
        )
        self.assertTrue(result['coverage_complete'], result['issues'])
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
        )
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(result['paired_records'], {})
        self.assertTrue(result['records']['backend'])
        self.assertTrue(result['records']['observer'])
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
        )
        self.assertFalse(result['coverage_complete'])
        self.assertEqual(
            result.get('records', {}).get('backend'),
            ((1, 1, 100, 0, b''), (2, 2, 200, 7, b'\x01'),
             (3, 3, 400, 0, b'')),
            result,
        )


if __name__ == '__main__':
    unittest.main()
