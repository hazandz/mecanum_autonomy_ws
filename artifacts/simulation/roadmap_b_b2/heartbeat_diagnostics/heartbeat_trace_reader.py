"""Read the standalone file-backed prototype only after its writer is joined."""

from dataclasses import dataclass
import os
from pathlib import Path
import struct
import zlib

HEADER_SIZE = 320
RECORD_SIZE = 96
MAX_CAPACITY = 4096
HEADER_MARKER = 0x48445231
RECORD_MARKER = 0x434F4D54


@dataclass(frozen=True)
class ReadResult:
    records: tuple
    structure_valid: bool
    coverage_complete: bool
    issues: tuple


def _text(data):
    raw = data.split(b'\0', 1)[0]
    if not raw or data[len(raw):].strip(b'\0'):
        raise ValueError('invalid header field')
    return raw.decode('ascii')


def read_after_join(path, *, expected, requested_window=None, clock_verified=False):
    """Return recovered records and independent completeness; caller owns join."""
    path = Path(path)
    with path.open('rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if size < HEADER_SIZE or size > HEADER_SIZE + MAX_CAPACITY * RECORD_SIZE:
            raise ValueError('file size outside bounds')
        data = stream.read(size + 1)
    if len(data) != size or data[:8] != b'HBTRACE1':
        raise ValueError('truncated or invalid file')
    version, hsize, rsize, capacity = struct.unpack_from('<IIII', data, 8)
    if (version != 1 or hsize != HEADER_SIZE or rsize != RECORD_SIZE
            or not 1 <= capacity <= MAX_CAPACITY
            or size != HEADER_SIZE + capacity * RECORD_SIZE):
        raise ValueError('invalid dimensions or truncated file')
    overflow, stored_crc, marker = struct.unpack_from('<III', data, 304)
    if marker != HEADER_MARKER or stored_crc != zlib.crc32(data[:304]):
        raise ValueError('incomplete or corrupt header')
    identity = {
        'collection': _text(data[24:60]), 'session': _text(data[60:96]),
        'backend': struct.unpack_from('<Q', data, 96)[0],
        'config': _text(data[104:168]), 'world': _text(data[168:200]),
        'clock': _text(data[200:232]), 'role': _text(data[232:240]),
        'provenance': _text(data[240:304]),
    }
    identity_matches = bool(identity['backend']) and identity == expected
    structural_issues = []
    records = []
    for index in range(capacity):
        slot = data[HEADER_SIZE + index * RECORD_SIZE:HEADER_SIZE + (index + 1) * RECORD_SIZE]
        if not any(slot):
            continue
        seq, kind, length, timestamp, status_seq = struct.unpack_from('<QIIQQ', slot)
        checksum, marker = struct.unpack_from('<II', slot, 88)
        if marker != RECORD_MARKER:
            structural_issues.append(f'incomplete_slot:{index}')
            continue
        if length > 56 or checksum != zlib.crc32(slot[:88]):
            structural_issues.append(f'corrupt_slot:{index}')
            continue
        if seq != index + 1:
            structural_issues.append(f'sequence_gap:{index}')
            continue
        if kind not in (1, 2, 3):
            structural_issues.append(f'unknown_kind:{index}')
            continue
        records.append((seq, kind, timestamp, status_seq, slot[32:32 + length]))
    if [r[0] for r in records] != list(range(1, len(records) + 1)):
        structural_issues.append('record_sequence_incomplete')
    kinds = [r[1] for r in records]
    if not kinds or kinds[0] != 1 or kinds[-1] != 3 or kinds.count(1) != 1 or kinds.count(3) != 1:
        structural_issues.append('missing_or_invalid_boundaries')
    structure_valid = not structural_issues
    issues = list(structural_issues)
    if not identity_matches:
        issues.append('identity_or_clock_mismatch')
    if overflow:
        issues.append('overflow_or_invalid_flag')
    if any(first[2] > second[2] for first, second in zip(records, records[1:])):
        issues.append('timestamp_regression')
    if clock_verified is not True:
        issues.append('clock_not_verified')
    if requested_window is None:
        issues.append('coverage_window_missing')
    elif (
        not isinstance(requested_window, (tuple, list)) or len(requested_window) != 2
        or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in requested_window)
        or requested_window[0] > requested_window[1]
    ):
        issues.append('coverage_window_invalid')
    elif (not structure_valid or not records or records[0][2] > requested_window[0]
          or requested_window[1] > records[-1][2]):
        issues.append('coverage_window_outside_boundaries')
    return ReadResult(tuple(records) if identity_matches else (), structure_valid,
                      not issues, tuple(issues))
