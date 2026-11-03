"""Single-run, paused GUI observation orchestration for B2.2."""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from collections import deque
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from observation_guard import (
    APPROVAL_PATH, CONFIG_HASH, EVIDENCE_ROOT, GUARD_PATH, GuardError,
    MANIFEST_SHA256, PACKET_PATH, RESOLVED_SHA256, RUN_ID, SCENARIO_SHA256,
    acquire_once, packet_bindings, sha256_bytes, sha256_file,
    strict_json_loads,
    validate_approval, validate_run_roots,
)

from observation_sink import ObservationEvidenceSink


TOOL_PATHS = {
    'observation_guard.py': Path(__file__).with_name('observation_guard.py'),
    'observation_sink.py': Path(__file__).with_name('observation_sink.py'),
    'observation_runner.py': Path(__file__).resolve(),
    'test_observation_packet.py': Path(__file__).with_name(
        'test_observation_packet.py',
    ),
}
SERVER_READY_S = 30.0
GUI_START_S = 30.0
REVIEW_CHECKPOINT_S = 60.0
OBSERVATION_S = 60.0
RUNTIME_CAP_S = 240.0
CLEANUP_CAP_S = 60.0
TOTAL_CAP_S = 300.0
HEARTBEAT_GAP_S = 1.0
CLOCK_READY_TIMEOUT_S = SERVER_READY_S
CLOCK_SAMPLE_GAP_S = 1.0
POLL_SLICE_S = 0.05
EXPECTED_ROS_NODES = {
    ('b22_gui_observation_observer', '/'),
    ('mecanum_sim_backend', '/'),
    ('robot_state_publisher', '/'), ('ros_gz_bridge', '/'),
}
STARTUP_TEMPORARY_ROS_NODES = {('b2_server_scene_readiness', '/')}


class ObservationFailure(RuntimeError):
    """A fail-closed runtime observation result."""


class ReviewInvalidated(ObservationFailure):
    """A Codex review checkpoint was invalidated and cannot be resumed."""


def enforce_runtime_cap(consumed_at: float, now: float) -> None:
    """Reject activity that exceeds the 240-second post-consume budget."""
    if now - consumed_at > RUNTIME_CAP_S:
        raise ObservationFailure('240 s runtime cap exceeded')


def classify_final_status(observation_passed, cleanup_errors):
    """Classify a completed automated observation after cleanup."""
    if cleanup_errors:
        return 'FAIL'
    return 'PASS' if observation_passed else 'FAIL'


def strict_gui_value(value: str) -> bool:
    """Parse only the exact lowercase ``true`` and ``false`` values."""
    if value not in ('true', 'false'):
        raise argparse.ArgumentTypeError(
            "gui must be exactly 'true' or 'false'",
        )
    return value == 'true'


def require_run_gui(gui: bool) -> None:
    """Require GUI mode for RUN004 before consuming its capacity-one guard."""
    if gui is not True:
        raise ObservationFailure('RUN004 requires --gui true before consume')


def preflight_desktop(
    stdin_isatty: bool, environ: dict[str, str], exists,
) -> None:
    """Require a discoverable X11/XWayland socket without Owner TTY input."""
    del stdin_isatty
    display = environ.get('DISPLAY', '')
    x11_socket = None
    if display:
        match = re.fullmatch(
            r'(?:(?:unix|localhost)?):([0-9]+)(?:\.[0-9]+)?', display,
        )
        if match:
            x11_socket = Path('/tmp/.X11-unix') / f'X{match.group(1)}'
    if x11_socket is None or not exists(x11_socket):
        raise ObservationFailure('RUN004 requires an X11/XWayland socket')
    if not exists('/usr/bin/xwininfo') or not exists('/usr/bin/xprop'):
        raise ObservationFailure('pinned X11 window tools are unavailable')
    if not environ.get('DISPLAY'):
        raise ObservationFailure('DISPLAY is required for Qt XCB capture')


def process_start_identity(pid: int, proc_root: Path = Path('/proc')) -> dict:
    """Read Linux PID, process-group, session and start-tick identity."""
    raw = (proc_root / str(pid) / 'stat').read_text(encoding='ascii')
    closing = raw.rfind(')')
    if closing < 0:
        raise ObservationFailure('malformed proc stat for owned process')
    fields = raw[closing + 2:].split()
    return {
        'pid': pid,
        'process_group_id': int(fields[2]),
        'session_id': int(fields[3]),
        'start_ticks': int(fields[19]),
    }


def _valid_owned_leader_identity(identity, pid):
    """Require a complete, typed identity for a newly owned session leader."""
    if not isinstance(identity, dict):
        return False
    for key in ('pid', 'process_group_id', 'session_id', 'start_ticks'):
        if type(identity.get(key)) is not int or identity[key] <= 0:
            return False
    return (identity['pid'] == pid
            and identity['process_group_id'] == pid
            and identity['session_id'] == pid)


def process_parent_pid(pid: int, proc_root: Path = Path('/proc')) -> int:
    """Read one process's parent PID from its current proc stat entry."""
    raw = (proc_root / str(pid) / 'stat').read_text(encoding='ascii')
    closing = raw.rfind(')')
    if closing < 0:
        raise ObservationFailure('malformed proc stat for owned process')
    fields = raw[closing + 2:].split()
    return int(fields[1])


def verify_host_dependencies(
    packet, *, module_importer=None, file_hasher=sha256_file,
    status_path=None, package_version_reader=None, python_executable=None,
    python_version=None, path_resolver=Path.resolve,
):
    """Check pinned Qt, X11 tools and Python module origins before consume."""
    import importlib
    importer = module_importer or importlib.import_module
    fingerprint = packet['installation']['dependency_fingerprints']
    qt = fingerprint['qt']
    desktop = fingerprint['desktop_tools']
    python = fingerprint['python']
    try:
        pyqt = importer('PyQt5')
        qtcore = importer('PyQt5.QtCore')
        qtgui = importer('PyQt5.QtGui')
        python_modules = {
            name: importer(name) for name in ('pydantic', 'numpy', 'pytest')
        }
        rclpy = importer('rclpy')
        gz_transport = importer('gz.transport13')
    except BaseException as error:
        raise ObservationFailure(
            f'host dependency import failed: {type(error).__name__}'
        ) from error
    actual_modules = {
        'PyQt5_origin': path_resolver(Path(pyqt.__file__), strict=True),
        'QtCore_origin': path_resolver(Path(qtcore.__file__), strict=True),
        'QtGui_origin': path_resolver(Path(qtgui.__file__), strict=True),
    }
    expected_modules = {
        'PyQt5_origin': qt['PyQt5_origin'],
        'QtCore_origin': qt['QtCore_origin'],
        'QtGui_origin': qt['QtGui_origin'],
    }
    for key, actual in actual_modules.items():
        expected = path_resolver(Path(expected_modules[key]), strict=True)
        if actual != expected:
            raise ObservationFailure(f'host module origin mismatch: {key}')
    hashes = {
        'PyQt5_sha256': file_hasher(actual_modules['PyQt5_origin']),
        'QtCore_sha256': file_hasher(actual_modules['QtCore_origin']),
        'QtGui_sha256': file_hasher(actual_modules['QtGui_origin']),
        'platform_plugin_sha256': file_hasher(
            path_resolver(Path(qt['platform_plugin']), strict=True)
        ),
    }
    for key, actual in hashes.items():
        if actual != qt[key]:
            raise ObservationFailure(f'host file fingerprint mismatch: {key}')
    if (qtcore.PYQT_VERSION_STR != qt['PyQt5_version']
            or qtcore.qVersion() != qt['Qt_version']):
        raise ObservationFailure('Qt/PyQt version fingerprint mismatch')
    for tool in ('xwininfo', 'xprop'):
        item = desktop[tool]
        path = path_resolver(Path(item['path']), strict=True)
        expected_path = path_resolver(Path(item['path']), strict=True)
        if path != expected_path:
            raise ObservationFailure(f'{tool} path fingerprint mismatch')
        if file_hasher(path) != item['sha256']:
            raise ObservationFailure(f'{tool} path/hash fingerprint mismatch')
    status_file = Path(status_path or '/var/lib/dpkg/status')
    expected_packages = dict(fingerprint['system_packages'])
    expected_packages.update({
        'x11-utils': desktop['xwininfo']['package_version'],
        'python3-pyqt5': desktop['python3_pyqt5_package_version'],
        'libqt5gui5t64': desktop['libqt5gui5t64_package_version'],
    })
    reader = package_version_reader or (
        lambda packages: _read_dpkg_versions(status_file, packages)
    )
    package_versions = reader(expected_packages)
    if package_versions != expected_packages:
        raise ObservationFailure(
            'desktop package version fingerprint mismatch'
        )
    readiness = fingerprint['readiness_worker_provenance']
    origin_checks = {
        'rclpy_origin': (rclpy, readiness['rclpy_origin']),
        'gz_transport_wrapper_origin': (
            gz_transport, readiness['gz_transport_wrapper_origin'],
        ),
    }
    for label, (module, expected_path) in origin_checks.items():
        actual_path = path_resolver(Path(module.__file__), strict=True)
        if actual_path != path_resolver(Path(expected_path), strict=True):
            raise ObservationFailure(
                f'readiness dependency origin mismatch: {label}'
            )
    readiness_hashes = {
        'rclpy_sha256': readiness['rclpy_origin'],
        'rclpy_executor_sha256': readiness['rclpy_executor_path'],
        'rclpy_context_sha256': readiness['rclpy_context_path'],
        'gz_transport_wrapper_sha256': readiness[
            'gz_transport_wrapper_origin'
        ],
        'gz_transport_native_sha256': readiness['gz_transport_native_origin'],
    }
    for label, path in readiness_hashes.items():
        if file_hasher(path_resolver(Path(path), strict=True)) != readiness[
            label
        ]:
            raise ObservationFailure(
                f'readiness dependency hash mismatch: {label}'
            )
    actual_executable = path_resolver(
        Path(python_executable or sys.executable), strict=True,
    )
    expected_executable = path_resolver(
        Path(python['executable']), strict=True,
    )
    if actual_executable != expected_executable:
        raise ObservationFailure('Python executable differs from packet')
    actual_python_version = python_version or sys.version.split()[0]
    if actual_python_version != python['version']:
        raise ObservationFailure('Python version differs from packet')
    actual_python_modules = python_modules
    for name, module in actual_python_modules.items():
        expected_module = python['modules'][name]
        actual_origin = path_resolver(
            Path(module.__file__), strict=True,
        )
        expected_origin = path_resolver(
            Path(expected_module['origin']), strict=True,
        )
        if (actual_origin != expected_origin
                or module.__version__ != expected_module['version']):
            raise ObservationFailure(f'{name} module fingerprint mismatch')
        actual_python_modules[name] = {
            'origin': str(actual_origin), 'version': module.__version__,
        }
    return {
        'qt': hashes,
        'qt_module_origins': {
            key: str(value) for key, value in actual_modules.items()
        },
        'python': {
            'executable': str(actual_executable),
            'version': actual_python_version,
            'modules': actual_python_modules,
        },
        'desktop_tools': {
            tool: {
                'path': str(path_resolver(Path(desktop[tool]['path']),
                                          strict=True)),
                'sha256': file_hasher(
                    path_resolver(Path(desktop[tool]['path']), strict=True)
                ),
            }
            for tool in ('xwininfo', 'xprop')
        },
        'system_packages': package_versions,
        'readiness_worker_provenance': {
            'rclpy_origin': str(path_resolver(
                Path(readiness['rclpy_origin']), strict=True,
            )),
            'rclpy_version': package_versions['ros-jazzy-rclpy'],
            'gz_transport_wrapper_origin': str(path_resolver(
                Path(readiness['gz_transport_wrapper_origin']), strict=True,
            )),
            'gz_transport_version': package_versions[
                'python3-gz-transport13'
            ],
        },
    }


def _read_dpkg_versions(status_file, expected_packages):
    """Read installed package versions from dpkg metadata without spawning."""
    records = Path(status_file).read_text(encoding='utf-8').split('\n\n')
    found = {}
    for record in records:
        fields = {}
        for line in record.splitlines():
            if line and not line[0].isspace() and ': ' in line:
                key, value = line.split(': ', 1)
                fields[key] = value
        name = fields.get('Package')
        if name in expected_packages and fields.get('Status') == (
                'install ok installed'):
            found[name] = fields.get('Version')
    if found != expected_packages:
        raise ObservationFailure('installed desktop package metadata mismatch')
    return found


def assert_packet_inputs(packet: dict, file_hashes: dict[str, str]) -> None:
    """Call the one canonical packet validator used by guard and runner."""
    return packet_bindings(packet, file_hashes)


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _host_identity() -> dict[str, str]:
    return {
        'hostname': socket.gethostname(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text(
            encoding='ascii',
        ).strip(),
    }


def _partition_for_pid(pid):
    """Read only the run partition from an owned process environment."""
    raw = Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    values = [item.partition(b'=')[2] for item in raw
              if item.startswith(b'GZ_PARTITION=')]
    if len(values) != 1:
        raise ObservationFailure('owned GUI has no unique GZ_PARTITION')
    return values[0].decode('utf-8', errors='strict')


async def _owned_helper(launcher, argv, environment, *, timeout_s, sink):
    """Run a short X11 helper in an owned group and retain its identity."""
    process = await launcher.start(tuple(argv), dict(environment))
    record = next(item for item in launcher.records if item.process is process)
    if sink is not None:
        sink.record('owned_helper_started', {
            'role': 'window_helper', 'command': list(argv), 'pid': process.pid,
            'process_identity': record.identity,
        })
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=max(0.001, timeout_s),
        )
    except asyncio.TimeoutError as error:
        raise ObservationFailure(
            'X11 helper exceeded checkpoint deadline'
        ) from error
    status = await process.wait()
    if status != 0:
        raise ObservationFailure(
            'X11 helper failed '
            f'({status}): {stderr.decode(errors="replace")[:512]}'
        )
    if sink is not None:
        sink.record('owned_helper_exit', {
            'role': 'window_helper', 'pid': process.pid, 'exit_status': status,
        })
    return stdout.decode('utf-8', errors='replace')


def _xwininfo_window_entries(tree):
    """Return actual child-window rows, excluding xwininfo root metadata."""
    entries = []
    pattern = re.compile(
        r'^(?P<indent>\s+)(?P<window>0x[0-9a-fA-F]+)\s+(?:"|\()'
    )
    for line in tree.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        entries.append({
            'window_id': match.group('window'),
            'depth': len(match.group('indent')),
        })
    seen = {}
    for entry in entries:
        window_id = entry['window_id']
        if window_id in seen:
            raise ObservationFailure(
                'xwininfo returned a duplicate window entry'
            )
        seen[window_id] = entry['depth']
    return entries


