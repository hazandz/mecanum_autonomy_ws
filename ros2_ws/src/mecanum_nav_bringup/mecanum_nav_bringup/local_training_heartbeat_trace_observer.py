"""Opt-in, diagnostic-only observer for backend heartbeat timestamps.

Imports in this module do not initialize ROS or load the native writer. Those
side effects occur only after an explicit supervisor start request.
"""
from __future__ import annotations

import asyncio
import ctypes
import hashlib
import os
import stat
import threading
import time
from pathlib import Path

HEARTBEAT_THRESHOLD_NS = 1_000_000_000
TRACE_CAPACITY = 4096
HEADER_SIZE = 320
RECORD_SIZE = 96
TRACE_DATA_KIND = 2
EVENT_CALLBACK_ENTRY = 6
EVENT_STATUS_VALIDATION = 7
EVENT_HEARTBEAT_CHECK = 8


def clock_context():
    """Fingerprint monotonic boot and time-namespace context."""
    from pathlib import Path

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


def prepare_trace_pair(directory, *, collection_id):
    """Prepare two exclusive no-follow files in an existing 0700 directory."""
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
    files = []
    for role in ('backend', 'observer'):
        path = directory / f'{role}.hbtrace'
        fd = os.open(
            path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW
            | os.O_CLOEXEC, 0o600,
        )
        try:
            os.fchmod(fd, 0o600)
            os.ftruncate(fd, HEADER_SIZE + TRACE_CAPACITY * RECORD_SIZE)
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise ValueError('trace file identity or mode invalid')
            files.append({
                'role': role, 'path': str(path), 'device': info.st_dev,
                'inode': info.st_ino, 'size': info.st_size,
            })
        finally:
            os.close(fd)
    return tuple(files)


def _load_api(library_path):
    library = ctypes.CDLL(str(Path(library_path).resolve(strict=True)))
    writer = ctypes.c_void_p
    library.hbtrace_open_path.argtypes = [
        ctypes.c_char_p, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint32,
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint64, ctypes.c_char_p,
        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
    ]
    library.hbtrace_open_path.restype = writer
    library.hbtrace_append.argtypes = [
        writer, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t,
    ]
    library.hbtrace_append.restype = ctypes.c_int
    library.hbtrace_close.argtypes = [writer]
    library.hbtrace_close.restype = None
    library.hbtrace_clock_monotonic_ns.argtypes = []
    library.hbtrace_clock_monotonic_ns.restype = ctypes.c_uint64
    return library


