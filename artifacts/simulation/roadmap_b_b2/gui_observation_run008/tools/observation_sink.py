"""Fail-closed append-only JSONL evidence sink for one GUI observation."""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


class ObservationEvidenceSink:
    """Write one new evidence stream and fsync every record."""

    def __init__(
        self, root: Path, run_id: str, session_id: str, *,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        open_fn=os.open,
    ) -> None:
        """Open a new exclusive evidence stream under the supplied root."""
        self.root = root
        self.run_id = run_id
        self.session_id = session_id
        self._monotonic_ns = monotonic_ns
        self._utc_now = utc_now
        self._lock = threading.Lock()
        self._sequence = 0
        self.events: list[str] = []
        path = root / 'observation.jsonl'
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND
        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW
        descriptor = open_fn(path, flags, 0o600)
        self._stream = os.fdopen(descriptor, 'a', encoding='utf-8')

    def record(self, event: str, facts: dict[str, object]) -> None:
        """Append and durably flush one correlated record or raise."""
        with self._lock:
            sequence = self._sequence + 1
            record = {
                'sequence': sequence,
                'steady_time_ns': self._monotonic_ns(),
                'utc_time': self._utc_now().astimezone(
                    timezone.utc,
                ).isoformat(timespec='microseconds'),
                'run_id': self.run_id,
                'session_id': self.session_id,
                'event': event,
                'facts': facts,
            }
            encoded = json.dumps(
                record, sort_keys=True, separators=(',', ':'),
                ensure_ascii=False, allow_nan=False,
            )
            self._stream.write(encoded + '\n')
            self._stream.flush()
            os.fsync(self._stream.fileno())
            self._sequence = sequence
            self.events.append(event)
            return sequence

    def close(self) -> None:
        """Close the append-only stream after all records are flushed."""
        self._stream.close()