def _valid_process_identity(identity, pid):
    fields = ('pid', 'process_group_id', 'session_id', 'start_ticks')
    return (
        isinstance(identity, dict)
        and all(type(identity.get(key)) is int and identity[key] > 0
                for key in fields)
        and identity['pid'] == pid
    )


def _owned_gui_lineage(
    pid, gui_record, *, identity_reader, parent_reader, max_depth=64,
):
    """Require an exact GUI owner or a same-session descendant of it."""
    owned = gui_record.identity
    if (not _valid_process_identity(owned, gui_record.pid)
            or _process_label(gui_record.command) != 'gui'):
        raise ObservationFailure(
            'owned GUI identity or launcher pin is invalid'
        )
    if identity_reader(gui_record.pid) != owned:
        raise ObservationFailure('owned GUI process identity changed')
    identity = identity_reader(pid)
    if not _valid_process_identity(identity, pid):
        raise ObservationFailure('window process identity is incomplete')
    if (identity['process_group_id'] != owned['process_group_id']
            or identity['session_id'] != owned['session_id']):
        raise ObservationFailure(
            'window process is outside the owned GUI group'
        )
    if pid == gui_record.pid:
        if identity != owned:
            raise ObservationFailure(
                'owned GUI process start identity changed'
            )
        return identity
    current = pid
    visited = {pid}
    for _depth in range(max_depth):
        parent = parent_reader(current)
        if type(parent) is not int or parent <= 0 or parent in visited:
            raise ObservationFailure('window process ancestry is invalid')
        if parent == gui_record.pid:
            if identity_reader(parent) != owned:
                raise ObservationFailure('owned GUI ancestor identity changed')
            return identity
        ancestor = identity_reader(parent)
        if (not _valid_process_identity(ancestor, parent)
                or ancestor['process_group_id'] != owned['process_group_id']
                or ancestor['session_id'] != owned['session_id']):
            raise ObservationFailure('window process ancestry is not owned')
        visited.add(parent)
        current = parent
    raise ObservationFailure('window process ancestry exceeded its bound')


async def bind_gui_window(*, launcher, environment, partition, deadline,
                          steady=time.monotonic, sink=None,
                          process_identity_reader=process_start_identity,
                          parent_reader=process_parent_pid,
                          executable_reader=os.readlink,
                          argv_reader=None,
                          partition_reader=_partition_for_pid):
    """Bind one X11 window to the already-owned GUI process identity."""
    remaining = deadline - steady()
    tree = await _owned_helper(
        launcher, ('/usr/bin/xwininfo', '-root', '-tree'), environment,
        timeout_s=remaining, sink=sink,
    )
    gui = [record for record in launcher.records if record.name == 'gui']
    if len(gui) != 1 or gui[0].identity is None:
        raise ObservationFailure(
            'exactly one identified owned GUI is required'
        )
    gui_record = gui[0]
    entries = _xwininfo_window_entries(tree)
    matches = []
    for entry in entries:
        window_id = entry['window_id']
        remaining = deadline - steady()
        if remaining <= 0:
            raise ReviewInvalidated(
                'window enumeration exhausted review budget'
            )
        props = await _owned_helper(
            launcher, ('/usr/bin/xprop', '-id', window_id,
                       '_NET_WM_PID', 'WM_CLASS', '_NET_WM_NAME', 'WM_NAME'),
            environment, timeout_s=min(2.0, remaining), sink=sink,
        )
        class_match = re.search(r'WM_CLASS\([^)]*\)\s*=\s*(.*)', props)
        if (
            class_match is None
            or not re.search(
                r'gazebo|\bgz\b', class_match.group(1), re.I
            )
        ):
            continue
        match = re.search(r'_NET_WM_PID\(CARDINAL\)\s*=\s*(\d+)', props)
        if not match:
            raise ObservationFailure(
                f'GUI client window {window_id} has no owned PID metadata'
            )
        pid = int(match.group(1))
        identity = _owned_gui_lineage(
            pid, gui_record, identity_reader=process_identity_reader,
            parent_reader=parent_reader,
        )
        exe = executable_reader(f'/proc/{pid}/exe')
        if argv_reader is None:
            argv = [part.decode('utf-8', errors='replace') for part in
                    Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
                    if part]
        else:
            argv = list(argv_reader(pid))
        if not exe or not argv:
            raise ObservationFailure(
                'window process executable/argv metadata is missing'
            )
        if partition_reader(pid) != partition:
            raise ObservationFailure(
                'window process partition differs from the run'
            )
        if process_identity_reader(pid) != identity:
            raise ObservationFailure(
                'window process identity changed during metadata read'
            )
        matches.append((entry['depth'], {
            'window_id': window_id, 'pid': pid,
            'pgid': identity['process_group_id'],
            'process_start_ticks': identity['start_ticks'],
            'gz_partition': partition, 'properties': props[:2048],
            'gui_process_identity': gui_record.identity,
            'executable': exe, 'argv': argv,
            'window_tree_depth': entry['depth'],
        }))
    if len(matches) != 1:
        if not matches:
            raise ObservationFailure(
                'expected exactly one owned GUI client window; found none'
            )
        raise ObservationFailure(
            'expected exactly one owned GUI client window; '
            f'found {len(matches)}'
        )
    result = matches[0][1]
    if sink is not None:
        sink.record('gui_window_bound', result)
    return result


def capture_x11_window(
    window_id, screenshot_path=None, *, qt_api_factory=None,
):
    """Capture only one X11 window and persist the unmodified PNG bytes."""
    if qt_api_factory is None:
        from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
        from PyQt5.QtGui import QGuiApplication, QImage
    else:
        QGuiApplication, QImage, QBuffer, QByteArray, QIODevice = (
            qt_api_factory()
        )
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    screen = app.primaryScreen()
    if screen is None:
        raise ObservationFailure('Qt XCB has no active screen')
    pixmap = screen.grabWindow(int(window_id, 16))
    if pixmap.isNull():
        raise ObservationFailure('window capture returned a null pixmap')
    image = pixmap.toImage()
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        raise ObservationFailure('captured image is empty or undecodable')
    array = QByteArray()
    buffer = QBuffer(array)
    if not buffer.open(QIODevice.WriteOnly) or not image.save(buffer, 'PNG'):
        raise ObservationFailure('could not encode captured window as PNG')
    buffer.close()
    data = bytes(array)
    if not data or len(data) > 32 * 1024 * 1024:
        raise ObservationFailure('captured PNG is empty or exceeds 32 MiB')
    decoded = QImage.fromData(data, 'PNG')
    if decoded.isNull() or decoded.width() <= 0 or decoded.height() <= 0:
        raise ObservationFailure('captured PNG failed decode verification')
    rgba = decoded.convertToFormat(QImage.Format_RGBA8888)
    bits = rgba.bits()
    bits.setsize(rgba.byteCount())
    raw = bytes(bits)
    pixels = (raw[index:index + 4] for index in range(0, len(raw), 4))
    first = next(pixels, None)
    if first is None or all(pixel == first for pixel in pixels):
        raise ObservationFailure('captured window is uniformly blank')
    path = Path(screenshot_path) if screenshot_path is not None else None
    if path is not None:
        atomic_publish(path, data)
    return {
        'path': str(path) if path is not None else None,
        'sha256': sha256_bytes(data),
        'width': decoded.width(), 'height': decoded.height(),
        'size_bytes': len(data), 'png_bytes': data,
    }


def capture_worker_png(window_id, *, capture=capture_x11_window):
    """Capture and validate one X11 window for the internal worker mode."""
    result = capture(window_id, None)
    return result['png_bytes']


def _capture_payload_facts(data):
    """Verify the worker's bounded PNG envelope in the parent process."""
    if (not isinstance(data, bytes) or not data
            or len(data) > 32 * 1024 * 1024):
        raise ObservationFailure('capture worker returned invalid PNG size')
    if (len(data) < 24 or data[:8] != b'\x89PNG\r\n\x1a\n'
            or data[12:16] != b'IHDR'):
        raise ObservationFailure('capture worker returned malformed PNG')
    width = int.from_bytes(data[16:20], 'big')
    height = int.from_bytes(data[20:24], 'big')
    if width <= 0 or height <= 0:
        raise ObservationFailure('capture worker returned zero-size PNG')
    return {
        'sha256': sha256_bytes(data), 'width': width, 'height': height,
        'size_bytes': len(data), 'png_bytes': data, 'path': None,
    }


async def capture_x11_window_bounded(
    window_id, *, launcher, environment, deadline, steady=time.monotonic,
    sink=None,
):
    """Capture via an owned worker while the loop stays responsive."""
    remaining = deadline - steady()
    if remaining <= 0:
        raise ReviewInvalidated('capture started after review deadline')
    command = (
        sys.executable, str(Path(__file__).resolve()),
        '--capture-worker', window_id,
    )
    process = await launcher.start(command, dict(environment))
    record = next(
        (item for item in launcher.records if item.process is process), None,
    )
    if record is None or not _valid_process_identity(
        record.identity, process.pid,
    ):
        raise ObservationFailure(
            'capture worker ownership is unknown; '
            f'residue unknown pid={process.pid}'
        )
    if sink is not None:
        sink.record('capture_worker_started', {
            'pid': record.pid, 'identity': record.identity,
            'command': list(command),
        })
    communication = asyncio.create_task(process.communicate())
    try:
        done, _pending = await asyncio.wait(
            {communication}, timeout=max(0.0, deadline - steady()),
        )
        if not done:
            raise ReviewInvalidated('capture worker exceeded review deadline')
        stdout, stderr = communication.result()
        if process.returncode is None:
            remaining = deadline - steady()
            if remaining <= 0:
                raise ReviewInvalidated(
                    'capture worker exit exceeded review deadline'
                )
            status = await asyncio.wait_for(
                process.wait(), timeout=remaining,
            )
        else:
            status = process.returncode
        if status != 0:
            raise ObservationFailure(
                'capture worker failed '
                f'({status}): '
                f'{stderr.decode(errors="replace")[:512]}'
            )
        facts = _capture_payload_facts(stdout)
        if sink is not None:
            sink.record('capture_worker_exit', {
                'pid': record.pid, 'exit_status': status,
                'png_sha256': facts['sha256'],
                'size_bytes': facts['size_bytes'],
            })
        return facts
    except BaseException as error:
        if not communication.done():
            communication.cancel()
            join_budget = min(1.0, max(0.0, deadline - steady()))
            done, _pending = await asyncio.wait(
                {communication}, timeout=join_budget,
            )
            if not done:
                raise ObservationFailure(
                    'capture communication task residue unknown'
                ) from error
            await asyncio.gather(communication, return_exceptions=True)
        raise


def _utc_timestamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def publish_review_request(*, root, packet_hash, session_id, window,
                           screenshot, request_id, created_steady_ns,
                           deadline_steady_ns, utc_now=_utc_timestamp):
    """Publish one exact request and return its immutable bytes and path."""
    root = Path(root)
    request_dir = root / 'review_mailbox' / 'requests'
    result_dir = root / 'review_mailbox' / 'results'
    screenshot_dir = root / 'screenshots'
    for directory in (root / 'review_mailbox', request_dir, result_dir,
                      screenshot_dir):
        if not directory.exists():
            directory.mkdir(mode=0o700)
        if directory.is_symlink() or not directory.is_dir():
            raise ObservationFailure('review mailbox path is redirected')
        os.chmod(directory, 0o700)
    screenshot_path = screenshot_dir / (
        f'{request_id}-{screenshot["sha256"]}.png'
    )
    if Path(screenshot['path']) != screenshot_path:
        raise ObservationFailure('screenshot path is not canonical')
    request_path = request_dir / f'{request_id}.json'
    result_path = result_dir / f'{request_id}.json'
    request = {
        'schema_id': 'b22_gui_codex_review_request/v1',
        'schema_version': 1, 'run_id': RUN_ID,
        'session_id': session_id, 'packet_sha256': packet_hash,
        'review_request_id': request_id,
        'screenshot_path': str(screenshot_path),
        'screenshot_sha256': screenshot['sha256'],
        'window_process_identity': {
            'evidence_sequence': window['evidence_sequence'],
            'window_id': window['window_id'], 'pid': window['pid'],
            'pgid': window['pgid'],
            'process_start_ticks': window['process_start_ticks'],
            'gz_partition': window['gz_partition'],
        },
        'request_created_utc': utc_now(),
        'request_created_steady_ns': created_steady_ns,
        'review_deadline_steady_ns': deadline_steady_ns,
        'result_path': str(result_path),
    }
    data = (json.dumps(request, sort_keys=True, separators=(',', ':'))
            + '\n').encode('utf-8')
    validate_review_request(
        request, evidence_root=root, packet_hash=packet_hash,
        session_id=session_id,
    )
    atomic_publish(request_path, data)
    return request_path, data, request


async def await_codex_review(*, request_path, request_bytes, request,
                             deadline, steady, sink, stop_event=None,
                             read_file=None,
                             monotonic_ns=time.monotonic_ns,
                             sleep=asyncio.sleep):
    """Poll one result while the parallel health monitors continue."""
    read_file = read_file or read_published
    result_path = Path(request['result_path'])
    seen = None
    while steady() < deadline:
        if stop_event is not None and stop_event.is_set():
            raise ReviewInvalidated('review invalidated by run health failure')
        try:
            data = read_file(result_path)
        except FileNotFoundError:
            await sleep(min(0.05, max(0.0, deadline - steady())))
            continue
        if seen is not None and data != seen:
            raise ObservationFailure('review result changed after publication')
        seen = data
        result = strict_json_loads(data)
        validate_review_result(
            result, request_bytes, request,
            now_ns=monotonic_ns(),
        )
        if sink is not None:
            sink.record('codex_review_result', {
                'result_sha256': sha256_bytes(data),
                'request_sha256': sha256_bytes(request_bytes),
                'screenshot_sha256': request['screenshot_sha256'],
                'verdict': result['verdict'], 'reason': result['reason'],
                'reviewer_kind': 'CODEX',
                'viewer_ref_state': result['viewer_ref_state'],
            })
        if result['verdict'] != 'PASS':
            raise ObservationFailure(
                f'Codex image review failed: {result["reason"]}'
            )
        return result
    raise ReviewInvalidated('Codex image review deadline expired')