class LocalTrainingHeartbeatTraceObserver:
    """Own one optional rclpy subscription and one observer trace writer."""

    def __init__(
        self, *, plan, trace_file, collection_id, clock_provenance,
        library_path, api_loader=_load_api, ready_timeout_s=1.0,
    ):
        """Bind the plan and lazy native API loader for an opt-in observer."""
        self.plan = plan
        self.trace_file = dict(trace_file)
        self.collection_id = collection_id
        self.clock_provenance = clock_provenance
        self.library_path = library_path
        self.api_loader = api_loader
        self.ready_timeout_s = ready_timeout_s
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._thread = None
        self._stop = threading.Event()
        self._api = None
        self._writer = None
        self._writer_was_opened = False
        self._context = None
        self._node = None
        self._executor = None
        self._timer = None
        self._backend_id = None
        self._last_accepted_ns = None
        self._last_accepted_sequence = None
        self._expired_recorded = False
        self._errors = []
        self._started = False
        self._joined = False

    def start(self):
        """Load the pinned native API and start an isolated executor thread."""
        if self._started:
            raise RuntimeError('heartbeat observer already started')
        self._started = True
        try:
            self._api = self.api_loader(self.library_path)
        except BaseException as error:
            self._append_error(f'native_library:{type(error).__name__}')
            self._ready.set()
            return False
        self._thread = threading.Thread(
            target=self._thread_main, name='b2-heartbeat-trace', daemon=False,
        )
        self._thread.start()
        return True

    def _thread_main(self):
        try:
            from rclpy.context import Context
            from rclpy.executors import SingleThreadedExecutor
            from rclpy.node import Node
            from mecanum_nav_rl_interfaces.msg import SimulationContactState

            self._context = Context()
            self._context.init(args=None)
            self._node = Node(
                'b2_heartbeat_trace_observer', context=self._context,
            )
            self._executor = SingleThreadedExecutor(context=self._context)
            self._executor.add_node(self._node)
            self._node.create_subscription(
                SimulationContactState,
                '/mecanum/local_training/backend_state',
                self._on_status, 50,
            )
            self._timer = self._node.create_timer(0.05, self._check_heartbeat)
            self._ready.set()
            while not self._stop.is_set() and self._context.ok():
                self._executor.spin_once(timeout_sec=0.05)
        except BaseException as error:
            self._append_error(f'observer_loop:{type(error).__name__}')
            self._ready.set()
        finally:
            try:
                self._close_writer()
            except BaseException as error:
                self._append_error(
                    f'trace_writer_close:{type(error).__name__}'
                )
            if self._executor is not None:
                try:
                    self._executor.shutdown(timeout_sec=0.1)
                except BaseException as error:
                    self._append_error(
                        f'executor_shutdown:{type(error).__name__}'
                    )
            if self._node is not None:
                try:
                    self._node.destroy_node()
                except BaseException as error:
                    self._append_error(f'node_destroy:{type(error).__name__}')
            if self._context is not None and self._context.ok():
                try:
                    self._context.shutdown()
                except BaseException as error:
                    self._append_error(
                        f'context_shutdown:{type(error).__name__}'
                    )
            self._joined = True

    def _append_error(self, message):
        with self._lock:
            if len(self._errors) < 32:
                self._errors.append(str(message)[:160])

    def _clock(self):
        if self._api is None:
            return 0
        return int(self._api.hbtrace_clock_monotonic_ns())

    def _open_writer(self, backend_id, begin_timestamp_ns):
        entry = self.trace_file
        self._writer = self._api.hbtrace_open_path(
            entry['path'].encode(), entry['device'], entry['inode'],
            TRACE_CAPACITY, self.collection_id.encode(),
            self.plan.session_id.encode(), backend_id,
            self.plan.config_hash.encode(), b'b2_training_arena',
            b'CLOCK_MONOTONIC', self.clock_provenance.encode(), b'observer',
        )
        if not self._writer:
            self._append_error('observer_trace_open_failed')
            return False
        self._writer_was_opened = True
        if self._api.hbtrace_append(
                self._writer, 1, begin_timestamp_ns, 0, None, 0) != 1:
            self._append_error('observer_trace_begin_failed')
            self._close_writer()
            return False
        return True

    def _append_event(self, event_code, timestamp, sequence, flags=0):
        if not self._writer:
            return False
        payload = (ctypes.c_ubyte * 2)(event_code, flags)
        if self._api.hbtrace_append(
                self._writer, TRACE_DATA_KIND, timestamp, sequence,
                payload, len(payload)) != 1:
            self._append_error('observer_trace_append_failed_or_overflow')
            return False
        return True

    def _on_status(self, message):
        callback_ns = self._clock()
        session = str(message.session_id)
        if session != self.plan.session_id:
            return
        backend_id = int(message.backend_instance_id)
        sequence = int(message.status_sequence)
        if (
            str(message.config_hash) != self.plan.config_hash
            or str(message.header.frame_id) != 'b2_training_arena'
            or backend_id <= 0
            or sequence <= 0
            or callback_ns <= 0
        ):
            self._append_error('status_binding_or_clock_invalid')
            return
        if self._backend_id is None:
            self._backend_id = backend_id
            if not self._open_writer(backend_id, callback_ns):
                return
        elif backend_id != self._backend_id:
            self._append_error('backend_instance_changed_within_session')
            return

        if self._last_accepted_ns is not None and not self._expired_recorded:
            gap = callback_ns - self._last_accepted_ns
            if gap > HEARTBEAT_THRESHOLD_NS:
                self._append_event(EVENT_HEARTBEAT_CHECK, callback_ns,
                                   self._last_accepted_sequence or sequence, 1)
                self._expired_recorded = True
        self._append_event(EVENT_CALLBACK_ENTRY, callback_ns, sequence)
        accepted = (
            bool(message.paused) and bool(message.actuator_inhibited)
            and int(message.fault_flags) == 0
            and not bool(message.applied_receipt_valid)
        )
        validation_ns = self._clock()
        flags = 1 if accepted else 0
        self._append_event(
            EVENT_STATUS_VALIDATION, validation_ns, sequence, flags,
        )
        if accepted:
            self._last_accepted_ns = callback_ns
            self._last_accepted_sequence = sequence
            self._expired_recorded = False

    def _check_heartbeat(self):
        if (self._writer is None or self._last_accepted_ns is None
                or self._expired_recorded):
            return
        now = self._clock()
        if now <= 0:
            self._append_error('heartbeat_clock_invalid')
            return
        if now - self._last_accepted_ns > HEARTBEAT_THRESHOLD_NS:
            self._append_event(
                EVENT_HEARTBEAT_CHECK, now,
                self._last_accepted_sequence or 0, 1,
            )
            self._expired_recorded = True

    def _close_writer(self):
        writer, self._writer = self._writer, None
        if writer:
            try:
                closed = self._api.hbtrace_append(
                    writer, 3, self._clock(), 0, None, 0,
                )
                if closed != 1:
                    self._append_error('observer_trace_end_failed_or_overflow')
            finally:
                self._api.hbtrace_close(writer)

    def stop(self, timeout_s=2.0):
        """Stop and boundedly join the owned executor thread."""
        if self._thread is None:
            self._joined = True
            return True
        self._stop.set()
        if self._context is not None and self._context.ok():
            try:
                self._context.shutdown()
            except BaseException as error:
                self._append_error(f'context_stop:{type(error).__name__}')
        self._thread.join(timeout_s)
        if self._thread.is_alive():
            self._append_error('observer_thread_residue_unknown')
            return False
        self._joined = True
        return True

    async def stop_async(self, timeout_s=2.0):
        """Signal the executor and join without blocking the owner loop."""
        if self._thread is None:
            self._joined = True
            return True
        self._stop.set()
        deadline = time.monotonic() + max(0.0, timeout_s)
        while self._thread.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._append_error('observer_thread_residue_unknown')
                return False
            await asyncio.sleep(min(0.01, remaining))
        self._thread.join(0)
        self._joined = True
        return True

    def snapshot(self):
        """Return a bounded snapshot of observer identity and errors."""
        with self._lock:
            return {
                'backend_instance_id': self._backend_id,
                'joined': self._joined,
                'errors': tuple(self._errors),
                'writer_opened': self._writer_was_opened,
            }
