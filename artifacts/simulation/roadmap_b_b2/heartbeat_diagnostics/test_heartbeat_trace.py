"""Offline cross-language tests; child processes are owned and joined here."""

import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

from heartbeat_trace_reader import HEADER_SIZE, RECORD_SIZE, read_after_join

HERE = Path(__file__).resolve().parent
EXPECTED = {
    'collection': 'collection-1', 'session': 'session-1', 'backend': 42,
    'config': 'config-1', 'world': 'world-1', 'clock': 'fake-monotonic',
    'role': 'backend', 'provenance': 'fixture-clock-v1',
}


class TraceBufferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='heartbeat-trace-test-')
        cls.binary = Path(cls.temp.name) / 'writer'
        subprocess.run([
            'g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
            str(HERE / 'test_heartbeat_trace_buffer.cpp'), '-o', str(cls.binary),
        ], check=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_case = tempfile.TemporaryDirectory(prefix='heartbeat-trace-case-')
        self.addCleanup(self.temp_case.cleanup)
        self.path = Path(self.temp_case.name) / 'trace.bin'

    def write_child(self, mode='normal'):
        result = subprocess.run([str(self.binary), str(self.path), mode],
                                check=False, timeout=5, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return read_after_join(self.path, expected=EXPECTED)

    def mutate(self, offset, payload):
        with self.path.open('r+b') as stream:
            stream.seek(offset)
            stream.write(payload)

    def test_normal_roundtrip_exact_values_and_boundaries(self):
        result = self.write_child()
        self.assertTrue(result.coverage_complete, result.issues)
        self.assertEqual(result.records, ((1, 1, 100, 0, b'begin'),
                                         (2, 2, 200, 7, b'status'),
                                         (3, 3, 400, 0, b'end')))
        raw = self.path.read_bytes()
        self.assertEqual(raw[:8], b'HBTRACE1')
        self.assertEqual(struct.unpack_from('<IIII', raw, 8), (1, HEADER_SIZE, RECORD_SIZE, 4))
        self.assertEqual(struct.unpack_from('<QIIQQ', raw, HEADER_SIZE + RECORD_SIZE),
                         (2, 2, 6, 200, 7))
        self.assertEqual(raw[HEADER_SIZE + RECORD_SIZE + 32:
                             HEADER_SIZE + RECORD_SIZE + 38], b'status')
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_existing_file_is_not_reinitialized(self):
        result = self.write_child('reuse')
        self.assertTrue(result.coverage_complete, result.issues)
        self.assertEqual(result.records[1][4], b'status')

    def test_abrupt_exit_after_commit_recovers_completed_records(self):
        result = self.write_child('abrupt')
        self.assertTrue(result.coverage_complete, result.issues)
        self.assertEqual(result.records[1], (2, 2, 200, 7, b'status'))

    def test_abrupt_exit_before_commit_preserves_previous_records(self):
        result = self.write_child('partial')
        self.assertEqual([r[0] for r in result.records], [1, 2])
        self.assertFalse(result.coverage_complete)
        self.assertIn('incomplete_slot:2', result.issues)
        self.assertIn('missing_or_invalid_boundaries', result.issues)

    def test_checksum_corruption_keeps_prior_records_but_not_coverage(self):
        self.write_child()
        self.mutate(HEADER_SIZE + RECORD_SIZE + 32, b'X')
        result = read_after_join(self.path, expected=EXPECTED)
        self.assertEqual(result.records[0][4], b'begin')
        self.assertFalse(result.coverage_complete)
        self.assertIn('corrupt_slot:1', result.issues)

    def test_truncated_file_rejected(self):
        self.write_child()
        with self.path.open('r+b') as stream:
            stream.truncate(HEADER_SIZE + RECORD_SIZE)
        with self.assertRaises(ValueError):
            read_after_join(self.path, expected=EXPECTED)

    def test_overflow_is_incomplete(self):
        result = self.write_child('overflow')
        self.assertFalse(result.coverage_complete)
        self.assertIn('overflow_or_invalid_flag', result.issues)

    def test_sequence_gap_is_incomplete_even_with_valid_checksum(self):
        self.write_child()
        raw = bytearray(self.path.read_bytes())
        start = HEADER_SIZE + RECORD_SIZE
        struct.pack_into('<Q', raw, start, 9)
        struct.pack_into('<I', raw, start + 88, zlib.crc32(raw[start:start + 88]))
        self.path.write_bytes(raw)
        result = read_after_join(self.path, expected=EXPECTED)
        self.assertFalse(result.coverage_complete)
        self.assertIn('sequence_gap:1', result.issues)

    def test_identity_and_clock_mismatch_are_incomplete(self):
        self.write_child()
        for field in ('session', 'clock'):
            with self.subTest(field=field):
                expected = dict(EXPECTED, **{field: 'wrong'})
                result = read_after_join(self.path, expected=expected)
                self.assertFalse(result.coverage_complete)
                self.assertIn('identity_or_clock_mismatch', result.issues)

    def test_missing_end_is_incomplete(self):
        self.write_child()
        self.mutate(HEADER_SIZE + 2 * RECORD_SIZE, bytes(RECORD_SIZE))
        result = read_after_join(self.path, expected=EXPECTED)
        self.assertEqual(len(result.records), 2)
        self.assertFalse(result.coverage_complete)
        self.assertIn('missing_or_invalid_boundaries', result.issues)


if __name__ == '__main__':
    unittest.main()