def _review_result_bytes(request_bytes, request, *, verdict, reason,
                         viewer_interaction_ref=None,
                         viewer_ref_state='TOOL_NO_STABLE_REFERENCE',
                         utc_now=_utc_timestamp):
    result = {
        'schema_id': 'b22_gui_codex_review_result/v1', 'schema_version': 1,
        'run_id': RUN_ID, 'session_id': request['session_id'],
        'packet_sha256': request['packet_sha256'],
        'review_request_id': request['review_request_id'],
        'request_sha256': sha256_bytes(request_bytes),
        'screenshot_sha256': request['screenshot_sha256'],
        'reviewer_kind': 'CODEX', 'verdict': verdict, 'reason': reason,
        'viewer_interaction_ref': viewer_interaction_ref,
        'viewer_ref_state': viewer_ref_state,
        'result_created_utc': utc_now(),
    }
    return (json.dumps(result, sort_keys=True, separators=(',', ':'))
            + '\n').encode('utf-8')


def publish_review_result_worker(
    request_path, *, verdict, reason, viewer_interaction_ref=None,
    viewer_ref_state='TOOL_NO_STABLE_REFERENCE', root=EVIDENCE_ROOT,
    read_file=None, publish=None,
):
    """One-shot local writer; it never initializes ROS/Gazebo or a viewer."""
    root = Path(root)
    read_file = read_file or read_published
    publish = publish or atomic_publish
    request_path = Path(request_path)
    expected_parent = root / 'review_mailbox' / 'requests'
    if request_path.parent != expected_parent:
        raise ObservationFailure('request path is outside canonical mailbox')
    request_bytes = read_file(request_path)
    request = strict_json_loads(request_bytes)
    validate_review_request(
        request, evidence_root=root, packet_hash=request.get('packet_sha256'),
        session_id=request.get('session_id'),
    )
    image_path = Path(request['screenshot_path'])
    image = read_file(image_path, max_bytes=32 * 1024 * 1024)
    if sha256_bytes(image) != request['screenshot_sha256']:
        raise ObservationFailure(
            'screenshot hash changed before result publish'
        )
    if verdict not in ('PASS', 'FAIL'):
        raise ObservationFailure('review verdict must be PASS or FAIL')
    if (
        not isinstance(reason, str) or not reason
        or len(reason.encode('utf-8')) > 512
    ):
        raise ObservationFailure('review reason must be 1..512 UTF-8 bytes')
    result_bytes = _review_result_bytes(
        request_bytes, request, verdict=verdict, reason=reason,
        viewer_interaction_ref=viewer_interaction_ref,
        viewer_ref_state=viewer_ref_state,
    )
    result_path = Path(request['result_path'])
    publish(result_path, result_bytes)
    return result_path


def _finalize_publisher_process(
    process, identity, *, deadline, steady, identity_reader, signal_group,
):
    """Boundedly settle one publisher handle without guessing ownership."""
    try:
        if process.poll() is not None:
            return None
    except BaseException as error:
        return f'residue unknown: process poll failed: {type(error).__name__}'
    if (identity is None or not _valid_process_identity(
            identity, process.pid)
            or identity['process_group_id'] != process.pid
            or identity['session_id'] != process.pid):
        remaining = deadline - steady()
        if remaining > 0:
            try:
                process.wait(timeout=min(1.0, remaining))
            except BaseException:
                pass
        try:
            if process.poll() is not None:
                return None
        except BaseException:
            pass
        return (
            'residue unknown: publisher identity unverified '
            f'pid={process.pid}'
        )
    for sig in (signal.SIGTERM, signal.SIGKILL):
        remaining = deadline - steady()
        if remaining <= 0:
            break
        try:
            current = identity_reader(process.pid)
            if current != identity:
                return (
                    'residue unknown: publisher identity changed '
                    f'pid={process.pid}'
                )
            signal_group(process.pid, sig)
        except ProcessLookupError:
            break
        except BaseException as error:
            return (
                'residue unknown: publisher signal failed '
                f'{type(error).__name__} pid={process.pid}'
            )
        remaining = deadline - steady()
        if remaining <= 0:
            break
        try:
            process.wait(timeout=min(1.0, remaining))
        except subprocess.TimeoutExpired:
            pass
        except BaseException as error:
            return (
                'residue unknown: publisher wait failed '
                f'{type(error).__name__} pid={process.pid}'
            )
        try:
            if process.poll() is not None:
                return None
        except BaseException:
            return f'residue unknown: publisher poll failed pid={process.pid}'
    return f'residue unknown: publisher still alive pid={process.pid}'


def publish_review_result_bounded(
    request_path, *, verdict, reason, viewer_interaction_ref=None,
    viewer_ref_state='TOOL_NO_STABLE_REFERENCE', request_deadline,
    steady=time.monotonic, popen=subprocess.Popen,
    identity_reader=process_start_identity, signal_group=None,
    on_started=None,
):
    """Run the file-only writer in an owned group with bounded cleanup."""
    remaining = request_deadline - steady()
    if remaining < 7.0:
        raise ReviewInvalidated('less than 7 seconds remain for publisher')
    budget = min(5.0, remaining)
    argv = [
        sys.executable, str(Path(__file__).resolve()),
        '--review-publish-worker', str(request_path), '--verdict', verdict,
        '--reason', reason, '--viewer-ref-state', viewer_ref_state,
    ]
    if viewer_interaction_ref is not None:
        argv.extend(['--viewer-ref', viewer_interaction_ref])
    process = popen(
        argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    # Retain the OS handle before any /proc read or evidence callback.
    owned_process = process
    identity = None
    signal_group = signal_group or os.killpg
    try:
        identity = identity_reader(process.pid)
        if (not _valid_process_identity(identity, process.pid)
                or identity['process_group_id'] != process.pid
                or identity['session_id'] != process.pid):
            raise ObservationFailure(
                'publisher worker ownership is unverified'
            )
        if on_started is not None:
            on_started(owned_process)
        remaining = request_deadline - steady()
        if remaining <= 0:
            raise ReviewInvalidated('publisher deadline expired before wait')
        stdout, stderr = process.communicate(
            timeout=min(budget, remaining),
        )
        if process.returncode != 0:
            raise ObservationFailure(
                'publisher worker failed: '
                f'{stderr.decode(errors="replace")[:512]}'
            )
        return {
            'exit_status': process.returncode,
            'worker_pid': process.pid, 'worker_identity': identity,
            'stdout': stdout.decode(errors='replace')[:512],
            'cleanup_status': 'not_required',
        }
    except BaseException as error:
        residue = _finalize_publisher_process(
            owned_process, identity, deadline=request_deadline,
            steady=steady, identity_reader=identity_reader,
            signal_group=signal_group,
        )
        message = f'publisher worker failed: {type(error).__name__}:{error}'
        if residue:
            message += f'; {residue}'
        raise ObservationFailure(message) from error


class ReadinessAdapter:
    """Expose audited readiness without any Owner input channel."""

    def __init__(self, readiness, readiness_complete_event=None,
                 expected_environment=None):
        """Wrap readiness and its optional completion signal."""
        self._readiness = readiness
        self.readiness_complete_event = readiness_complete_event
        self._expected_environment = dict(expected_environment or {})
        self._bound_environment = None

    def bind_environment(self, environment):
        """Check the supervisor binding without calling a nonexistent API."""
        bound = dict(environment)
        if bound != self._expected_environment:
            raise ObservationFailure(
                'supervisor environment differs from the launch plan'
            )
        self._bound_environment = bound

    def bind_evidence_sink(self, evidence_sink):
        """Forward the evidence sink required by canonical readiness."""
        binder = getattr(self._readiness, 'bind_evidence_sink', None)
        if binder is None:
            raise ObservationFailure(
                'canonical readiness has no evidence-sink binding hook'
            )
        return binder(evidence_sink)

    async def server_scene(self, plan, process, timeout_s):
        """Run the bounded server-scene readiness check."""
        if self._bound_environment != dict(plan.environment):
            raise ObservationFailure(
                'readiness environment was not bound to the launch plan'
            )
        result = await self._readiness.server_scene(plan, process, timeout_s)
        if self.readiness_complete_event is not None:
            self.readiness_complete_event.set()
        return result

    async def gui_process_started(self, plan, process, timeout_s):
        """Run the bounded GUI process-start check."""
        return await self._readiness.gui_process_started(
            plan, process, timeout_s,
        )


REQUEST_FIELDS = {
    'schema_id', 'schema_version', 'run_id', 'session_id',
    'packet_sha256', 'review_request_id', 'screenshot_path',
    'screenshot_sha256', 'window_process_identity', 'request_created_utc',
    'request_created_steady_ns', 'review_deadline_steady_ns', 'result_path',
}
RESULT_FIELDS = {
    'schema_id', 'schema_version', 'run_id', 'session_id',
    'packet_sha256', 'review_request_id', 'request_sha256',
    'screenshot_sha256', 'reviewer_kind', 'verdict', 'reason',
    'viewer_interaction_ref', 'viewer_ref_state', 'result_created_utc',
}


def _write_all(fd, data):
    view = memoryview(data)
    while view:
        count = os.write(fd, view)
        if count <= 0:
            raise OSError('short file write')
        view = view[count:]


def _open_directory_nofollow(path):
    """Walk an absolute directory path one component at a time."""
    path = Path(os.path.abspath(path))
    fd = os.open(path.anchor, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        for component in path.parts[1:]:
            next_fd = os.open(
                component, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
                | getattr(os, 'O_NOFOLLOW', 0), dir_fd=fd,
            )
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def atomic_publish(path: Path, data: bytes):
    """Atomically publish a new file by same-directory hard link."""
    path = Path(path)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise ObservationFailure('mailbox parent is missing or redirected')
    directory_fd = _open_directory_nofollow(path.parent)
    temporary = f'.tmp-{uuid.uuid4()}'
    descriptor = None
    try:
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL
            | getattr(os, 'O_NOFOLLOW', 0), 0o600, dir_fd=directory_fd,
        )
        _write_all(descriptor, data)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(
            temporary, path.name, src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd, follow_symlinks=False,
        )
        os.unlink(temporary, dir_fd=directory_fd)
        os.fsync(directory_fd)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.close(directory_fd)
    return path


def read_published(path: Path, *, max_bytes=16 * 1024):
    """Read one regular mode-0600 mailbox file without following links."""
    path = Path(path)
    dfd = _open_directory_nofollow(path.parent)
    try:
        fd = os.open(
            path.name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0),
            dir_fd=dfd,
        )
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise ObservationFailure('mailbox type/mode mismatch')
            if info.st_size > max_bytes:
                raise ObservationFailure('mailbox exceeds 16 KiB')
            output = bytearray()
            while len(output) <= max_bytes:
                chunk = os.read(fd, min(4096, max_bytes + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
            if len(output) != info.st_size or len(output) > max_bytes:
                raise ObservationFailure('mailbox changed while being read')
            return bytes(output)
        finally:
            os.close(fd)
    finally:
        os.close(dfd)


def validate_review_request(
    request, *, evidence_root, packet_hash, session_id,
):
    """Validate request schema, identity bindings, paths, and deadline."""
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise ObservationFailure('review request schema mismatch')
    request_id = request['review_request_id']
    if not isinstance(request_id, str) or not re.fullmatch(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-'
        r'[89ab][0-9a-f]{3}-[0-9a-f]{12}', request_id,
    ):
        raise ObservationFailure('review request ID must be canonical UUID')
    digest = request['screenshot_sha256']
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r'[0-9a-f]{64}', digest)
    ):
        raise ObservationFailure('screenshot SHA-256 is malformed')
    root = Path(evidence_root)
    expected = {
        'schema_id': 'b22_gui_codex_review_request/v1',
        'schema_version': 1, 'run_id': RUN_ID, 'session_id': session_id,
        'packet_sha256': packet_hash,
        'screenshot_path': str(
            root / 'screenshots' / f'{request_id}-{digest}.png'
        ),
        'result_path': str(
            root / 'review_mailbox' / 'results' / f'{request_id}.json'
        ),
    }
    for key, value in expected.items():
        if type(request.get(key)) is not type(value) or request[key] != value:
            raise ObservationFailure(f'review request {key} mismatch')
    identity = request['window_process_identity']
    identity_fields = {
        'evidence_sequence', 'window_id', 'pid', 'pgid',
        'process_start_ticks', 'gz_partition',
    }
    if not isinstance(identity, dict) or set(identity) != identity_fields:
        raise ObservationFailure('window/process evidence schema mismatch')
    for key in ('evidence_sequence', 'pid', 'pgid', 'process_start_ticks'):
        if type(identity[key]) is not int or identity[key] <= 0:
            raise ObservationFailure(f'window identity {key} is invalid')
    for key in ('window_id', 'gz_partition'):
        if not isinstance(identity[key], str) or not identity[key]:
            raise ObservationFailure(f'window identity {key} is invalid')
    for key in ('request_created_steady_ns', 'review_deadline_steady_ns'):
        if type(request[key]) is not int or request[key] <= 0:
            raise ObservationFailure(f'{key} must be a positive integer')
    if (
        request['review_deadline_steady_ns']
        <= request['request_created_steady_ns']
    ):
        raise ObservationFailure(
            'review deadline is not after request creation'
        )
    if (
        not isinstance(request['request_created_utc'], str)
        or not request['request_created_utc']
    ):
        raise ObservationFailure('request UTC timestamp is invalid')
    return request


def validate_review_result(result, request_bytes, request, *, now_ns):
    """Validate result bindings and reject invalid or late reviewer output."""
    if not isinstance(result, dict) or set(result) != RESULT_FIELDS:
        raise ObservationFailure('review result schema mismatch')
    expected = {
        'schema_id': 'b22_gui_codex_review_result/v1', 'schema_version': 1,
        'run_id': RUN_ID, 'session_id': request['session_id'],
        'packet_sha256': request['packet_sha256'],
        'review_request_id': request['review_request_id'],
        'request_sha256': sha256_bytes(request_bytes),
        'screenshot_sha256': request['screenshot_sha256'],
        'reviewer_kind': 'CODEX',
    }
    for key, value in expected.items():
        if type(result.get(key)) is not type(value) or result[key] != value:
            raise ObservationFailure(f'review result {key} mismatch')
    if result['verdict'] not in ('PASS', 'FAIL'):
        raise ObservationFailure('review verdict must be PASS or FAIL')
    reason = result['reason']
    if (
        not isinstance(reason, str) or not reason
        or len(reason.encode('utf-8')) > 512
    ):
        raise ObservationFailure('review reason must be 1..512 UTF-8 bytes')
    ref = result['viewer_interaction_ref']
    if ref is not None and (not isinstance(ref, str) or len(ref) > 256):
        raise ObservationFailure('viewer interaction reference is invalid')
    state = result['viewer_ref_state']
    if state not in ('AVAILABLE', 'TOOL_NO_STABLE_REFERENCE'):
        raise ObservationFailure('viewer reference state is invalid')
    if (state == 'AVAILABLE') != (ref is not None):
        raise ObservationFailure('viewer state and reference disagree')
    if (
        not isinstance(result['result_created_utc'], str)
        or not result['result_created_utc']
    ):
        raise ObservationFailure('result timestamp is invalid')
    if now_ns >= request['review_deadline_steady_ns']:
        raise ReviewInvalidated(
            'review result arrived after the fixed deadline'
        )
    return result


