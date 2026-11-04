"""Offline cross-language tests; child processes are owned and joined here."""

import os
import inspect
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


def read_request(path, *, expected=EXPECTED, requested_window=(100, 400)):
    kwargs = {'expected': expected}
    if 'requested_window' in inspect.signature(read_after_join).parameters:
        kwargs.update(requested_window=requested_window, clock_verified=True)
    return read_after_join(path, **kwargs)


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
        return read_request(self.path)

    def mutate(self, offset, payload):
        with self.path.open('r+b') as stream:
            stream.seek(offset)
            stream.write(payload)

    def rewrite_record(self, index, *, timestamp=None, seq=None, kind=None):
        raw = bytearray(self.path.read_bytes())
        start = HEADER_SIZE + index * RECORD_SIZE
        if timestamp is not None:
            struct.pack_into('<Q', raw, start + 16, timestamp)
        if seq is not None:
            struct.pack_into('<Q', raw, start, seq)
        if kind is not None:
            struct.pack_into('<I', raw, start + 8, kind)
        struct.pack_into('<I', raw, start + 88, zlib.crc32(raw[start:start + 88]))
        self.path.write_bytes(raw)

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
                self.assertEqual(result.records, ())
                self.assertIn('identity_or_clock_mismatch', result.issues)

    def test_missing_end_is_incomplete(self):
        self.write_child()
        self.mutate(HEADER_SIZE + 2 * RECORD_SIZE, bytes(RECORD_SIZE))
        result = read_after_join(self.path, expected=EXPECTED)
        self.assertEqual(len(result.records), 2)
        self.assertFalse(result.coverage_complete)
        self.assertIn('missing_or_invalid_boundaries', result.issues)

    def test_reversed_end_timestamp_is_not_coverage(self):
        self.write_child()
        self.rewrite_record(2, timestamp=50)
        result = read_request(self.path, requested_window=(100, 200))
        self.assertFalse(result.coverage_complete)

    def test_intermediate_timestamp_regression_is_not_coverage(self):
        self.write_child()
        self.rewrite_record(1, timestamp=50)
        result = read_request(self.path, requested_window=(100, 200))
        self.assertFalse(result.coverage_complete)

    def test_window_outside_collection_is_not_coverage(self):
        self.write_child()
        for window in ((99, 400), (100, 401), (200, 100)):
            with self.subTest(window=window):
                result = read_request(self.path, requested_window=window)
                self.assertFalse(result.coverage_complete)

    def test_missing_window_does_not_confirm_coverage(self):
        self.write_child()
        result = read_request(self.path, requested_window=None)
        self.assertFalse(result.coverage_complete)
        self.assertTrue(result.structure_valid)
        self.assertIn('coverage_window_missing', result.issues)
        self.assertEqual(len(result.records), 3)

    def test_unverified_clock_does_not_confirm_coverage(self):
        self.write_child()
        result = read_after_join(self.path, expected=EXPECTED, requested_window=(100, 400))
        self.assertTrue(result.structure_valid)
        self.assertFalse(result.coverage_complete)
        self.assertIn('clock_not_verified', result.issues)

    def test_equal_window_boundaries_are_covered(self):
        self.write_child()
        for window in ((100, 400), (100, 100), (400, 400)):
            with self.subTest(window=window):
                self.assertTrue(read_request(self.path, requested_window=window).coverage_complete)

    def test_bad_sequence_and_unknown_kind_are_not_valid_records(self):
        self.write_child()
        self.rewrite_record(1, seq=9)
        result = read_request(self.path)
        self.assertNotIn(9, [r[0] for r in result.records])
        self.assertEqual([r[0] for r in result.records], [1, 3])
        self.assertIn('sequence_gap:1', result.issues)
        self.rewrite_record(1, seq=2, kind=99)
        result = read_request(self.path)
        self.assertNotIn(99, [r[1] for r in result.records])
        self.assertEqual([r[0] for r in result.records], [1, 3])
        self.assertIn('unknown_kind:1', result.issues)

    def test_identity_mismatch_returns_no_usable_records(self):
        self.write_child()
        result = read_request(self.path, expected=dict(EXPECTED, session='wrong'))
        self.assertFalse(result.coverage_complete)
        self.assertEqual(result.records, ())


if __name__ == '__main__':
    unittest.main()
