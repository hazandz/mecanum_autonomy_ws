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
    coverage_complete: bool
    issues: tuple


def _text(data):
    raw = data.split(b'\0', 1)[0]
    if not raw or data[len(raw):].strip(b'\0'):
        raise ValueError('invalid header field')
    return raw.decode('ascii')


def read_after_join(path, *, expected):
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
    issues = []
    if not identity['backend'] or identity != expected:
        issues.append('identity_or_clock_mismatch')
    if overflow:
        issues.append('overflow_or_invalid_flag')
    records = []
    for index in range(capacity):
        slot = data[HEADER_SIZE + index * RECORD_SIZE:HEADER_SIZE + (index + 1) * RECORD_SIZE]
        if not any(slot):
            continue
        seq, kind, length, timestamp, status_seq = struct.unpack_from('<QIIQQ', slot)
        checksum, marker = struct.unpack_from('<II', slot, 88)
        if marker != RECORD_MARKER:
            issues.append(f'incomplete_slot:{index}')
            continue
        if length > 56 or checksum != zlib.crc32(slot[:88]):
            issues.append(f'corrupt_slot:{index}')
            continue
        if seq != index + 1:
            issues.append(f'sequence_gap:{index}')
        if kind not in (1, 2, 3):
            issues.append(f'unknown_kind:{index}')
        records.append((seq, kind, timestamp, status_seq, slot[32:32 + length]))
    if [r[0] for r in records] != list(range(1, len(records) + 1)):
        issues.append('record_sequence_incomplete')
    kinds = [r[1] for r in records]
    if not kinds or kinds[0] != 1 or kinds[-1] != 3 or kinds.count(1) != 1 or kinds.count(3) != 1:
        issues.append('missing_or_invalid_boundaries')
    return ReadResult(tuple(records), not issues, tuple(issues))