class TrackedProcessLauncher:
    """Use the audited launcher while checking its owned session identity."""

    def __init__(self, delegate, on_start=None, identity_reader=None,
                 proc_root=Path('/proc'), signal_process=os.kill,
                 process_inventory=None):
        """Wrap the audited launcher with process-start identity tracking."""
        self.delegate = delegate
        self.on_start = on_start
        self.identity_reader = identity_reader or process_start_identity
        self.proc_root = Path(proc_root)
        self.signal_process = signal_process
        self.process_inventory = process_inventory
        self.identities = {}
        self.records = []
        self.waiters = {}

    async def start(self, command, environment):
        """Start a process and record its PID/session identity immediately."""
        process = await self.delegate.start(command, environment)
        record = SimpleNamespace(
            name=_process_label(command), command=tuple(command),
            pid=process.pid, process=process, identity=None,
            identity_error=None,
        )
        self.records.append(record)
        self.waiters[id(process)] = asyncio.create_task(process.wait())
        try:
            identity = self.identity_reader(process.pid)
            if not _valid_owned_leader_identity(identity, process.pid):
                raise ObservationFailure(
                    'new launcher process is not its owned session leader'
                )
            record.identity = identity
            self.identities[id(process)] = identity
        except BaseException as error:
            record.identity_error = f'{type(error).__name__}:{error}'
            raise
        if self.on_start is not None:
            self.on_start(record, record.identity)
        return process

    def _members(self, process):
        identity = self.identities.get(id(process))
        if identity is None:
            raise ObservationFailure(
                'owned process group identity is unknown; '
                'residue is unverified'
            )
        members = []
        leader_access_uncertain = False
        if self.process_inventory is not None:
            inventory = self.process_inventory()
        else:
            inventory = []
            for entry in self.proc_root.iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    inventory.append(
                        self.identity_reader(int(entry.name)),
                    )
                except (FileNotFoundError, ProcessLookupError):
                    continue
                except (PermissionError, ValueError):
                    if int(entry.name) == process.pid:
                        leader_access_uncertain = True
                    continue
        for current in inventory:
            if current['pid'] == process.pid:
                if current != identity:
                    raise ObservationFailure(
                        'owned process leader identity changed; '
                        'PID reuse suspected'
                    )
            if (current['process_group_id'] == identity['process_group_id']
                    and current['session_id'] == identity['session_id']
                    and current['start_ticks'] >= identity['start_ticks']):
                members.append(current)
        if leader_access_uncertain:
            raise ObservationFailure(
                'owned process leader identity unavailable; residue unknown'
            )
        return identity, members

    def group_alive(self, process):
        """Check members against the process group and session identity."""
        if id(process) not in self.identities:
            raise ObservationFailure(
                'owned process group identity is unknown; residue unverified'
            )
        _identity, members = self._members(process)
        return bool(members)

    async def stop_group(self, process, sig):
        """Signal only members whose current proc identity remains owned."""
        if id(process) not in self.identities:
            raise ObservationFailure(
                'cannot signal a process group without verified identity'
            )
        identity, members = self._members(process)
        if not members:
            return
        leader = next(
            (item for item in members if item['pid'] == process.pid), None,
        )
        if (
            leader is not None
            and leader['start_ticks'] == identity['start_ticks']
        ):
            current = self.identity_reader(process.pid)
            if current != identity:
                raise ObservationFailure(
                    'leader identity changed before signal; residue unknown'
                )
            await self.delegate.stop_group(process, sig)
            return
        # The leader exited; signal only members whose live proc identity was
        # captured in the currently verified owned session.
        import signal
        for member in members:
            current = self.identity_reader(member['pid'])
            if current != member:
                continue
            try:
                self.signal_process(
                    member['pid'],
                    sig if isinstance(sig, int) else signal.SIGINT,
                )
            except ProcessLookupError:
                pass


class ResilientSupervisor:
    """Instantiate the canonical supervisor with failure-resilient cleanup."""

    def __new__(cls, base_type, **kwargs):
        """Create the audited supervisor with best-effort owned cleanup."""
        cleanup_window = kwargs.pop('cleanup_window')
        cleanup_errors = kwargs.pop('cleanup_errors')
        cleanup_options = kwargs.pop('cleanup_options', {})

        class BoundSupervisor(base_type):
            async def start(self):
                """Start RUN004 roles without an Owner ACK stage."""
                ProcessRecord = importlib.import_module(
                    'mecanum_nav_bringup.local_training_process_supervisor',
                ).ProcessRecord
                try:
                    bind_environment = getattr(
                        self.readiness, 'bind_environment', None,
                    )
                    if bind_environment is not None:
                        bind_environment(self.plan.environment)
                    bridge_command = getattr(
                        self.plan, 'bridge_command', None,
                    )
                    if bridge_command:
                        bridge = await self.launcher.start(
                            bridge_command, self.plan.environment,
                        )
                        record = ProcessRecord(
                            'parameter_bridge', bridge_command,
                            bridge.pid, bridge,
                        )
                        self.owned.append(record)
                        self._capture_output(record)
                        self.evidence_sink.record(
                            'parameter_bridge_requested', self._facts(record),
                        )
                    server_command = self.plan.commands[0]
                    server = await self.launcher.start(
                        server_command, self.plan.environment,
                    )
                    record = ProcessRecord(
                        'server', server_command, server.pid, server,
                    )
                    self.owned.append(record)
                    self._capture_output(record)
                    self.evidence_sink.record(
                        'server_requested', self._facts(record),
                    )
                    await self.readiness.server_scene(
                        self.plan, server, self.SERVER_READY_TIMEOUT_S,
                    )
                    self.evidence_sink.record(
                        'server_scene_ready', {
                            **self._facts(record),
                            'session_id': self.plan.session_id,
                        },
                    )
                    if not self.plan.gui_requested:
                        return
                    gui_command = self.plan.commands[1]
                    gui = await self.launcher.start(
                        gui_command, self.plan.environment,
                    )
                    gui_record = ProcessRecord(
                        'gui', gui_command, gui.pid, gui,
                    )
                    self.owned.append(gui_record)
                    self._capture_output(gui_record)
                    self.evidence_sink.record(
                        'gui_requested', self._facts(gui_record),
                    )
                    await self.readiness.gui_process_started(
                        self.plan, gui, self.GUI_READY_TIMEOUT_S,
                    )
                    self.evidence_sink.record(
                        'gui_process_started', self._facts(gui_record),
                    )
                except BaseException:
                    await self.cleanup()
                    raise

            async def cleanup(self):
                captured = list(self.owned)
                captured.extend(
                    record for record in getattr(
                        self.launcher, 'records', (),
                    ) if all(
                        record.process is not item.process
                        for item in captured
                    )
                )
                base_task = None
                cancelled = False
                try:
                    deadline = cleanup_window.begin()
                    base_task = asyncio.create_task(super().cleanup())
                    done, _ = await asyncio.wait(
                        {base_task}, timeout=max(
                            0.0, deadline - cleanup_window.steady(),
                        ),
                    )
                    if base_task not in done:
                        base_task.cancel()
                        cleanup_errors.append('base_cleanup_timeout')
                        joined, _ = await asyncio.wait(
                            {base_task}, timeout=max(
                                0.0, deadline - cleanup_window.steady(),
                            ),
                        )
                        if not joined:
                            cleanup_errors.append(
                                'base_cleanup_task_residue_unknown'
                            )
                        else:
                            await asyncio.gather(
                                base_task, return_exceptions=True,
                            )
                    else:
                        error = base_task.exception()
                        if error is not None:
                            raise error
                except asyncio.CancelledError:
                    cancelled = True
                    if base_task is not None and not base_task.done():
                        base_task.cancel()
                        joined, _ = await asyncio.wait(
                            {base_task}, timeout=max(
                                0.0, cleanup_window.begin()
                                - cleanup_window.steady(),
                            ),
                        )
                        if joined:
                            await asyncio.gather(
                                base_task, return_exceptions=True,
                            )
                        else:
                            cleanup_errors.append(
                                'base_cleanup_task_residue_unknown'
                            )
                except BaseException as error:
                    cleanup_errors.append(
                        f'base_cleanup:{type(error).__name__}:{error}'
                    )
                finally:
                    await _fallback_cleanup(
                        self.launcher, captured, self.evidence_sink,
                        cleanup_errors, deadline=cleanup_window.begin(),
                        steady=cleanup_window.steady,
                        **cleanup_options,
                    )
                if cleanup_window.steady() >= cleanup_window.begin():
                    if any('residue' in item or 'timeout' in item
                           for item in cleanup_errors):
                        raise ObservationFailure(
                            'cleanup deadline/residue was not cleared'
                        )
                if cancelled:
                    raise asyncio.CancelledError
        return BoundSupervisor(**kwargs)


class CleanupWindow:
    """One immutable cleanup deadline shared by every cleanup path."""

    def __init__(self, consumed_at, total_deadline, steady=time.monotonic):
        """Bind one cleanup window to the run's absolute total deadline."""
        self.consumed_at = consumed_at
        self.total_deadline = total_deadline
        self.steady = steady
        self.started_at = None
        self.deadline = None
        self.pending_operations = []

    def begin(self):
        """Return the same absolute deadline on every cleanup invocation."""
        if self.started_at is None:
            self.started_at = self.steady()
            self.deadline = min(
                self.started_at + CLEANUP_CAP_S, self.total_deadline,
            )
        return self.deadline


def _process_label(command):
    values = tuple(str(value) for value in command)
    if '--capture-worker' in values:
        return 'capture_helper'
    if values and Path(values[0]).name in ('xwininfo', 'xprop'):
        return 'window_helper'
    if 'parameter_bridge' in values and 'ros_gz_bridge' in values:
        return 'parameter_bridge'
    if len(values) > 1 and values[1:3] == ('run', 'robot_state_publisher'):
        return 'robot_state_publisher'
    if '-g' in values:
        return 'gui'
    if '-s' in values:
        return 'server'
    return 'owned_process'


class PassiveBackendObserver:
    """Owned ROS context with backend-state and clock subscribers only."""

    def __init__(self, ros_api_factory=None, *, steady_ns=time.monotonic_ns):
        """Prepare an independent observer context without initializing ROS."""
        self.context = None
        self.executor = None
        self.node = None
        self.subscriptions = []
        self._node_add_attempted = False
        self.events = deque()
        self._rclpy = None
        self._ros_api_factory = ros_api_factory
        self._steady_ns = steady_ns
        self._closed = False

    @staticmethod
    def _production_ros_api():
        import rclpy
        from rclpy.context import Context
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.node import Node
        from rclpy.qos import (
            DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy,
        )
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from rosgraph_msgs.msg import Clock
        return SimpleNamespace(
            rclpy=rclpy, Context=Context, Node=Node,
            SingleThreadedExecutor=SingleThreadedExecutor,
            SimulationContactState=SimulationContactState, Clock=Clock,
            QoSProfile=QoSProfile, HistoryPolicy=HistoryPolicy,
            ReliabilityPolicy=ReliabilityPolicy,
            DurabilityPolicy=DurabilityPolicy,
        )

    @staticmethod
    def clock_qos_profile(api):
        """Match the pinned ros_gz_bridge CLOCK profile's delivery policy."""
        return api.QoSProfile(
            history=api.HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=api.ReliabilityPolicy.BEST_EFFORT,
            durability=api.DurabilityPolicy.VOLATILE,
        )

    def start(self):
        """Initialize a private context with status and clock subscribers."""
        self._closed = False
        api = (
            self._ros_api_factory()
            if self._ros_api_factory is not None
            else self._production_ros_api()
        )
        self._rclpy = api.rclpy
        self.context = api.Context()
        self._rclpy.init(context=self.context, domain_id=83)
        self.executor = api.SingleThreadedExecutor(context=self.context)
        self.node = api.Node(
            'b22_gui_observation_observer', context=self.context,
        )
        self._node_add_attempted = True
        if self.executor.add_node(self.node) is False:
            raise ObservationFailure('observer executor rejected its node')
        self.subscriptions.append(self.node.create_subscription(
            api.SimulationContactState,
            '/mecanum/local_training/backend_state',
            lambda message: self._record_event('backend', message), 50,
        ))
        self.subscriptions.append(self.node.create_subscription(
            api.Clock, '/clock',
            lambda message: self._record_event('clock', message.clock),
            self.clock_qos_profile(api),
        ))

    def _record_event(self, kind, message):
        self.events.append((
            kind, message, time.monotonic(), self._steady_ns(),
        ))

    def spin_once(self, timeout_s: float = 0.1):
        """Process passive observer callbacks for one bounded interval."""
        if self.executor is None or self.node is None:
            raise ObservationFailure('observer executor is not active')
        self.executor.spin_once(timeout_sec=timeout_s)

    def close(self, *, deadline=None, steady=time.monotonic):
        """Release each owned ROS resource once, continuing after errors."""
        if self._closed:
            return
        self._closed = True
        errors = []
        executor, self.executor = self.executor, None
        node, self.node = self.node, None
        context, self.context = self.context, None
        if (
            executor is not None and node is not None
            and self._node_add_attempted
        ):
            try:
                executor.remove_node(node)
            except BaseException as error:
                errors.append(error)
        if executor is not None:
            try:
                timeout = (
                    max(0.0, deadline - steady())
                    if deadline is not None else CLEANUP_CAP_S
                )
                if executor.shutdown(timeout_sec=timeout) is False:
                    raise TimeoutError('observer executor shutdown timed out')
            except BaseException as error:
                errors.append(error)
        try:
            if node is not None:
                node.destroy_node()
        except BaseException as error:
            errors.append(error)
        self.subscriptions.clear()
        try:
            if (
                context is not None and self._rclpy is not None
                and self._rclpy.ok(context=context)
            ):
                self._rclpy.shutdown(context=context)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise ObservationFailure(
                f'observer context cleanup failed: {type(errors[0]).__name__}'
            ) from errors[0]

    def node_inventory(self):
        """Read the post-consume graph from this owned observer node."""
        if self.node is None:
            raise ObservationFailure('observer node is not active')
        return self.node.get_node_names_and_namespaces()


async def evaluate_observation(
    *, plan, observer, duration_s: float = OBSERVATION_S,
    steady=time.monotonic, ack_event=None,
    deadline=None, sink=None, expected_nodes=EXPECTED_ROS_NODES,
    temporary_nodes=STARTUP_TEMPORARY_ROS_NODES,
    readiness_complete_event=None, graph_convergence_s=30.0,
    temporary_stale_s=30.0,
    clock_ready_timeout_s=CLOCK_READY_TIMEOUT_S,
):
    """Monitor status and clock through acknowledgment and observation."""
    monitor_started = steady()
    acknowledgement_time = None
    observation_start = None
    last_heartbeat = None
    last_status_sequence = None
    status_count = 0
    clock_value = None
    clock_stable_since = None
    review_accepted_at = None
    last_clock_received = None
    clock_count = 0
    backend_identity = None
    seen_nodes = None
    readiness_completed_at = None
    while True:
        now = steady()
        if ack_event is not None and ack_event.is_set() and (
            review_accepted_at is None
        ):
            review_accepted_at = now
            clock_stable_since = None
        if deadline is not None and now >= deadline:
            raise ObservationFailure('240 s consume-to-end deadline expired')
        if now - monitor_started > clock_ready_timeout_s and clock_count == 0:
            raise ObservationFailure('clock readiness timed out')
        observer.spin_once(min(POLL_SLICE_S, max(0.001, duration_s)))
        while observer.events:
            event = observer.events.popleft()
            kind, message, received = event[:3]
            received_ns = event[3] if len(event) > 3 else int(received * 1e9)
            if kind == 'clock':
                stamp = (message.sec, message.nanosec)
                clock_count += 1
                if sink is not None:
                    sink.record('clock_sample', {
                        'clock_sec': stamp[0], 'clock_nanosec': stamp[1],
                        'receive_steady_s': received,
                        'receive_steady_ns': received_ns,
                        'processing_steady_ns': int(steady() * 1e9),
                        'received_sample_index': clock_count,
                        'validation_state': 'RECEIVED_NOT_VALIDATED',
                        'previous_receive_steady_ns': (
                            None if last_clock_received is None
                            else int(last_clock_received * 1e9)
                        ),
                        'previous_clock': clock_value,
                    })
                try:
                    if clock_value is None:
                        clock_value = stamp
                    elif stamp != clock_value:
                        raise ObservationFailure('simulation clock advanced')
                    elif (review_accepted_at is not None
                          and received >= review_accepted_at
                          and clock_stable_since is None):
                        clock_stable_since = received
                    if (last_clock_received is not None
                            and received - last_clock_received
                            > CLOCK_SAMPLE_GAP_S):
                        raise ObservationFailure(
                            'clock sample gap exceeded 1 s'
                        )
                except BaseException as error:
                    if sink is not None:
                        sink.record('clock_validation_failed', {
                            'sample_index': clock_count,
                            'reason': str(error)[:512],
                            'detection_steady_ns': int(steady() * 1e9),
                            'receive_steady_ns': received_ns,
                            'previous_receive_steady_ns': (
                                None if last_clock_received is None
                                else int(last_clock_received * 1e9)
                            ),
                        })
                    raise
                last_clock_received = received
                continue
            status_count += 1
            processing_ns = int(steady() * 1e9)
            prior_status_sequence = last_status_sequence
            prior_heartbeat_ns = (
                None if last_heartbeat is None
                else int(last_heartbeat * 1e9)
            )
            if sink is not None:
                sink.record('backend_status_sample', {
                    'validation_state': 'RECEIVED_NOT_VALIDATED',
                    'received_sample_index': status_count,
                    'receive_steady_s': received,
                    'receive_steady_ns': received_ns,
                    'processing_steady_ns': processing_ns,
                    'session_id': getattr(message, 'session_id', None),
                    'config_hash': getattr(message, 'config_hash', None),
                    'backend_instance_id': getattr(
                        message, 'backend_instance_id', None,
                    ),
                    'world': getattr(
                        getattr(message, 'header', None), 'frame_id', None,
                    ),
                    'status_sequence': getattr(
                        message, 'status_sequence', None,
                    ),
                    'paused': getattr(message, 'paused', None),
                    'actuator_inhibited': getattr(
                        message, 'actuator_inhibited', None,
                    ),
                    'fault_flags': getattr(message, 'fault_flags', None),
                    'applied_receipt_valid': getattr(
                        message, 'applied_receipt_valid', None,
                    ),
                    'previous_receive_steady_ns': prior_heartbeat_ns,
                    'previous_status_sequence': prior_status_sequence,
                })
            try:
                identity = (
                    message.session_id, message.config_hash,
                    message.backend_instance_id, message.header.frame_id,
                )
                if identity != (
                    plan.session_id, plan.config_hash,
                    identity[2], 'b2_training_arena',
                ) or not identity[2]:
                    raise ObservationFailure('backend identity mismatch')
                if backend_identity is None:
                    backend_identity = identity
                elif identity != backend_identity:
                    raise ObservationFailure('backend identity changed')
                if not message.paused or not message.actuator_inhibited:
                    raise ObservationFailure(
                        'backend is not paused and inhibited'
                    )
                if message.fault_flags != 0:
                    raise ObservationFailure('backend reports fault flags')
                if message.applied_receipt_valid:
                    raise ObservationFailure('applied receipt observed')
                if message.status_sequence <= 0:
                    raise ObservationFailure(
                        'invalid backend heartbeat sequence'
                    )
                if (last_status_sequence is not None
                        and message.status_sequence <= last_status_sequence):
                    raise ObservationFailure(
                        'backend heartbeat sequence did not increase'
                    )
                if (last_heartbeat is not None
                        and received - last_heartbeat > HEARTBEAT_GAP_S):
                    raise ObservationFailure(
                        'backend heartbeat gap exceeded 1 s'
                    )
            except BaseException as error:
                if sink is not None:
                    sink.record('backend_status_validation_failed', {
                        'sample_index': status_count,
                        'reason': str(error)[:512],
                        'detection_steady_ns': int(steady() * 1e9),
                        'receive_steady_ns': received_ns,
                        'previous_receive_steady_ns': prior_heartbeat_ns,
                        'previous_status_sequence': prior_status_sequence,
                        'trigger_status_sequence': getattr(
                            message, 'status_sequence', None,
                        ),
                    })
                raise
            last_heartbeat = received
            last_status_sequence = message.status_sequence
            if sink is not None:
                sink.record('backend_status_validated', {
                    'sample_index': status_count,
                    'status_sequence': message.status_sequence,
                    'processing_steady_ns': int(steady() * 1e9),
                })
        if hasattr(observer, 'node_inventory'):
            inventory = observer.node_inventory()
            participants = list(inventory)
            unique_participants = set(participants)
            names = {name for name, _namespace in participants}
            if len(participants) != len(unique_participants):
                raise ObservationFailure(
                    'duplicate ROS graph participant names were observed'
                )
            unexpected = unique_participants - (
                set(expected_nodes) | set(temporary_nodes)
            )
            if unexpected:
                raise ObservationFailure(
                    f'unexpected ROS graph participants: {sorted(unexpected)}'
                )
            if readiness_complete_event is None:
                readiness_completed_at = monitor_started
            elif readiness_complete_event.is_set() and (
                readiness_completed_at is None
            ):
                readiness_completed_at = now
            permanent_missing = set(expected_nodes) - unique_participants
            if readiness_completed_at is not None:
                if (permanent_missing and now - readiness_completed_at
                        >= graph_convergence_s):
                    raise ObservationFailure(
                        'ROS graph did not converge after scene readiness: '
                        f'{sorted(permanent_missing)}'
                    )
                stale_temporary = unique_participants & set(temporary_nodes)
                if (stale_temporary and now - readiness_completed_at
                        >= temporary_stale_s):
                    raise ObservationFailure(
                        'temporary readiness ROS node remained in graph'
                    )
            if unique_participants != seen_nodes:
                seen_nodes = unique_participants
                if sink is not None:
                    sink.record('ros_graph_inventory', {
                        'nodes': sorted(names),
                        'participants': [
                            list(item) for item in sorted(unique_participants)
                        ],
                        'unexpected_nodes': sorted(unexpected),
                    })
        now = steady()
        if (
            last_heartbeat is not None
            and now - last_heartbeat > HEARTBEAT_GAP_S
        ):
            raise ObservationFailure('backend heartbeat lost for over 1 s')
        if last_clock_received is not None and (
            now - last_clock_received > CLOCK_SAMPLE_GAP_S
        ):
            raise ObservationFailure(
                'clock samples stopped during observation'
            )
        if (last_heartbeat is None
                and now - monitor_started > clock_ready_timeout_s):
            raise ObservationFailure('backend status readiness timed out')
        if (
            review_accepted_at is not None
            and acknowledgement_time is None
        ):
            acknowledgement_time = review_accepted_at
        clock_stable = (
            clock_stable_since is not None
            and now - clock_stable_since >= 1.0
        )
        if (
            acknowledgement_time is not None and clock_stable
            and observation_start is None
        ):
            observation_start = now
        if (
            observation_start is not None
            and now - observation_start >= duration_s
        ):
            return {
                'backend_identity': list(backend_identity),
                'last_status_sequence': last_status_sequence,
                'backend_status_samples': status_count,
                'heartbeat_last_steady': last_heartbeat,
                'clock_samples': clock_count,
                'clock_stamp': list(clock_value),
                'observed_seconds': now - observation_start,
            }
        await asyncio.sleep(0)


def _installed_paths():
    from ament_index_python.packages import (
        get_package_prefix, get_package_share_directory,
    )
    from mecanum_nav_bringup.local_training_process_supervisor import (
        _physics_engine_plugin_path,
    )

    description = Path(get_package_share_directory(
        'ROBOT_URDF_final_description',
    )).resolve(strict=True)
    rl_share = Path(get_package_share_directory('mecanum_nav_rl')).resolve(
        strict=True,
    )
    bringup = Path(get_package_share_directory('mecanum_nav_bringup')).resolve(
        strict=True,
    )
    backend_prefix = Path(get_package_prefix('mecanum_sim_backend')).resolve(
        strict=True,
    )
    interfaces_prefix = Path(get_package_prefix(
        'mecanum_nav_rl_interfaces',
    )).resolve(strict=True)
    return {
        'description_share': description,
        'rl_share': rl_share,
        'bringup_share': bringup,
        'backend_prefix': backend_prefix,
        'interfaces_prefix': interfaces_prefix,
        'physics_engine_path': _physics_engine_plugin_path(),
    }


def _fingerprint_install(paths: dict[str, Path]) -> dict[str, str]:
    candidates = {
        'world': paths['description_share'] / 'worlds/b2_training_arena.sdf',
        'model': paths['description_share'] / 'models/mecanum_b2/model.sdf',
        'robot_urdf': paths['description_share'] / (
            'urdf/mecanum_b2_static.urdf'
        ),
        'gui_config': paths['bringup_share'] / (
            'config/gui/local_training.config'
        ),
        'bridge_config': paths['bringup_share'] / (
            'config/bridge/local_training.runtime.yaml'
        ),
        'local_training_launch': paths['bringup_share'] / (
            'launch/sim_train_local_training.launch.py'
        ),
        'asset_manifest': paths['description_share'] / (
            'manifests/b2/asset_manifest.json'
        ),
        'resolved_config': paths['rl_share'] / (
            'config/v3/resolved/sim_train_local_training_soak.resolved.json'
        ),
        'scenario': paths['rl_share'] / (
            'scenarios/local_training/B2_SOAK_V1.json'
        ),
        'backend_system': paths['backend_prefix'] / (
            'lib/libmecanum_sim_backend_system.so'
        ),
        'backend_core': paths['backend_prefix'] / (
            'lib/libmecanum_sim_backend_core.so'
        ),
        'launch_contract': (
            paths['bringup_share'].parent.parent
            / 'lib/python3.12/site-packages/'
            / 'mecanum_nav_bringup/local_training_launch_contract.py'
        ),
        'process_supervisor': (
            paths['bringup_share'].parent.parent
            / 'lib/python3.12/site-packages/'
            / 'mecanum_nav_bringup/local_training_process_supervisor.py'
        ),
        'readiness_worker': (
            paths['bringup_share'].parent.parent
            / 'lib/python3.12/site-packages/'
            / 'mecanum_nav_bringup/local_training_readiness_worker.py'
        ),
    }
    result = {}
    for name, path in candidates.items():
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise ObservationFailure(f'installed {name} is not a file')
        result[str(resolved)] = sha256_file(resolved)
    description_share = paths['description_share']
    manifest_path = description_share / 'manifests/b2/asset_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for relative in sorted(manifest['resource_closure']):
        path = description_share.parent / relative
        resolved = path.resolve(strict=True)
        result[str(resolved)] = sha256_file(resolved)
    install_root = paths['backend_prefix']
    interface_lib = install_root / 'lib'
    for path in sorted(interface_lib.glob('libmecanum_nav_rl_interfaces*.so')):
        result[str(path.resolve(strict=True))] = sha256_file(path)
    for path in (
        Path(
            '/opt/ros/jazzy/opt/gz_sim_vendor/lib/'
            'libgz-sim8-scene-broadcaster-system.so.8.11.0'
        ),
        Path(
            '/opt/ros/jazzy/opt/gz_sim_vendor/lib/'
            'libgz-sim8-sensors-system.so.8.11.0'
        ),
        Path(
            '/opt/ros/jazzy/opt/gz_rendering_vendor/lib/'
            'libgz-rendering8-ogre2.so.8.2.3'
        ),
        Path(
            '/opt/ros/jazzy/opt/gz_rendering_vendor/lib/'
            'gz-rendering-8/engine-plugins/'
            'libgz-rendering8-ogre2.so.8.2.3'
        ),
        Path(shutil.which('gz') or ''), Path(shutil.which('ros2') or ''),
        Path('/opt/ros/jazzy/lib/ros_gz_bridge/parameter_bridge'),
        Path('/opt/ros/jazzy/lib/robot_state_publisher/robot_state_publisher'),
        Path('/opt/ros/jazzy/lib/libros_gz_bridge.so'),
        Path('/opt/ros/jazzy/lib/librobot_state_publisher_node.so'),
    ):
        resolved = path.resolve(strict=True)
        result[str(resolved)] = sha256_file(resolved)
    for interface_asset in (
        'msg/SimulationContactState.msg',
        'msg/FinalIssuedCommandReceipt.msg',
        'srv/LocalTrainingBackendControl.srv',
    ):
        path = (
            install_root / 'share/mecanum_nav_rl_interfaces' / interface_asset
        )
        resolved = path.resolve(strict=True)
        result[str(resolved)] = sha256_file(resolved)
    for path in sorted(paths['physics_engine_path'].glob('*')):
        if path.is_file():
            resolved = path.resolve(strict=True)
            result[str(resolved)] = sha256_file(resolved)
    return result


def _exclusive_copy(source: Path, destination: Path) -> None:
    """Copy bytes into a new evidence path without replacing prior evidence."""
    data = source.read_bytes()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(destination, flags, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def build_runtime_plan(gui: bool, temp_dir: Path):
    """Resolve installed B2 assets and call the audited pure launch API."""
    require_run_gui(gui)
    from mecanum_nav_bringup.local_training_launch_contract import (
        build_launch_plan, load_bound_config, write_bound_world,
    )
    from mecanum_nav_bringup.local_training_process_supervisor import (
        _physics_engine_plugin_path,
    )

    paths = _installed_paths()
    config = paths['rl_share'] / (
        'config/v3/resolved/sim_train_local_training_soak.resolved.json'
    )
    world = paths['description_share'] / 'worlds/b2_training_arena.sdf'
    model = paths['description_share'] / 'models/mecanum_b2/model.sdf'
    gui_config = paths['bringup_share'] / 'config/gui/local_training.config'
    bridge = paths['bringup_share'] / (
        'config/bridge/local_training.runtime.yaml'
    )
    document, config_hash, manifest_hash, scenario_id = (
        load_bound_config(config)
    )
    if (
        sha256_file(config) != RESOLVED_SHA256
        or config_hash != CONFIG_HASH
        or manifest_hash != MANIFEST_SHA256
        or scenario_id != 'B2_SOAK_V1'
        or sha256_file(
            paths['rl_share'] / 'scenarios/local_training/B2_SOAK_V1.json'
        )
        != SCENARIO_SHA256
    ):
        raise ObservationFailure('installed B2 input pins do not match packet')
    session_id = str(uuid.uuid4())
    ingress_id = secrets.randbits(64) or 1
    partition = f"mecanum_b2_{session_id.replace('-', '')}"
    plan = build_launch_plan(
        gui='true', resolved_config=config, world_file=world,
        gui_config=gui_config, session_id=session_id, partition=partition,
        bridge_config=bridge,
        resource_paths=(paths['description_share'].parent,
                        paths['description_share'] / 'models'),
        plugin_path=paths['backend_prefix'] / 'lib',
        physics_engine_plugin_path=_physics_engine_plugin_path(),
        asset_manifest_file=(
            paths['description_share'] / 'manifests/b2/asset_manifest.json'
        ),
        scenario_directory=paths['rl_share'] / 'scenarios/local_training',
        runtime_world_directory=temp_dir,
        coordinator_ingress_instance_id=ingress_id,
    )
    descriptor = {
        'schema_id': 'mecanum_b2_run_descriptor/v1',
        'run_id': RUN_ID,
        'session_id': plan.session_id,
        'config_hash': plan.config_hash,
        'asset_manifest_sha256': plan.asset_manifest_sha256,
        'coordinator_ingress_instance_id': (
            plan.coordinator_ingress_instance_id
        ),
        'ros_domain_id': 83,
        'world_source_sha256': sha256_file(world),
        'runtime_bound_world_sha256': None,
        'robot_state_publisher_params_sha256': None,
    }
    bound_path = write_bound_world(plan, world, model)
    descriptor['runtime_bound_world_sha256'] = sha256_file(bound_path)
    urdf_path = paths['description_share'] / 'urdf/mecanum_b2_static.urdf'
    params_path = temp_dir / 'robot_state_publisher.params.yaml'
    params = (
        '/**:\n  ros__parameters:\n    robot_description: '
        + json.dumps(urdf_path.read_text(encoding='utf-8'))
        + '\n    use_sim_time: true\n'
    )
    with params_path.open('x', encoding='utf-8') as stream:
        stream.write(params)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor['robot_state_publisher_params_sha256'] = sha256_file(
        params_path
    )
    descriptor_path = temp_dir / 'run_descriptor.json'
    with descriptor_path.open('x', encoding='utf-8') as stream:
        json.dump(descriptor, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return plan, paths, descriptor, descriptor_path


def _validate_plan_commands(
    plan, packet, *, runtime_dir=None, evidence_root=EVIDENCE_ROOT,
    effective=False,
):
    """Check staged or final argv against the pinned command template."""
    templates = packet['commands_argv']['exact_templates']
    if not plan.gui_requested or len(plan.commands) != 2:
        raise ObservationFailure('launch plan is not the one-GUI RUN004 plan')
    server, gui = (tuple(command) for command in plan.commands)
    server_template = tuple(templates['server'])
    if (len(server) != len(server_template)
            or server[:-1] != server_template[:-1]):
        raise ObservationFailure('server argv differs from approved packet')
    template_world = Path(
        server_template[-1].replace('<session_uuid>', plan.session_id)
    )
    if 'B22_GUI_OBSERVATION_RUN001' in str(template_world):
        raise ObservationFailure('server template points to RUN001')
    if effective:
        expected_template = Path(
            str(template_world).replace(str(EVIDENCE_ROOT), str(evidence_root))
        )
        expected_world = (
            Path(evidence_root) / 'runtime_assets' / template_world.name
        )
        if (Path(server[-1]) != expected_world
                or Path(plan.world_file) != expected_world
                or expected_template != expected_world):
            raise ObservationFailure(
                'effective server world argv is not canonical RUN004 asset'
            )
    else:
        if runtime_dir is None:
            raise ValueError('staged plan validation requires runtime_dir')
        staged_world = Path(server[-1])
        if (staged_world.parent != Path(runtime_dir)
                or staged_world.name != template_world.name
                or Path(plan.world_file) != staged_world):
            raise ObservationFailure(
                'staged server world differs from bound RUN004 world'
            )
    if gui != tuple(templates['gui']):
        raise ObservationFailure('GUI argv differs from approved packet')
    bridge = tuple(getattr(plan, 'bridge_command', ()) or ())
    if bridge != tuple(templates['parameter_bridge']):
        raise ObservationFailure('bridge argv differs from approved packet')


def _check_output_tasks(supervisor, sink):
    """Raise on background stdout/stderr task failure without swallowing it."""
    for record in tuple(getattr(supervisor, 'owned', ())):
        for task in getattr(record, 'output_tasks', ()):
            if not task.done():
                continue
            if task.cancelled():
                raise ObservationFailure(
                    f'background output task was cancelled: {record.name}'
                )
            error = task.exception()
            if error is not None:
                sink.record('background_output_failure', {
                    'process': record.name,
                    'error_type': type(error).__name__,
                    'error': str(error)[:1000],
                })
                raise ObservationFailure(
                    f'background output evidence failed: {record.name}'
                ) from error


async def _monitor_owned_processes(
    *, launcher, supervisor, sink, stop_event, deadline, steady,
    review_state=None,
):
    """Continuously fail on owned role exits and background evidence errors."""
    reported_exits = set()
    while not stop_event.is_set():
        for record in tuple(launcher.records):
            if id(record.process) in reported_exits:
                continue
            waiter = launcher.waiters.get(id(record.process))
            if waiter is None or not waiter.done():
                continue
            if waiter.cancelled():
                raise ObservationFailure(
                    f'owned process waiter cancelled: {record.name}'
                )
            status = waiter.result()
            sink.record('owned_process_exit', {
                'process': record.name, 'pid': record.pid,
                'exit_status': status,
            })
            reported_exits.add(id(record.process))
            if (record.name in ('window_helper', 'capture_helper')
                    and status == 0):
                continue
            raise ObservationFailure(
                f'owned process exited unexpectedly: {record.name} ({status})'
            )
        _check_output_tasks(supervisor, sink)
        if review_state and review_state.get('path'):
            data = read_published(Path(review_state['path']))
            if sha256_bytes(data) != review_state['sha256']:
                raise ObservationFailure(
                    'accepted Codex result changed during observation'
                )
        if steady() >= deadline:
            raise ObservationFailure('240 s consume-to-end deadline expired')
        await asyncio.sleep(0.05)


async def _wait_competing(
    awaitable, monitor_task, deadline, steady, observer_task=None,
    wait_fn=asyncio.wait, cleanup_window=None,
):
    """Wait for one operation while process monitoring remains active."""
    operation = asyncio.ensure_future(awaitable)
    remaining = deadline - steady()
    try:
        if remaining <= 0:
            raise ObservationFailure('240 s consume-to-end deadline expired')
        competing = {operation, monitor_task}
        if observer_task is not None:
            competing.add(observer_task)
        done, _pending = await wait_fn(
            competing, timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if monitor_task in done:
            if monitor_task.cancelled():
                raise ObservationFailure('owned-process monitor was cancelled')
            error = monitor_task.exception()
            if error is not None:
                raise error
            raise ObservationFailure(
                'owned-process monitor stopped unexpectedly'
            )
        if observer_task is not None and observer_task in done:
            if observer_task.cancelled():
                raise ObservationFailure('observation monitor was cancelled')
            error = observer_task.exception()
            if error is not None:
                raise error
            raise ObservationFailure(
                'observation completed before Codex review acceptance'
            )
        if operation in done:
            if steady() >= deadline:
                raise ObservationFailure(
                    'competing operation completed at or after its deadline'
                )
            return operation.result()
        raise ObservationFailure('240 s consume-to-end deadline expired')
    finally:
        if not operation.done():
            cleanup_deadline = (
                cleanup_window.begin() if cleanup_window is not None
                else deadline
            )
            operation.cancel()
            remaining = max(0.0, cleanup_deadline - steady())
            done, _pending = await asyncio.wait(
                {operation}, timeout=remaining,
            )
            if done:
                await asyncio.gather(operation, return_exceptions=True)
            else:
                if cleanup_window is not None:
                    cleanup_window.pending_operations.append(operation)
                raise ObservationFailure(
                    'cancelled operation cleanup residue is UNKNOWN'
                )


async def _join_task(task, *, timeout_s):
    """Cancel and join one owned asyncio task within a bounded interval."""
    if task is None:
        return True
    if not task.done():
        task.cancel()
    done, _pending = await asyncio.wait({task}, timeout=max(0.0, timeout_s))
    if not done:
        return False
    await asyncio.gather(task, return_exceptions=True)
    return True


async def _run(args, *, dependencies=None):
    """Run one approved observation with injectable test boundaries."""
    deps = dependencies or {}
    mono = deps.get('monotonic', time.monotonic)
    wall_utc = deps.get('utc_now', _utc_now)
    require_run_gui(args.gui)
    preflight = deps.get('preflight', preflight_desktop)
    preflight(
        deps.get('stdin_isatty', sys.stdin.isatty()),
        deps.get('environ', os.environ),
        deps.get('exists', lambda path: Path(path).exists()),
    )
    packet_path = Path(
        deps.get('packet_path', PACKET_PATH)
    ).resolve(strict=True)
    approval_path = Path(
        deps.get('approval_path', APPROVAL_PATH)
    ).resolve(strict=True)
    packet, packet_hash, hashes = validate_approval(
        packet_path=packet_path, approval_path=approval_path,
        expected_commit=args.approved_commit, tool_paths=TOOL_PATHS,
    )
    bindings = assert_packet_inputs(packet, hashes)
    verify_commit = deps.get('verify_commit', verify_packet_commit)
    verify_commit(args.approved_commit, packet_path)
    try:
        verified_host_dependencies = deps.get(
            'verify_host_dependencies', verify_host_dependencies,
        )(
            packet,
            module_importer=deps.get('module_importer'),
            file_hasher=deps.get('dependency_file_hasher', sha256_file),
            package_version_reader=deps.get('package_version_reader'),
            python_executable=deps.get('python_executable'),
            python_version=deps.get('python_version'),
            path_resolver=deps.get('dependency_path_resolver', Path.resolve),
        )
    except BaseException as error:
        raise ObservationFailure(
            f'host dependency verification failed: {type(error).__name__}'
        ) from error
    injected_paths = dependencies is not None
    guard_path = Path(deps.get('guard_path', GUARD_PATH))
    evidence_root = Path(deps.get('evidence_root', EVIDENCE_ROOT))
    guard_path, evidence_root = validate_run_roots(
        guard_path, evidence_root,
        expected_guard=guard_path if injected_paths else GUARD_PATH,
        expected_evidence=evidence_root if injected_paths else EVIDENCE_ROOT,
    )
    if not evidence_root.exists():
        evidence_root.mkdir(mode=0o700, parents=False, exist_ok=False)
    if not guard_path.parent.is_dir():
        raise GuardError('canonical acquisition directory is unavailable')

    install_preflight = deps.get('install_preflight')
    install_fingerprints = install_preflight() if install_preflight else None
    temp_parent = Path(deps.get('temp_root', '/tmp'))
    temp_parent.mkdir(parents=True, exist_ok=True)
    runtime_dir_context = deps.get(
        'temporary_directory_factory', tempfile.TemporaryDirectory,
    )(
        prefix='b22_gui_observation_run004_', dir=temp_parent,
    )
    runtime_dir = Path(runtime_dir_context.name)
    try:
        plan, paths, descriptor, descriptor_path = deps.get(
            'build_plan', build_runtime_plan,
        )(args.gui, runtime_dir)
        plan = replace(
            plan, environment={
                **dict(plan.environment), 'ROS_DOMAIN_ID': '83',
                'QT_QPA_PLATFORM': 'xcb',
            },
        )
        _validate_plan_commands(
            plan, packet, runtime_dir=runtime_dir,
            evidence_root=evidence_root,
        )
    except BaseException:
        runtime_dir_context.cleanup()
        raise
    fingerprints = install_fingerprints or _fingerprint_install(paths)
    if fingerprints != bindings['file_sha256']:
        runtime_dir_context.cleanup()
        raise ObservationFailure(
            'installed file fingerprints differ from packet'
        )
    if (not isinstance(plan.session_id, str)
            or not re.fullmatch(
                r'[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-'
                r'[89ab][0-9a-f]{3}-[0-9a-f]{12}', plan.session_id,
            )
            or type(plan.coordinator_ingress_instance_id) is not int
            or plan.coordinator_ingress_instance_id <= 0
            or plan.coordinator_ingress_instance_id >= 1 << 64
            or plan.environment.get('GZ_PARTITION') != (
                f"mecanum_b2_{plan.session_id.replace('-', '')}")):
        runtime_dir_context.cleanup()
        raise ObservationFailure('runtime identity propagation mismatch')
    ros2_template = tuple(
        packet['commands_argv']['exact_templates'][
            'robot_state_publisher'
        ]
    )
    if injected_paths:
        ros2_template = tuple(
            value.replace(str(EVIDENCE_ROOT), str(evidence_root))
            for value in ros2_template
        )
    ros2_executable = deps.get('ros2_executable') or shutil.which('ros2')
    params_path = evidence_root / 'runtime_assets'
    params_path /= 'robot_state_publisher.params.yaml'
    planned_rsp_command = (
        ros2_executable, 'run', 'robot_state_publisher',
        'robot_state_publisher', '--ros-args', '--params-file',
        str(params_path),
    )
    if (not ros2_executable or ros2_executable != ros2_template[0]
            or planned_rsp_command != ros2_template):
        runtime_dir_context.cleanup()
        raise ObservationFailure(
            'robot_state_publisher argv differs from approved packet'
        )
    if not Path(ros2_executable).is_file():
        runtime_dir_context.cleanup()
        raise ObservationFailure('installed ros2 executable is missing')

    run_id = deps.get('run_id', RUN_ID)
    process_identity = deps.get(
        'runner_process_identity', process_start_identity,
    )(os.getpid())
    acquisition = {
        'schema_id': 'b22_gui_observation_acquisition/v1',
        'run_id': run_id,
        'capacity': 1,
        'packet_sha256': packet_hash,
        'packet_commit': args.approved_commit,
        'production_source_pin': bindings['production_source_pin'],
        'tool_sha256': hashes,
        'input_sha256': bindings['input_sha256'],
        'installed_sha256': fingerprints,
        'dependency_fingerprints': verified_host_dependencies,
        'resolved_install_paths': {
            key: str(value) for key, value in paths.items()
        },
        'session_id': plan.session_id,
        'coordinator_ingress_instance_id': (
            plan.coordinator_ingress_instance_id
        ),
        'gz_partition': plan.environment['GZ_PARTITION'],
        'ros_domain_id': 83,
        'runtime_bound_world_sha256': descriptor['runtime_bound_world_sha256'],
        'robot_state_publisher_params_sha256': descriptor[
            'robot_state_publisher_params_sha256'
        ],
        'run_descriptor_sha256': sha256_file(descriptor_path),
        'host': deps.get('host_identity', _host_identity)(),
        'runner_process': process_identity,
        'steady_ns': deps.get('monotonic_ns', time.monotonic_ns)(),
        'utc_time': wall_utc(),
    }
    try:
        deps.get('acquire', acquire_once)(guard_path, acquisition)
    except BaseException:
        runtime_dir_context.cleanup()
        raise

    consumed_at = mono()
    runtime_deadline = consumed_at + RUNTIME_CAP_S
    total_deadline = consumed_at + TOTAL_CAP_S
    cleanup_window = CleanupWindow(consumed_at, total_deadline, mono)
    sink = None
    supervisor = None
    launcher = None
    observer = None
    observer_task = None
    process_monitor_task = None
    stop_monitor = asyncio.Event()
    review_pass_event = asyncio.Event()
    final_status = 'FAIL'
    observation_verdict = 'FAIL'
    failure = None
    cleanup_errors = []
    original_environment = {}
    readiness_complete_event = asyncio.Event()
    bound_environment = {'ROS_DOMAIN_ID': '83', **dict(plan.environment)}
    try:
        if not evidence_root.exists():
            evidence_root.mkdir(mode=0o700, parents=False, exist_ok=False)
        sink = deps.get('sink_factory', ObservationEvidenceSink)(
            evidence_root, run_id, plan.session_id,
        )
        sink.record('guard_consumed', {
            'packet_sha256': packet_hash,
            'packet_commit': args.approved_commit,
            'production_source_pin': bindings['production_source_pin'],
            'tool_sha256': hashes,
            'descriptor_path': str(descriptor_path),
            'descriptor_sha256': sha256_file(descriptor_path),
            'source_world_sha256': descriptor['world_source_sha256'],
            'runtime_bound_world_sha256': descriptor[
                'runtime_bound_world_sha256'
            ],
            'install_fingerprints': fingerprints,
            'dependency_fingerprints': verified_host_dependencies,
        })
        evidence_assets = evidence_root / 'runtime_assets'
        evidence_assets.mkdir(mode=0o700, exist_ok=False)
        persisted_world = evidence_assets / Path(plan.world_file).name
        persisted_params = evidence_assets / (
            'robot_state_publisher.params.yaml'
        )
        persisted_descriptor = evidence_assets / 'run_descriptor.json'
        _exclusive_copy(Path(plan.world_file), persisted_world)
        _exclusive_copy(runtime_dir / persisted_params.name, persisted_params)
        _exclusive_copy(descriptor_path, persisted_descriptor)
        commands = list(plan.commands)
        commands[0] = tuple(commands[0][:-1]) + (str(persisted_world),)
        plan = replace(
            plan, world_file=persisted_world, commands=tuple(commands),
        )
        _validate_plan_commands(
            plan, packet, evidence_root=evidence_root, effective=True,
        )
        sink.record('runtime_assets_persisted', {
            'runtime_bound_world_path': str(persisted_world),
            'runtime_bound_world_sha256': sha256_file(persisted_world),
            'run_descriptor_path': str(persisted_descriptor),
            'run_descriptor_sha256': sha256_file(persisted_descriptor),
            'robot_state_publisher_params_path': str(persisted_params),
            'robot_state_publisher_params_sha256': sha256_file(
                persisted_params
            ),
        })
        original_environment = {
            key: os.environ.get(key) for key in bound_environment
        }
        os.environ.update(bound_environment)

        from mecanum_nav_bringup.local_training_process_supervisor import (
            LocalTrainingProcessSupervisor, ProcessRecord,
            RclpyReadiness, SubprocessProcessLauncher,
        )

        class Run004Readiness(RclpyReadiness):
            """Bind worker cleanup to the run's one cleanup window."""

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._run_cleanup_window = cleanup_window

            async def _finalize_worker(self):
                failed = sys.exc_info()[0] is not None
                if failed and self._worker_cleanup_deadline is None:
                    shared_deadline = self._run_cleanup_window.begin()
                    remaining = max(
                        0.0, shared_deadline - self._monotonic(),
                    )
                    self.CLEANUP_CAP_S = min(
                        self.CLEANUP_CAP_S, remaining,
                    )
                await super()._finalize_worker()

        def sink_factory(record, identity):
            return sink.record('owned_process_identity', {
                'process': record.name, 'command': list(record.command),
                'pid': record.pid, 'process_identity': identity,
            })
        launcher = TrackedProcessLauncher(
            deps.get('launcher', SubprocessProcessLauncher()),
            on_start=sink_factory,
            identity_reader=deps.get('process_identity_reader'),
            proc_root=deps.get('proc_root', Path('/proc')),
            signal_process=deps.get('signal_process', os.kill),
            process_inventory=deps.get('process_inventory'),
        )
        if 'readiness' in deps:
            readiness_base = deps['readiness']
        elif deps.get('readiness_factory') is not None:
            readiness_base = deps['readiness_factory'](Run004Readiness)
        else:
            readiness_base = Run004Readiness()
        readiness = ReadinessAdapter(
            readiness_base, readiness_complete_event, plan.environment,
        )
        if deps.get('supervisor_factory'):
            supervisor = deps['supervisor_factory'](
                plan=plan, launcher=launcher, readiness=readiness,
                evidence_sink=sink,
            )
        else:
            supervisor = ResilientSupervisor(
                LocalTrainingProcessSupervisor, plan=plan, launcher=launcher,
                readiness=readiness, evidence_sink=sink,
                cleanup_window=cleanup_window,
                cleanup_errors=cleanup_errors,
                cleanup_options={
                    'sleep': deps.get('cleanup_sleep', asyncio.sleep),
                    'escalation_grace': deps.get(
                        'cleanup_escalation_grace', (5.0, 3.0, 3.0),
                    ),
                },
            )
        observer = deps.get('observer_factory', PassiveBackendObserver)()
        observer.start()
        sink.record('passive_observer_started', {
            'node': 'b22_gui_observation_observer',
            'ros_domain_id': 83,
            'subscriptions': [
                '/mecanum/local_training/backend_state', '/clock',
            ],
            'control_publishers': 0,
            'control_service_clients': 0,
        })
        review_state = {}
        process_monitor_task = asyncio.create_task(_monitor_owned_processes(
            launcher=launcher, supervisor=supervisor,
            sink=sink, stop_event=stop_monitor,
            deadline=runtime_deadline, steady=mono,
            review_state=review_state,
        ))
        observation_evaluator = deps.get(
            'evaluate_observation', evaluate_observation,
        )
        observer_task = asyncio.create_task(observation_evaluator(
            plan=plan, observer=observer, duration_s=OBSERVATION_S,
            steady=mono, ack_event=review_pass_event,
            deadline=runtime_deadline, sink=sink,
            expected_nodes={
                (name, packet['composition']['namespace'])
                for name in packet['composition']['persistent_ros_nodes']
            },
            temporary_nodes={
                (name, packet['composition']['namespace'])
                for name in packet['composition'][
                    'startup_temporary_ros_nodes'
                ]
            },
            readiness_complete_event=readiness_complete_event,
            graph_convergence_s=packet['composition'][
                'graph_convergence_after_readiness_s'
            ],
            temporary_stale_s=packet['composition'][
                'temporary_node_stale_after_readiness_s'
            ],
        ))
        rsp_command = planned_rsp_command
        rsp = await _wait_competing(
            launcher.start(rsp_command, dict(plan.environment)),
            process_monitor_task, runtime_deadline, mono, observer_task,
            cleanup_window=cleanup_window,
        )
        rsp_record = ProcessRecord(
            'robot_state_publisher', rsp_command, rsp.pid, rsp,
        )
        supervisor.owned.append(rsp_record)
        capture_output = getattr(supervisor, '_capture_output', None)
        if capture_output is not None:
            capture_output(rsp_record)
        sink.record('owned_process_started', {
            'process': rsp_record.name, 'command': list(rsp_command),
            'pid': rsp.pid,
            'process_identity': launcher.identities.get(id(rsp)),
        })
        await _wait_competing(
            supervisor.start(), process_monitor_task, runtime_deadline, mono,
            observer_task, cleanup_window=cleanup_window,
        )
        if runtime_deadline - mono() < 121.0:
            raise ObservationFailure(
                'insufficient active budget to begin review and observation'
            )
        review_started = mono()
        review_deadline = min(review_started + REVIEW_CHECKPOINT_S,
                              runtime_deadline)
        review_deadline_ns = deps.get(
            'monotonic_ns', time.monotonic_ns,
        )() + int(
            max(0.0, review_deadline - review_started) * 1_000_000_000
        )
        partition = plan.environment['GZ_PARTITION']
        window = await _wait_competing(
            deps.get('bind_gui_window', bind_gui_window)(
                launcher=launcher, environment=bound_environment,
                partition=partition, deadline=review_deadline, steady=mono,
                sink=sink,
            ),
            process_monitor_task, review_deadline, mono, observer_task,
            wait_fn=deps.get('binding_wait_fn', asyncio.wait),
            cleanup_window=cleanup_window,
        )
        window['evidence_sequence'] = sink.record('gui_window_bound', {
            key: value for key, value in window.items()
            if key != 'evidence_sequence'
        })
        request_id = str(uuid.uuid4())
        screenshot_dir = evidence_root / 'screenshots'
        if not screenshot_dir.exists():
            screenshot_dir.mkdir(mode=0o700)
        capture = await _wait_competing(
            deps.get(
                'capture_window_bounded', capture_x11_window_bounded,
            )(
                window['window_id'], launcher=launcher,
                environment=bound_environment, deadline=review_deadline,
                steady=mono, sink=sink,
            ),
            process_monitor_task, review_deadline, mono, observer_task,
            cleanup_window=cleanup_window,
        )
        capture_facts = _capture_payload_facts(capture.get('png_bytes'))
        for key in ('sha256', 'width', 'height', 'size_bytes'):
            if capture.get(key) != capture_facts[key]:
                raise ObservationFailure(
                    f'capture worker {key} differs from parent validation'
                )
        screenshot_path = screenshot_dir / (
            f'{request_id}-{capture_facts["sha256"]}.png'
        )
        atomic_publish(screenshot_path, capture_facts.pop('png_bytes'))
        capture = capture_facts
        capture['path'] = str(screenshot_path)
        sink.record('window_screenshot_captured', {
            'window_id': window['window_id'],
            'screenshot_path': str(screenshot_path),
            'screenshot_sha256': capture['sha256'],
            'width': capture['width'], 'height': capture['height'],
            'size_bytes': capture['size_bytes'],
        })
        request_path, request_bytes, request = publish_review_request(
            root=evidence_root, packet_hash=packet_hash,
            session_id=plan.session_id, window=window, screenshot=capture,
            request_id=request_id,
            created_steady_ns=deps.get('monotonic_ns', time.monotonic_ns)(),
            deadline_steady_ns=review_deadline_ns, utc_now=wall_utc,
        )
        sink.record('codex_review_request_published', {
            'request_path': str(request_path),
            'request_sha256': sha256_bytes(request_bytes),
            'screenshot_sha256': capture['sha256'],
            'review_deadline_steady_ns': review_deadline_ns,
        })
        print(
            'RUN004_REVIEW_READY '
            + json.dumps({'request_id': request_id,
                          'request_path': str(request_path)},
                         sort_keys=True),
            flush=True,
        )
        review_waiter = deps.get('await_review', await_codex_review)
        review = await _wait_competing(
            review_waiter(
                request_path=request_path, request_bytes=request_bytes,
                request=request, deadline=review_deadline, steady=mono,
                sink=sink, stop_event=stop_monitor,
                monotonic_ns=deps.get('monotonic_ns', time.monotonic_ns),
                read_file=deps.get('read_published', read_published),
            ),
            process_monitor_task, runtime_deadline, mono, observer_task,
            cleanup_window=cleanup_window,
        )
        sink.record('automated_visual_review', {
            'automated_observation_verdict': review['verdict'],
            'owner_visual_review': 'NOT_PERFORMED',
            'reviewer_kind': 'CODEX',
            'reason': review['reason'],
            'screenshot_sha256': capture['sha256'],
        })
        review_state.update({
            'path': request['result_path'],
            'sha256': sha256_bytes(read_published(
                Path(request['result_path']),
            )),
        })
        review_pass_event.set()
        verdict = await _wait_competing(
            observer_task, process_monitor_task, runtime_deadline, mono,
            cleanup_window=cleanup_window,
        )
        verdict.update({
            'automated_observation_verdict': 'PASS',
            'owner_visual_review': 'NOT_PERFORMED',
            'codex_review_request_id': request_id,
            'screenshot_sha256': capture['sha256'],
        })
        sink.record('observation_result', verdict)
        observation_verdict = 'PASS'
        final_status = 'PASS'
        if mono() > runtime_deadline:
            raise ObservationFailure('240 s runtime cap exceeded')
    except BaseException as error:
        failure = error
        final_status = 'FAIL'
        observation_verdict = 'FAIL'
        if sink is not None:
            try:
                sink.record('observation_failure', {
                    'error_type': type(error).__name__,
                    'error': str(error)[:1000],
                    'traceback': ''.join(traceback.format_exception(
                        type(error), error, error.__traceback__,
                    ))[-12000:],
                })
            except BaseException as sink_error:
                cleanup_errors.append(
                    f'evidence_failure:{type(sink_error).__name__}'
                )
    finally:
        cleanup_deadline = cleanup_window.begin()
        cleanup_start = cleanup_window.started_at
        stop_monitor.set()
        observer_task_joined = observer_task is None
        for task in (observer_task, process_monitor_task):
            try:
                joined = await _join_task(
                    task, timeout_s=max(0.0, cleanup_deadline - mono()),
                )
                if task is observer_task:
                    observer_task_joined = joined
                if not joined:
                    cleanup_errors.append('async_task_residue_unknown')
            except BaseException as error:
                if task is observer_task:
                    observer_task_joined = False
                cleanup_errors.append(
                    f'task_cleanup:{type(error).__name__}:{error}'
                )
        if observer is not None:
            if observer_task_joined:
                try:
                    observer.close(
                        deadline=cleanup_deadline, steady=mono,
                    )
                except BaseException as error:
                    cleanup_errors.append(
                        f'observer_close:{type(error).__name__}:{error}'
                    )
            else:
                cleanup_errors.append('observer_context_residue_unknown')
        all_records = (
            list(getattr(launcher, 'records', ())) if launcher else []
        )
        supervisor_records = (
            list(getattr(supervisor, 'owned', ()))
            if supervisor is not None else []
        )
        if supervisor is not None:
            try:
                remaining = max(0.0, cleanup_deadline - mono())
                cleanup_task = asyncio.create_task(supervisor.cleanup())
                done, _pending = await asyncio.wait(
                    {cleanup_task}, timeout=remaining,
                )
                if cleanup_task in done:
                    error = cleanup_task.exception()
                    if error is not None:
                        cleanup_errors.append(
                            'supervisor_cleanup:'
                            f'{type(error).__name__}:{error}'
                        )
                else:
                    cleanup_task.cancel()
                    cleanup_errors.append('supervisor_cleanup_timeout')
                    joined, _pending = await asyncio.wait(
                        {cleanup_task},
                        timeout=max(0.0, cleanup_deadline - mono()),
                    )
                    if joined:
                        await asyncio.gather(
                            cleanup_task, return_exceptions=True,
                        )
                    else:
                        cleanup_errors.append(
                            'supervisor_cleanup_task_residue_unknown'
                        )
            except BaseException as error:
                cleanup_errors.append(
                    f'supervisor_cleanup:{type(error).__name__}:{error}'
                )
        for operation in cleanup_window.pending_operations:
            remaining = max(0.0, cleanup_deadline - mono())
            if not operation.done() and remaining > 0:
                await asyncio.wait({operation}, timeout=remaining)
            if operation.done():
                await asyncio.gather(operation, return_exceptions=True)
            else:
                cleanup_errors.append(
                    'competing_operation_task_residue_unknown'
                )
        for record in supervisor_records:
            for task in getattr(record, 'output_tasks', ()):
                if task.cancelled():
                    continue
                if task.done() and task.exception() is not None:
                    cleanup_errors.append(
                        f'background_output_failure:{record.name}:'
                        f'{type(task.exception()).__name__}'
                    )
        if launcher is not None and all_records:
            try:
                await _fallback_cleanup(
                    launcher, all_records, sink, cleanup_errors,
                    deadline=cleanup_deadline, steady=mono,
                    sleep=deps.get('cleanup_sleep', asyncio.sleep),
                    escalation_grace=deps.get(
                        'cleanup_escalation_grace', (5.0, 3.0, 3.0),
                    ),
                )
            except BaseException as error:
                cleanup_errors.append(
                    f'fallback_cleanup:{type(error).__name__}:{error}'
                )
        if launcher is not None:
            for record in all_records:
                if record.identity_error:
                    cleanup_errors.append(
                        'identity_unknown:'
                        f'{record.name}:{record.identity_error}'
                    )
            for task in launcher.waiters.values():
                try:
                    if not await _join_task(
                        task, timeout_s=max(0.0, cleanup_deadline - mono()),
                    ):
                        cleanup_errors.append('process_waiter_residue_unknown')
                except BaseException as error:
                    cleanup_errors.append(
                        'process_waiter_cleanup:'
                        f'{type(error).__name__}:{error}'
                    )
        for key, previous in original_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        try:
            runtime_dir_context.cleanup()
        except BaseException as error:
            cleanup_errors.append(
                f'runtime_dir_cleanup:{type(error).__name__}:{error}'
            )
        if mono() - cleanup_start > CLEANUP_CAP_S:
            cleanup_errors.append('cleanup_deadline_exceeded')
        if mono() > total_deadline:
            cleanup_errors.append('consume_to_end_deadline_exceeded')
        if mono() > cleanup_deadline:
            cleanup_errors.append('cleanup_deadline_exceeded')
        finalization_deadline = min(cleanup_deadline, total_deadline)

        def check_finalization_deadline(stage, *, record_if_possible=False):
            nonlocal final_status
            if mono() <= finalization_deadline:
                return
            reason = f'finalization_deadline_exceeded:{stage}'
            if reason not in cleanup_errors:
                cleanup_errors.append(reason)
            final_status = 'FAIL'
            if record_if_possible:
                try:
                    sink.record('finalization_deadline_violation', {
                        'stage': stage,
                        'deadline_steady': finalization_deadline,
                    })
                except BaseException as error:
                    cleanup_errors.append(
                        'finalization_deadline_evidence_failure:'
                        f'{type(error).__name__}'
                    )
        if cleanup_errors:
            final_status = 'FAIL'
        if sink is not None:
            try:
                sink.record('observation_verdict', {
                    'status': observation_verdict,
                    'automated_observation_verdict': observation_verdict,
                    'owner_visual_review': 'NOT_PERFORMED',
                    'failure_type': (
                        type(failure).__name__ if failure else None
                    ),
                })
                sink.record('final_status', {
                    'status': final_status,
                    'observation_status': observation_verdict,
                    'automated_observation_verdict': observation_verdict,
                    'owner_visual_review': 'NOT_PERFORMED',
                    'evidence_close_required_for_validity': True,
                    'failure_type': (
                        type(failure).__name__ if failure else None
                    ),
                    'cleanup_elapsed_s': mono() - cleanup_start,
                    'cleanup_errors': cleanup_errors,
                })
                check_finalization_deadline(
                    'final_status_record', record_if_possible=True,
                )
            except BaseException as error:
                final_status = 'FAIL'
                cleanup_errors.append(
                    f'final_evidence_write:{type(error).__name__}:{error}'
                )
                try:
                    sink.record('evidence_incomplete', {
                        'reason': cleanup_errors[-1],
                    })
                except BaseException:
                    pass
            close_ok = False
            try:
                sink.close()
                close_ok = True
                check_finalization_deadline('sink_close')
            except BaseException as error:
                final_status = 'FAIL'
                cleanup_errors.append(
                    f'evidence_close:{type(error).__name__}:{error}'
                )
            if close_ok:
                try:
                    stream_path = evidence_root / 'observation.jsonl'
                    completion = {
                        'schema_id': 'b22_gui_observation_completion/v1',
                        'run_id': run_id,
                        'session_id': plan.session_id,
                        'status': final_status,
                        'automated_observation_verdict': observation_verdict,
                        'owner_visual_review': 'NOT_PERFORMED',
                        'stream_sha256': deps.get(
                            'stream_hasher', sha256_file,
                        )(stream_path),
                        'cleanup_errors': cleanup_errors,
                        'completed_utc': wall_utc(),
                    }
                    check_finalization_deadline('stream_hash')
                    completion['status'] = final_status
                    completion['cleanup_errors'] = cleanup_errors
                    deps.get('completion_publisher', atomic_publish)(
                        evidence_root / 'final_result.json',
                        (json.dumps(completion, sort_keys=True,
                                    separators=(',', ':')) + '\n').encode(),
                    )
                    check_finalization_deadline('completion_publication')
                except BaseException as error:
                    final_status = 'FAIL'
                    cleanup_errors.append(
                        f'evidence_completion:{type(error).__name__}:{error}'
                    )
    if mono() > min(cleanup_window.begin(), total_deadline):
        final_status = 'FAIL'
        if ('finalization_deadline_exceeded:runner_return'
                not in cleanup_errors):
            cleanup_errors.append(
                'finalization_deadline_exceeded:runner_return'
            )
        print(
            'RUN004_FINALIZATION_DEADLINE_VIOLATION '
            'stage=runner_return marker_may_be_non_authoritative',
            file=sys.stderr, flush=True,
        )
    return final_status


async def _fallback_cleanup(
    launcher, records, sink, errors, *, deadline=None,
    steady=time.monotonic, sleep=asyncio.sleep,
    escalation_grace=(5.0, 3.0, 3.0),
):
    """Escalate captured process groups and retain ownership records."""
    unique = {id(record.process): record for record in records}
    owned = list(reversed(list(unique.values())))
    signals = (signal.SIGINT, signal.SIGTERM, signal.SIGKILL)
    if len(escalation_grace) != len(signals):
        raise ValueError('cleanup escalation grace must have three stages')
    if deadline is None:
        raise ValueError('cleanup requires the runner shared deadline')
    cleanup_deadline = deadline
    for sig, grace in zip(signals, escalation_grace):
        if steady() >= cleanup_deadline:
            break
        for record in owned:
            if steady() >= cleanup_deadline:
                break
            try:
                if launcher.group_alive(record.process):
                    await launcher.stop_group(record.process, sig)
            except BaseException as error:
                errors.append(
                    f'cleanup:{record.name}:{type(error).__name__}:{error}'
                )
        stage_deadline = min(cleanup_deadline, steady() + grace)
        while steady() < stage_deadline:
            live = []
            for record in owned:
                try:
                    if launcher.group_alive(record.process):
                        live.append(record)
                except BaseException as error:
                    errors.append(
                        'identity:'
                        f'{record.name}:{type(error).__name__}:{error}'
                    )
            if not live:
                break
            await sleep(min(0.05, max(0.0, stage_deadline - steady())))
        if not any(
            _safe_group_alive(launcher, record, errors) for record in owned
        ):
            break
        if steady() >= cleanup_deadline:
            break
    for record in owned:
        try:
            if launcher.group_alive(record.process):
                errors.append(f'residue:process_group:{record.pid}')
        except BaseException as error:
            errors.append(
                f'residue_unknown:{record.name}:{type(error).__name__}:{error}'
            )
        try:
            if sink is not None:
                sink.record('fallback_cleanup_attempt', {
                    'process': record.name, 'pid': record.pid,
                    'ownership_record_retained': True,
                })
        except BaseException as error:
            errors.append(f'cleanup_evidence:{type(error).__name__}')


def _safe_group_alive(launcher, record, errors):
    """Check ownership without skipping remaining groups on failure."""
    try:
        return launcher.group_alive(record.process)
    except BaseException as error:
        errors.append(
            f'residue_unknown:{record.name}:{type(error).__name__}:{error}'
        )
        return True


def verify_packet_commit(commit: str, packet_path: Path) -> None:
    """Require current HEAD and committed packet bytes to match approval."""
    root = Path(__file__).resolve().parents[5]
    head = subprocess.run(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if head != commit:
        raise GuardError('current HEAD differs from approved packet commit')
    relative = packet_path.resolve().relative_to(root.resolve())
    committed = subprocess.run(
        ['git', '-C', str(root), 'show', f'{commit}:{relative.as_posix()}'],
        check=True, capture_output=True,
    ).stdout
    if committed != packet_path.read_bytes():
        raise GuardError('working packet bytes differ from approved commit')


def parse_args(argv=None):
    """Parse runtime or the file-only bounded Codex result publisher."""
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--publish-review-result', metavar='REQUEST')
    mode.add_argument('--review-publish-worker', metavar='REQUEST')
    mode.add_argument('--capture-worker', metavar='WINDOW_ID')
    parser.add_argument('--gui', type=strict_gui_value)
    parser.add_argument('--approved-commit')
    parser.add_argument('--verdict', choices=('PASS', 'FAIL'))
    parser.add_argument('--reason')
    parser.add_argument('--viewer-ref')
    parser.add_argument('--viewer-ref-state', choices=(
        'AVAILABLE', 'TOOL_NO_STABLE_REFERENCE',
    ), default='TOOL_NO_STABLE_REFERENCE')
    return parser.parse_args(argv)


def main(argv=None):
    """Execute one runtime invocation or the no-middleware review publisher."""
    args = parse_args(argv)
    if args.review_publish_worker:
        try:
            path = publish_review_result_worker(
                args.review_publish_worker, verdict=args.verdict,
                reason=args.reason or '',
                viewer_interaction_ref=args.viewer_ref,
                viewer_ref_state=args.viewer_ref_state,
            )
        except BaseException as error:
            raise SystemExit(
                f'RUN004 review publisher worker: {error}'
            ) from error
        print(str(path))
        return
    if args.capture_worker:
        try:
            data = capture_worker_png(args.capture_worker)
        except BaseException as error:
            raise SystemExit(
                f'RUN004 capture worker: {type(error).__name__}:{error}'
            ) from error
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return
    if args.publish_review_result:
        try:
            request_path = Path(args.publish_review_result)
            request_bytes = read_published(request_path)
            request = strict_json_loads(request_bytes)
            validate_review_request(
                request, evidence_root=EVIDENCE_ROOT,
                packet_hash=request.get('packet_sha256'),
                session_id=request.get('session_id'),
            )
            remaining = (
                request['review_deadline_steady_ns'] - time.monotonic_ns()
            ) / 1_000_000_000
            result = publish_review_result_bounded(
                request_path, verdict=args.verdict or '',
                reason=args.reason or '',
                viewer_interaction_ref=args.viewer_ref,
                viewer_ref_state=args.viewer_ref_state,
                request_deadline=time.monotonic() + remaining,
            )
        except BaseException as error:
            raise SystemExit(f'RUN004 review publisher: {error}') from error
        print(json.dumps(result, sort_keys=True))
        return
    if args.gui is None or not args.approved_commit:
        raise SystemExit('--gui and --approved-commit are required')
    try:
        status = asyncio.run(_run(args))
    except BaseException as error:
        raise SystemExit(f'{RUN_ID}: {error}') from error
    if status != 'PASS':
        raise SystemExit(f'{RUN_ID}: {status}')
    print(f'{RUN_ID}: PASS')


if __name__ == '__main__':
    main()
