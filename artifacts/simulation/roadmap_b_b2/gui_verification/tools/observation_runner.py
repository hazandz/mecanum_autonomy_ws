"""B2.2: profile XCB cô lập, review Codex và supervisor production."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

REPOSITORY = Path(__file__).resolve().parents[5]
HISTORICAL_TOOLS = REPOSITORY / 'artifacts/simulation/roadmap_b_b2/gui_observation_run008/tools'
sys.path.insert(0, str(HISTORICAL_TOOLS))
# Chỉ dùng API capture/binding; không gọi entry point hay capacity RUN008.
import observation_runner as capture
# Module hiện tại cần tên riêng khi import bằng importlib (CLI không tên observation_runner).


def digest(data):
    return hashlib.sha256(data).hexdigest()


INSTALL_INPUTS = (
    'lib/libmecanum_sim_backend_system.so',
    'lib/libmecanum_sim_backend_core.so',
    'lib/libmecanum_heartbeat_trace_writer.so',
    'lib/python3.12/site-packages/mecanum_nav_bringup/local_training_process_supervisor.py',
    'lib/python3.12/site-packages/mecanum_nav_bringup/local_training_launch_contract.py',
    'lib/python3.12/site-packages/mecanum_nav_bringup/local_training_readiness_worker.py',
    'lib/python3.12/site-packages/mecanum_nav_bringup/local_training_heartbeat_trace_observer.py',
    'lib/python3.12/site-packages/mecanum_nav_rl/config/v3_models.py',
    'lib/python3.12/site-packages/mecanum_nav_rl_interfaces/msg/__init__.py',
    'share/mecanum_nav_bringup/config/gui/local_training.config',
    'share/mecanum_nav_bringup/config/bridge/local_training.runtime.yaml',
    'share/ROBOT_URDF_final_description/worlds/b2_training_arena.sdf',
    'share/ROBOT_URDF_final_description/models/mecanum_b2/model.sdf',
    'share/ROBOT_URDF_final_description/urdf/mecanum_b2_static.urdf',
    'share/ROBOT_URDF_final_description/manifests/b2/asset_manifest.json',
    'share/mecanum_nav_rl/config/v3/resolved/sim_train_local_training_soak.resolved.json',
    'share/mecanum_nav_rl/scenarios/local_training/B2_SOAK_V1.json',
)


def profile_inputs(prefix):
    """Pin toàn bộ install và các module capture dùng từ source snapshot."""
    paths = {prefix / rel for rel in INSTALL_INPUTS}
    paths.update(p for p in prefix.rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    paths.add(Path(__file__).resolve())
    paths.update(HISTORICAL_TOOLS / name for name in (
        'observation_runner.py', 'observation_sink.py', 'observation_guard.py',
    ))
    return paths


def verify_profile(args):
    """Kiểm hồ sơ/hash trước consume và trước mọi subprocess của lượt."""
    raw = Path(args.profile).resolve(strict=True).read_bytes()
    if digest(raw) != args.profile_sha256:
        raise ValueError('profile SHA-256 mismatch')
    profile = capture.strict_json_loads(raw, max_bytes=4*1024*1024)
    if profile.get('mode', 'gui') not in ('gui', 'contact_probe_only'):
        raise ValueError('unsupported run mode')
    if profile.get('mode') == 'contact_probe_only':
        if digest(Path(profile['engine_file']).read_bytes()) != profile['physics_engine_sha256']:
            raise ValueError('contact engine fingerprint mismatch')
    if profile.get('schema') != 'b22_gui_profile/v2':
        raise ValueError('unsupported profile schema')
    if (not re.fullmatch(r'b22-[a-z0-9-]+\.service', profile.get('unit', ''))
            or profile.get('parent_argv', [None])[0] != '/bin/bash'
            or len(profile['parent_argv']) != 2
            or Path(profile['parent_argv'][1]).parent != Path(args.evidence)):
        raise ValueError('profile unit/parent command invalid')
    for key in ('run_id', 'source_commit', 'authority'):
        if profile.get(key) != getattr(args, key):
            raise ValueError('profile binding mismatch: '+key)
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        raise ValueError('source commit must be an exact full SHA')
    if not re.fullmatch(r'[A-Za-z0-9_]+', args.run_id) or not args.authority.strip():
        raise ValueError('invalid run ID or missing authority')
    prefix = Path(args.install).resolve(strict=True)
    root = Path(args.evidence).resolve(strict=True)
    if (profile.get('install') != str(prefix)
            or profile.get('evidence') != str(root)
            or profile.get('python') != str(Path(sys.executable).resolve())):
        raise ValueError('profile path/interpreter mismatch')
    expected = profile.get('files')
    required = {str(p) for p in profile_inputs(prefix)}
    if not isinstance(expected, dict) or set(expected) != required:
        raise ValueError('profile file inventory incomplete or changed')
    for path, checksum in expected.items():
        if (not isinstance(checksum, str) or not re.fullmatch(r'[0-9a-f]{64}', checksum)
                or digest(Path(path).read_bytes()) != checksum):
            raise ValueError('profile file SHA-256 mismatch: '+path)
    return profile


def worker_command(args):
    """Một argv canonical cho packet và quan sát /proc, không hash lệnh dự đoán."""
    return [sys.executable, '-B', str(Path(__file__).resolve()),
            '--evidence', args.evidence, '--run-id', args.run_id,
            '--install', args.install, '--source-commit', args.source_commit,
            '--authority', args.authority, '--profile', args.profile,
            '--profile-sha256', args.profile_sha256]


def execution_observations():
    """Biên I/O: giữ chính bytes /proc đã dùng để suy identity và argv."""
    def observe(pid):
        directory = Path('/proc')/str(pid)
        raw = {name: (directory/name).read_bytes().hex()
               for name in ('stat', 'cmdline', 'cgroup', 'status')}
        raw['stat_after'] = (directory/'stat').read_bytes().hex()
        return raw
    return {'parent': observe(os.getppid()), 'worker': observe(os.getpid()),
            'invocation_id': os.environ.get('INVOCATION_ID'),
            'collected_ns': time.monotonic_ns()}


def normalize_execution(profile, expected_worker, raw):
    """Ràng buộc unit/process thật với profile trước consume/spawn ROS."""
    def parse(record):
        def identity(hex_stat):
            data = bytes.fromhex(hex_stat).decode('utf-8')
            fields = data[data.rfind(')')+2:].split()
            if fields[0] not in ('R', 'S', 'D'):
                raise ValueError('execution process not live')
            return {'pid': int(data.split(' ', 1)[0]), 'parent_pid': int(fields[1]),
                    'process_group_id': int(fields[2]), 'session_id': int(fields[3]),
                    'start_ticks': int(fields[19])}
        result = identity(record['stat'])
        if result != identity(record['stat_after']):
            raise ValueError('execution identity changed during observation')
        cmdline = bytes.fromhex(record['cmdline'])
        if not cmdline.endswith(b'\0') or not cmdline[:-1]:
            raise ValueError('execution cmdline incomplete')
        result['argv'] = [part.decode('utf-8') for part in cmdline[:-1].split(b'\0')]
        groups = bytes.fromhex(record['cgroup']).decode().splitlines()
        unified = [line[3:] for line in groups if line.startswith('0::')]
        status = bytes.fromhex(record['status']).decode().splitlines()
        uids = [line.split()[1:] for line in status if line.startswith('Uid:')]
        if (len(unified) != 1 or len(uids) != 1 or len(uids[0]) != 4
                or any(int(v) != os.geteuid() for v in uids[0])):
            raise ValueError('execution cgroup/UID unverified')
        result['cgroup'] = unified[0]
        return result
    parent, worker = parse(raw['parent']), parse(raw['worker'])
    invocation = raw.get('invocation_id')
    if (not isinstance(invocation, str) or not re.fullmatch(r'[0-9a-f]{32}', invocation)
            or parent['argv'] != profile['parent_argv']
            or worker['argv'] != expected_worker
            or worker['parent_pid'] != parent['pid']
            or worker['cgroup'] != parent['cgroup']
            or not parent['cgroup'].endswith('/'+profile['unit'])):
        raise ValueError('execution does not belong to planned unit/command')
    return {'unit': profile['unit'], 'invocation_id': invocation,
            'parent': parent, 'worker': worker, 'raw': raw}


def verify_import_origins(prefix, modules):
    """Không chấp nhận module production lọt vào từ checkout/underlay cũ."""
    origins = {}
    for name, module in modules.items():
        path = Path(module.__file__).resolve(strict=True)
        if not path.is_relative_to(prefix):
            raise ValueError('module outside pinned install: '+name)
        origins[name] = str(path)
    return origins


async def prepare_xauthority(path, display, deadline, total_deadline):
    """Giữ handle spawn; timeout/cancel luôn thu hồi và reap đúng xauth child."""
    record = {'role': 'xauth', 'started_ns': time.monotonic_ns(),
              'parent_pid': os.getpid(), 'uid': os.getuid(),
              'cleanup_errors': [], 'joined': False}
    process = None
    spawn = None
    communication = None
    primary = None

    async def bounded(awaitable, end):
        remaining = end-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('xauth deadline expired')
        return await asyncio.wait_for(asyncio.shield(awaitable), remaining)

    try:
        operation_deadline = min(deadline, time.monotonic()+3)
        if time.monotonic() >= deadline:
            raise TimeoutError('active deadline before xauth spawn')
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            'xauth', '-f', str(path), 'add', display,
            'MIT-MAGIC-COOKIE-1', secrets.token_hex(16), start_new_session=True,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE))
        process = await bounded(spawn, operation_deadline)
        record['pid'] = process.pid
        communication = asyncio.create_task(process.communicate())
        stdout, stderr = await bounded(communication, operation_deadline)
        record.update(exit_status=process.returncode, stdout_sha256=digest(stdout),
                      stderr_sha256=digest(stderr))
        if process.returncode != 0:
            raise RuntimeError('xauth preparation failed')
        path.chmod(0o600)
    except BaseException as error:
        primary = error
        record['primary_error'] = {'type': type(error).__name__, 'reason': str(error)}
        raise
    finally:
        # Ngân sách riêng hữu hạn, không đổi mốc consume hay total deadline.
        end = min(total_deadline, time.monotonic()+3)
        record['cleanup_deadline_ns'] = int(end*1e9)
        try:
            if spawn is not None and process is None:
                process = await bounded(spawn, end)
                record['pid'] = process.pid
            if process is not None:
                if communication is None:
                    communication = asyncio.create_task(process.communicate())
                if process.returncode is None:
                    # PID là direct child chưa reap từ chính handle này; không tra theo tên.
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        record['gone_at_terminate'] = True
                    record['terminated'] = True
                    try:
                        await bounded(communication, min(end, time.monotonic()+.25))
                    except TimeoutError:
                        if process.returncode is None:
                            try:
                                process.kill()
                            except ProcessLookupError:
                                record['gone_at_kill'] = True
                            record['killed'] = True
                await bounded(communication, end)
                await bounded(asyncio.create_task(process.wait()), end)
                record.update(joined=True, exit_status=process.returncode)
        except BaseException as error:
            record['cleanup_errors'].append({'type': type(error).__name__, 'reason': str(error)})
        record['ended_ns'] = time.monotonic_ns()
        try:
            capture.atomic_publish(path.parent/'xauth-record.json', json.dumps(record).encode())
        except BaseException as error:
            record['cleanup_errors'].append({'type': type(error).__name__, 'reason': str(error)})
        if record['cleanup_errors']:
            reason = 'xauth cleanup/evidence incomplete: '+str(record['cleanup_errors'])
            if primary is not None:
                primary.add_note(reason)
            else:
                raise RuntimeError(reason)
    return record


def validate_window_metadata(info, properties, pid):
    """Yêu cầu cửa sổ viewable, geometry/depth thật và đúng PID tại capture."""
    if 'Map State: IsViewable' not in info:
        raise ValueError('capture window is not viewable')
    for field in ('Width', 'Height', 'Depth'):
        match = re.search(r'\b'+field+r':\s*([0-9]+)', info)
        if match is None or int(match[1]) <= 0:
            raise ValueError('invalid window '+field)
    match = re.search(r'_NET_WM_PID\(CARDINAL\)\s*=\s*([0-9]+)', properties)
    if match is None or int(match[1]) != pid:
        raise ValueError('capture window PID changed')


def xcb_environment(environment, display, authority):
    """Ràng buộc cùng display/authority cho GUI, X11 tools và capture."""
    if not display.startswith(':') or not display[1:].isdigit():
        raise ValueError('display must be a local X11 display')
    path = Path(authority).resolve(strict=True)
    if not path.is_file() or path.stat().st_uid != os.getuid():
        raise ValueError('authority must be an owned file')
    return {**environment, 'DISPLAY': display, 'XAUTHORITY': str(path),
            'QT_QPA_PLATFORM': 'xcb'}


def review_result(request, review, png, now_ns, request_bytes):
    """Kiểm review gắn request/ảnh và deadline; không suy human ACK."""
    if now_ns >= request['deadline_ns']:
        raise ValueError('review expired')
    if (capture.strict_json_loads(request_bytes) != request
            or review.get('request_sha256') != digest(request_bytes)):
        raise ValueError('review request SHA-256 mismatch')
    for key in ('run_id', 'session_id', 'nonce', 'screenshot_sha256'):
        if review.get(key) != request[key]:
            raise ValueError('review binding mismatch: ' + key)
    if digest(png) != request['screenshot_sha256']:
        raise ValueError('screenshot changed')
    if review.get('source') != 'codex_image_review':
        raise ValueError('review source must be Codex')
    if review.get('owner_visual_review') != 'NOT_PERFORMED':
        raise ValueError('human ACK cannot be fabricated')
    if review.get('verdict') not in ('PASS', 'FAIL'):
        raise ValueError('invalid review verdict')
    return review['verdict'] == 'PASS'


def load_capture_api():
    """Nạp helper lịch sử dưới tên riêng, giữ bytes và entry point cũ."""
    path = HISTORICAL_TOOLS / 'observation_runner.py'
    spec = importlib.util.spec_from_file_location('b22_capture_api', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def tracked_residue(launcher):
    """Giữ lỗi identity riêng; không để sweep che lỗi controller ban đầu."""
    problems = []
    for record in launcher.records:
        try:
            if record.process.returncode is None or launcher.group_alive(record.process):
                problems.append({'pid':record.pid,'state':'LIVE_OR_UNREAPED'})
        except BaseException as error:
            problems.append({'pid':record.pid,'state':'UNKNOWN','error':str(error)})
    return problems


async def monitor_owned(supervisor, stop, deadline, api, sink):
    """Giám sát các role dài hạn; helper hữu hạn do API riêng join/kiểm exit."""
    critical = {'x11_display', 'robot_state_publisher', 'parameter_bridge', 'server', 'gui'}
    next_resources = 0.0
    while not stop.is_set():
        if getattr(supervisor, '_cleanup_requested', False):
            await stop.wait()
            return
        for record in tuple(supervisor.owned):
            if record.name in critical and record.process.returncode is not None:
                raise RuntimeError(f'owned role exited: {record.name}:{record.process.returncode}')
        child = supervisor._heartbeat_observer_process
        if child is not None and child.returncode is not None:
            raise RuntimeError(f'heartbeat observer exited: {child.returncode}')
        if time.monotonic() >= next_resources:
            memory = [line for line in Path('/proc/meminfo').read_text().splitlines()
                      if line.startswith(('MemAvailable:', 'SwapTotal:', 'SwapFree:'))]
            sink.record('host_resources', {'memory': memory,
                        'owned_pids': [record.pid for record in supervisor.owned]})
            next_resources = time.monotonic()+1
        api._check_output_tasks(supervisor, sink, None)
        if time.monotonic() >= deadline:
            raise TimeoutError('absolute active deadline')
        await asyncio.sleep(.05)


async def await_start(supervisor, evaluator, monitor, deadline, total_deadline):
    """Không hủy startup cleanup vì graph biến mất sau cleanup đã yêu cầu."""
    task = asyncio.create_task(supervisor.start())
    try:
        while not task.done():
            cleaning = getattr(supervisor, '_cleanup_requested', False)
            if not cleaning:
                for health in (evaluator, monitor):
                    if health.done():
                        health.result()
            remaining = (total_deadline if cleaning else deadline)-time.monotonic()
            if remaining <= 0:
                raise TimeoutError('startup absolute deadline')
            await asyncio.wait((task,), timeout=min(.05,remaining))
        return task.result()
    finally:
        if not task.done():
            task.cancel()
            await asyncio.wait((task,),timeout=max(0,min(30,total_deadline-time.monotonic())))
        if task.done() and not task.cancelled():
            task.exception()


def publish_completion(run_root, payload, consumed_ns, *, now_ns=None,
                       publish=None, read_log=None):
    """Marker chỉ là candidate; kiểm hạn sau hash và cả hai lần công bố."""
    clock = now_ns or time.monotonic_ns
    writer = publish or capture.atomic_publish
    reader = read_log or Path.read_bytes
    deadline = consumed_ns+300_000_000_000
    completion = {
        **payload, 'stream_sha256': digest(reader(run_root/'observation.jsonl')),
        'acceptance_state': 'CANDIDATE_REQUIRES_PROCESS_EXIT_VALIDATION',
        'consumed_ns': consumed_ns, 'total_deadline_ns': deadline,
        'prepared_ns': clock(),
    }
    raw = json.dumps(completion, default=str).encode()
    writer(run_root/'completion.json', raw)
    publication_end = clock()
    receipt = {'completion_sha256': digest(raw), 'consumed_ns': consumed_ns,
               'total_deadline_ns': deadline,
               'completion_publication_end_ns': publication_end}
    writer(run_root/'completion-publication.json', json.dumps(receipt).encode())
    finished = clock()
    return 0 if (completion['cleanup_clean'] and not completion['failures']
                 and consumed_ns <= completion['prepared_ns'] < deadline
                 and completion['prepared_ns'] <= publication_end < deadline
                 and publication_end <= finished < deadline) else 3


def completion_timing_errors(consumed, completion_raw, publication,
                             process_exit_status, process_exit_ns):
    """Lớp nghiệm thu phải gọi sau terminal; marker xuất hiện không đủ để đạt."""
    completion = capture.strict_json_loads(completion_raw)
    start = consumed['at_ns']
    deadline = start+300_000_000_000
    errors = []
    if (type(start) is not int or type(process_exit_ns) is not int
            or type(process_exit_status) is not int):
        return ('terminal_process_evidence_missing',)
    if (consumed.get('total_deadline_ns') != deadline
            or any(document.get('consumed_ns') != start
                   or document.get('total_deadline_ns') != deadline
                   for document in (completion, publication))):
        errors.append('consume_deadline_binding_mismatch')
    if completion.get('acceptance_state') != 'CANDIDATE_REQUIRES_PROCESS_EXIT_VALIDATION':
        errors.append('completion_not_terminal_gated')
    if publication.get('completion_sha256') != digest(completion_raw):
        errors.append('completion_hash_mismatch')
    prepared = completion.get('prepared_ns')
    published = publication.get('completion_publication_end_ns')
    if (type(prepared) is not int or type(published) is not int
            or not start <= prepared <= published <= process_exit_ns < deadline):
        errors.append('completion_or_process_after_total_deadline')
    if process_exit_status != 0:
        errors.append('process_exit_nonzero')
    if completion.get('cleanup_clean') is not True or completion.get('failures') != []:
        errors.append('completion_reports_failure')
    return tuple(errors)


def validate_terminal(run_root, evidence_path, packet_path, packet_sha256):
    """Chốt thời hạn từ terminal systemd của đúng invocation, không từ marker."""
    raw = evidence_path.read_bytes()
    evidence = capture.strict_json_loads(raw)
    packet_raw = packet_path.read_bytes()
    if digest(packet_raw) != packet_sha256:
        raise ValueError('approved packet SHA-256 mismatch')
    packet = capture.strict_json_loads(packet_raw)
    def properties(text):
        pairs = [line.split('=', 1) for line in text.splitlines() if '=' in line]
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError('duplicate systemd property')
        return result
    initial = properties(evidence['initial_unit'])
    terminal = properties(evidence['terminal_unit'])
    consumed = capture.strict_json_loads((run_root/'consumed.json').read_bytes(), max_bytes=64*1024)
    errors = []
    profile_raw = Path(packet['profile']).read_bytes()
    if digest(profile_raw) != packet['profile_sha256']:
        raise ValueError('packet profile SHA-256 mismatch')
    profile = capture.strict_json_loads(profile_raw, max_bytes=4*1024*1024)
    expected_args = argparse.Namespace(**{
        key: profile[key] for key in ('evidence', 'run_id', 'install', 'source_commit', 'authority')
    }, profile=packet['profile'], profile_sha256=packet['profile_sha256'])
    if (packet['run_id'] != run_root.name or consumed['run_id'] != packet['run_id']
            or profile['run_id'] != packet['run_id']
            or str(run_root.parent) != profile['evidence']
            or consumed['source_commit'] != packet['source_commit']
            or profile['source_commit'] != packet['source_commit']
            or consumed['profile_sha256'] != packet['profile_sha256']
            or digest(Path(__file__).read_bytes()) != packet['source_runner_sha256']
            or profile['unit'] != packet['unit']
            or profile['parent_argv'] != packet['parent_argv']
            or digest(Path(packet['parent_argv'][1]).read_bytes()) != packet['wrapper_sha256']
            or packet['worker_argv'] != worker_command(expected_args)
            or packet['launch_command'][-2:] != packet['parent_argv']
            or packet['launch_command'].count('--unit='+packet['unit']) != 1):
        errors.append('packet_run_source_or_command_binding_mismatch')
    execution = normalize_execution(profile, worker_command(expected_args), consumed['execution']['raw'])
    if execution != consumed['execution']:
        errors.append('consume_execution_record_inconsistent')
    if (type(execution['raw']['collected_ns']) is not int
            or not 0 < execution['raw']['collected_ns'] <= consumed['at_ns']):
        errors.append('execution_observation_time_unverified')
    if (initial.get('Id') != packet['unit']
            or initial.get('InvocationID') != execution['invocation_id']
            or int(initial['MainPID']) != execution['parent']['pid']
            or initial.get('ControlGroup') != execution['parent']['cgroup']):
        errors.append('terminal_not_bound_to_consumed_execution')
    for record in (initial, terminal):
        # Lệnh hiện hành chỉ gồm các path ASCII không whitespace; mơ hồ thì reject.
        start_text = record.get('ExecStart', '')
        starts = re.findall(r'argv\[\]=(.*?) ;', start_text)
        if (not start_text.startswith('{ path='+packet['parent_argv'][0]+' ; ')
                or len(starts) != 1 or shlex.split(starts[0]) != packet['parent_argv']):
            errors.append('systemd_exec_start_command_mismatch')
    if (not initial.get('InvocationID') or not initial.get('ControlGroup')
            or int(initial['MainPID']) <= 0
            or terminal.get('InvocationID') != initial['InvocationID']
            or terminal.get('Id') != initial.get('Id')
            or terminal.get('ControlGroup') not in ('', initial['ControlGroup'])
            or terminal.get('LoadState') != 'loaded'
            or terminal.get('ActiveState') != 'active'
            or terminal.get('SubState') != 'exited'
            or int(terminal['MainPID']) != 0
            or int(terminal['ExecMainPID']) != int(initial['MainPID'])
            or int(terminal['ExecMainCode']) != os.CLD_EXITED
            or terminal.get('Result') != 'success'):
        errors.append('terminal_unit_identity_or_state_unverified')
    # systemd xuất microseconds: dùng biên trên để không nhận nhầm sát deadline.
    exit_ns = int(terminal['ExecMainExitTimestampMonotonic'])*1000+1000
    if not consumed['at_ns'] <= exit_ns <= evidence['collected_end_ns']:
        errors.append('terminal_timestamp_unverified')
    errors.extend(completion_timing_errors(
        consumed, (run_root/'completion.json').read_bytes(),
        capture.strict_json_loads((run_root/'completion-publication.json').read_bytes()),
        int(terminal['ExecMainStatus']), exit_ns))
    result = {'timing_verdict': 'FAIL' if errors else 'PASS', 'errors': errors,
              'scope': 'completion publication and exact unit process exit deadline',
              'unit': initial['Id'], 'invocation_id': initial['InvocationID'],
              'process_exit_ns_upper_bound': exit_ns,
              'evidence_sha256': digest(raw), 'source_commit': consumed['source_commit']}
    result.update(run_id=consumed['run_id'], packet_sha256=packet_sha256,
                  profile_sha256=packet['profile_sha256'],
                  worker_pid=execution['worker']['pid'])
    capture.atomic_publish(run_root/'completion-acceptance.json', json.dumps(result).encode())
    print(json.dumps(result))
    return 3 if errors else 0


async def run(args):
    profile = verify_profile(args)
    execution = normalize_execution(profile, worker_command(args), execution_observations())
    root = Path(args.evidence).resolve(strict=True)
    run_root = root / args.run_id
    run_root.mkdir(mode=0o700)
    # Một mốc consume duy nhất, bao gồm setup/xauth/startup/review/observation.
    consumed_ns = time.monotonic_ns()
    capture.atomic_publish(run_root / 'consumed.json', json.dumps({
        'run_id': args.run_id, 'authority': args.authority,
        'source_commit': args.source_commit, 'at_ns': consumed_ns,
        'active_deadline_ns': consumed_ns+240_000_000_000,
        'total_deadline_ns': consumed_ns+300_000_000_000,
        'profile_sha256': args.profile_sha256,
        'execution': execution,
    }).encode())
    try:
        entry = run_contact if profile.get('mode') == 'contact_probe_only' else run_consumed
        return await entry(args, run_root, consumed_ns, profile)
    except BaseException as error:
        capture.atomic_publish(run_root/'invocation-failure.json', json.dumps({
            'type': type(error).__name__, 'reason': str(error),
            'notes': getattr(error, '__notes__', []), 'at_ns': time.monotonic_ns(),
        }).encode())
        raise


def contact_proof_errors(proof, expected):
    """Chỉ chấp nhận proof backend thật của chính phiên infrastructure."""
    errors = []
    for key, value in expected.items():
        if proof.get(key) != value:
            errors.append('proof_identity:'+key)
    if proof.get('result') != 3 or proof.get('reason_code') != 0 or proof.get('contact_capability_state') != 2:
        errors.append('backend_not_verified')
    world = expected['proof_world_name']
    for key, value in {'probe_model_scoped_name':world+'::b2_capability_probe',
        'probe_collision_scoped_name':world+'::b2_capability_probe::link::collision',
        'floor_collision_scoped_name':world+'::ground_plane::link::collision'}.items():
        if proof.get(key) != value:
            errors.append('fixture_identity:'+key)
    ids = [proof.get(k) for k in ('probe_model_entity_id','probe_collision_entity_id','floor_collision_entity_id')]
    if any(type(v) is not int or v <= 0 for v in ids) or len(set(ids)) != 3:
        errors.append('fixture_entity_ids')
    for count, prefix in [('contact_sample_count','contact'),('covered_empty_sample_count','empty')]:
        n = proof.get(count, 0)
        first, last = proof[prefix+'_first_iteration'], proof[prefix+'_last_iteration']
        stamps = [proof[prefix+'_'+edge+'_stamp'] for edge in ('first','last')]
        ns = [s['sec']*1_000_000_000+s['nanosec'] for s in stamps]
        if n < 3 or first <= 0 or last-first+1 != n or ns[1]-ns[0] < 20_000_000:
            errors.append('sample_coverage:'+prefix)
    if proof['empty_first_iteration'] <= proof['contact_last_iteration']:
        errors.append('separation_order')
    if not proof.get('proof_gz_sim_version','').startswith('8.') or len(proof.get('proof_collision_registry_sha256','')) != 64:
        errors.append('engine_registry_provenance')
    return errors


async def run_contact(args, run_root, start_ns, profile):
    """Route contact-only: không dựng lifecycle, publisher hay actuator gate."""
    import rclpy
    from rclpy.context import Context
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rosidl_runtime_py.convert import message_to_ordereddict as message_dict
    from ros_gz_interfaces.srv import ControlWorld
    from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
    from mecanum_nav_rl_interfaces.msg import SimulationContactState
    from mecanum_nav_bringup.local_training_launch_contract import build_launch_plan, write_bound_world
    from mecanum_nav_bringup import local_training_process_supervisor as sp
    from observation_sink import ObservationEvidenceSink
    prefix = Path(args.install).resolve(strict=True)
    verify_import_origins(prefix, {'supervisor':sp})
    desc = prefix/'share/ROBOT_URDF_final_description'; rl = prefix/'share/mecanum_nav_rl'; bringup = prefix/'share/mecanum_nav_bringup'
    sid = str(uuid.uuid4()); deadline = (start_ns+240_000_000_000)/1e9; total = (start_ns+300_000_000_000)/1e9
    sink = ObservationEvidenceSink(run_root,args.run_id,sid)
    plan = build_launch_plan(gui='false',resolved_config=rl/'config/v3/resolved/sim_train_local_training_soak.resolved.json',
        world_file=desc/'worlds/b2_training_arena.sdf',gui_config=bringup/'config/gui/local_training.config',
        session_id=sid,partition='mecanum_b2_'+sid.replace('-',''),bridge_config=bringup/'config/bridge/local_training.runtime.yaml',
        resource_paths=(desc.parent,desc/'models'),plugin_path=prefix/'lib',physics_engine_plugin_path=sp._physics_engine_plugin_path(),
        asset_manifest_file=desc/'manifests/b2/asset_manifest.json',scenario_directory=rl/'scenarios/local_training',
        runtime_world_directory=run_root,coordinator_ingress_instance_id=secrets.randbits(64) or 1)
    plan = replace(plan,environment={**plan.environment,'ROS_DOMAIN_ID':'83'})
    write_bound_world(plan,desc/'worlds/b2_training_arena.sdf',desc/'models/mecanum_b2/model.sdf')
    tree = ET.parse(plan.world_file);plugin = tree.find(".//plugin[@name='mecanum_sim_backend::BackendSystem']")
    if plugin is None: raise ValueError('bound backend plugin missing')
    ET.SubElement(plugin,'contact_probe_only').text = 'true'
    plugin.find('first_safe_stop_sequence').text = '0'
    tree.write(plan.world_file,encoding='utf-8',xml_declaration=True)
    capture.atomic_publish(run_root/'bindings.json',json.dumps({'source_commit':args.source_commit,
        'profile_sha256':args.profile_sha256,'world_sha256':digest(plan.world_file.read_bytes()),
        'mode':'contact_probe_only','session_id':sid,'coordinator_ingress_instance_id':plan.coordinator_ingress_instance_id,
        'config_hash':plan.config_hash,'asset_manifest_sha256':plan.asset_manifest_sha256,
        'commands':plan.commands,'environment':dict(plan.environment),'verified_profile':profile},default=str).encode())
    async def publisher(batch, end):
        await asyncio.to_thread(capture.atomic_publish,run_root/'cleanup-batch.json',
            json.dumps({'batch_id':batch.batch_id,'events':batch.events},default=str).encode())
        return sp.CleanupEvidenceAck(batch.batch_id,True)
    sup = sp.LocalTrainingProcessSupervisor(plan=plan,launcher=sp.SubprocessProcessLauncher(),
        readiness=sp.RclpyReadiness(),evidence_sink=sink,heartbeat_diagnostics_enabled=True,
        heartbeat_trace_directory=run_root/'trace',cleanup_evidence_publisher=publisher)
    (run_root/'trace').mkdir(mode=0o700)
    context = Context(); node = executor = None; failures = []; outcomes = {}; statuses = []
    probe_end = None; sequence = 0
    try:
        await asyncio.wait_for(sup.start(),max(.001,deadline-time.monotonic()))
        rclpy.init(context=context,domain_id=83)
        node = Node('b22_contact_probe_client',context=context)
        executor = SingleThreadedExecutor(context=context);executor.add_node(node)
        node.create_subscription(SimulationContactState,'/mecanum/local_training/backend_state',
            lambda message:statuses.append((time.monotonic_ns(),message)),50)
        client = node.create_client(Control,'/mecanum/local_training/backend_control')
        world_client = node.create_client(ControlWorld,'/world/b2_training_arena/control')
        def health():
            if statuses:
                now, status = statuses[-1]
                if (status.session_id != sid or status.config_hash != plan.config_hash or
                    not status.actuator_inhibited or status.applied_receipt_valid or status.fault_flags):
                    raise RuntimeError('contact session/health/inhibit violation')
                if time.monotonic_ns()-now > 1_000_000_000:raise RuntimeError('contact heartbeat expired')
            for owned in sup.owned:
                if owned.process.returncode is not None:raise RuntimeError('owned process exited: '+owned.name)
        async def spin():
            executor.spin_once(timeout_sec=.005);health();await asyncio.sleep(.001)
        async def call(client, request, end, kind):
            if end<=time.monotonic():raise TimeoutError(kind+' before submission')
            sink.record('contact_request',{'kind':kind,'request':message_dict(request)})
            future = client.call_async(request)
            while not future.done():
                if time.monotonic()>=end:raise TimeoutError(kind+' response deadline')
                await spin()
            response=future.result();sink.record('contact_response',{'kind':kind,'response':message_dict(response)})
            return response
        ready_end=min(deadline,time.monotonic()+5)
        while not statuses or not client.service_is_ready() or not world_client.service_is_ready():
            if time.monotonic()>=ready_end:raise TimeoutError('contact clients/status not ready')
            await spin()
        backend = statuses[-1][1].backend_instance_id
        graph = node.get_node_names_and_namespaces()
        writers = {topic:node.count_publishers(topic) for topic in ('/cmd_vel','/mecanum/final_issued_command')}
        sink.record('contact_graph',{'participants':graph,'actuator_publishers':writers})
        if any(writers.values()):raise RuntimeError('foreign actuator publisher in contact domain')
        control=ControlWorld.Request();control.world_control.pause=False
        control_end=min(deadline,time.monotonic()+1)
        response=await call(world_client,control,control_end,'resume_inhibited')
        if not response.success:raise RuntimeError('resume rejected')
        while statuses[-1][1].paused:
            if time.monotonic()>=control_end:raise TimeoutError('resume not measured')
            await spin()
        sequence=0
        def request(action):
            nonlocal sequence
            sequence+=1;req=Control.Request();req.schema_version=1;req.operation=5;req.probe_action=action
            req.coordinator_ingress_instance_id=plan.coordinator_ingress_instance_id;req.request_sequence=sequence
            req.expected_backend_instance_id=backend;req.session_id=sid;req.config_hash=plan.config_hash
            req.asset_manifest_sha256=plan.asset_manifest_sha256
            if action!=1:req.probe_start_request_sequence=1
            return req
        probe_end=min(deadline,time.monotonic()+5)
        req=request(1)
        while True:
            response=await call(client,req,min(probe_end-1,time.monotonic()+1),'START' if req.request_sequence==1 else 'QUERY')
            if response.result==2:
                await spin();continue  # exact cached request, never a second START
            if response.result!=3:raise RuntimeError('backend rejected contact request: '+str(message_dict(response)))
            if response.contact_capability_state==2:break
            if time.monotonic()>=probe_end-1:raise TimeoutError('contact proof cleanup reserve reached')
            req=request(2);await spin()
        proof=message_dict(response)
        expected={'proof_session_id':sid,'proof_backend_instance_id':backend,'proof_config_hash':plan.config_hash,
            'proof_asset_manifest_sha256':plan.asset_manifest_sha256,'proof_world_name':'b2_training_arena',
            'proof_physics_engine_fingerprint_sha256':profile['physics_engine_sha256']}
        errors=contact_proof_errors(proof,expected)
        if errors:raise RuntimeError('contact proof invalid: '+str(errors))
        control.world_control.pause=True
        control_end=min(deadline,time.monotonic()+1)
        response=await call(world_client,control,control_end,'pause_after_verified')
        if not response.success:raise RuntimeError('pause rejected')
        while not statuses[-1][1].paused:
            if time.monotonic()>=control_end:raise TimeoutError('pause not measured')
            await spin()
        capture.atomic_publish(run_root/'contact-proof.json',json.dumps(proof).encode())
        outcomes={'contact_verdict':'CAPABILITY_VERIFIED','session_id':sid,'backend_instance_id':backend}
    except BaseException as error:
        failures.append({'type':type(error).__name__,'reason':str(error)})
        if probe_end is not None and sequence and time.monotonic() < probe_end:
            try:
                abort = request(3)
                sink.record('contact_abort_request',{'request':message_dict(abort)})
                future = client.call_async(abort)
                while not future.done() and time.monotonic() < probe_end:
                    executor.spin_once(timeout_sec=min(.005,max(0,probe_end-time.monotonic())))
                    await asyncio.sleep(.001)
                sink.record('contact_abort_result',{'complete':future.done(),
                    'response':message_dict(future.result()) if future.done() else None})
            except BaseException as abort_error:
                failures.append({'type':'AbortCleanup','reason':str(abort_error)})
        raise
    finally:
        for close in (
            lambda: executor.shutdown(timeout_sec=max(0,min(1,total-time.monotonic()))) if executor is not None else None,
            lambda: node.destroy_node() if node is not None else None,
            lambda: context.shutdown() if context.ok() else None,
        ):
            try:close()
            except BaseException as close_error:failures.append({'type':'ClientCleanup','reason':str(close_error)})
        clean=await sup.cleanup(deadline=min(total,time.monotonic()+30))
        capture.atomic_publish(run_root/'cleanup.json',json.dumps(sup.cleanup_snapshot(),default=str).encode())
        sink.record('contact_final',{'outcomes':outcomes,'failures':failures,'cleanup_clean':clean,
            'statuses':[{'at_ns':t,'sequence':s.status_sequence,'paused':s.paused,'inhibited':s.actuator_inhibited,
                         'fault_flags':s.fault_flags} for t,s in statuses]})
        sink.close()
        final_exit=publish_completion(run_root,{'outcomes':outcomes,'failures':failures,'cleanup_clean':clean,
            'owner_visual_review':'NOT_PERFORMED','trace_audit':'PENDING'},start_ns)
    return final_exit


async def run_consumed(args, run_root, start_ns, profile):
    from mecanum_nav_bringup.local_training_launch_contract import build_launch_plan, write_bound_world
    from mecanum_nav_bringup import local_training_process_supervisor as sp
    from mecanum_nav_bringup import local_training_heartbeat_trace_observer as trace_api
    from observation_sink import ObservationEvidenceSink
    api = load_capture_api()
    deadline = (start_ns+240_000_000_000)/1e9
    total_deadline = (start_ns+300_000_000_000)/1e9
    prefix = Path(args.install).resolve(strict=True)
    from mecanum_nav_rl.config import v3_models
    from mecanum_nav_rl_interfaces import msg as interfaces
    origins = verify_import_origins(prefix, {
        'supervisor': sp, 'trace_observer': trace_api,
        'v3_models': v3_models, 'interfaces': interfaces,
    })
    desc = prefix / 'share/ROBOT_URDF_final_description'
    bringup = prefix / 'share/mecanum_nav_bringup'
    rl = prefix / 'share/mecanum_nav_rl'
    sid = str(uuid.uuid4())
    sink = ObservationEvidenceSink(run_root, args.run_id, sid)
    trace_dir = run_root / 'trace'
    trace_dir.mkdir(mode=0o700)
    plan = build_launch_plan(
        gui='true', resolved_config=rl/'config/v3/resolved/sim_train_local_training_soak.resolved.json',
        world_file=desc/'worlds/b2_training_arena.sdf', gui_config=bringup/'config/gui/local_training.config',
        session_id=sid, partition='mecanum_b2_'+sid.replace('-', ''),
        bridge_config=bringup/'config/bridge/local_training.runtime.yaml',
        resource_paths=(desc.parent, desc/'models'), plugin_path=prefix/'lib',
        physics_engine_plugin_path=sp._physics_engine_plugin_path(),
        asset_manifest_file=desc/'manifests/b2/asset_manifest.json',
        scenario_directory=rl/'scenarios/local_training', runtime_world_directory=run_root,
        coordinator_ingress_instance_id=secrets.randbits(64) or 1,
    )
    display_number = next(n for n in range(105,200)
                          if not Path(f'/tmp/.X11-unix/X{n}').exists()
                          and not Path(f'/tmp/.X{n}-lock').exists())
    authority = run_root/'display.Xauthority'
    await prepare_xauthority(authority, f':{display_number}', deadline, total_deadline)
    parent_environment = dict(os.environ)
    environment = xcb_environment({**plan.environment,'ROS_DOMAIN_ID':str(args.domain)},
                                  f':{display_number}',authority)
    plan = replace(plan,environment=environment)
    write_bound_world(plan,desc/'worlds/b2_training_arena.sdf',desc/'models/mecanum_b2/model.sdf')
    bindings = {}
    for package in ('mecanum_nav_bringup','mecanum_nav_rl'):
        module = __import__(package)
        bindings[package] = str(Path(module.__file__).resolve())
    files = [Path(__file__),Path(sp.__file__),Path(trace_api.__file__),plan.world_file,
             plan.resolved_config,desc/'manifests/b2/asset_manifest.json',
             rl/'scenarios/local_training/B2_SOAK_V1.json']
    files += list((prefix/'lib').glob('libmecanum*.so'))
    pins = {str(p):digest(p.read_bytes()) for p in files}
    (run_root/'bindings.json').write_text(json.dumps({'pins':pins,'origins':{**bindings, **origins},
        'environment':environment,'commands':plan.commands,'clock':trace_api.clock_context(),
        'source_commit':args.source_commit,'authority':args.authority,
        'profile_sha256':args.profile_sha256, 'verified_profile':profile,
        'consumed_ns':start_ns, 'active_deadline_ns':int(deadline*1e9),
        'total_deadline_ns':int(total_deadline*1e9)},indent=2))
    ack = asyncio.Event()
    ready = asyncio.Event()
    outcomes = {'owner_visual_review':'NOT_PERFORMED','heartbeat_historical_RUN008':'UNKNOWN'}
    failures = []

    class Launcher(api.TrackedProcessLauncher):
        async def start_controlled(self, command, environment):
            process = await self.delegate.start_controlled(command,environment)
            record = self._retain_process_handle(process,command)
            self._verify_record_identity(record)
            return process

    launcher = Launcher(sp.SubprocessProcessLauncher(), on_start=lambda record, identity:
        sink.record('owned_process_identity',{'pid':record.pid,'role':record.name,
                    'identity':identity,'command':record.command}))

    class Readiness(sp.RclpyReadiness):
        gui_confirmation_source = 'codex_image_review'
        async def server_scene(self, *values):
            await super().server_scene(*values)
            ready.set()
        async def owner_ack(self, timeout_s):
            if deadline-time.monotonic() < 121:
                raise RuntimeError('insufficient active budget for review and observation')
            review_deadline = min(deadline,time.monotonic()+timeout_s)
            # Cho render thread hoàn tất frame đầu; không gia hạn checkpoint.
            settle_until = min(review_deadline,time.monotonic()+5)
            while time.monotonic() < settle_until:
                if evaluator.done(): await evaluator
                if monitor.done(): await monitor
                await asyncio.sleep(.05)
            window = await api.bind_gui_window(launcher=launcher,environment=environment,
                partition=plan.environment['GZ_PARTITION'],deadline=review_deadline,sink=sink)
            window = await api.bind_gui_window(launcher=launcher,environment=environment,
                partition=plan.environment['GZ_PARTITION'],deadline=review_deadline,sink=sink,
                discovery_phase='capture_revalidation',expected_window=window)
            gui_env = dict(part.split(b'=',1) for part in Path(f'/proc/{window["pid"]}/environ').read_bytes().split(b'\0') if b'=' in part)
            if gui_env.get(b'DISPLAY') != environment['DISPLAY'].encode():
                raise RuntimeError('GUI and capture displays differ')
            sink.record('gui_display_binding', {'pid':window['pid'], 'window_id':window['window_id'],
                        'DISPLAY':environment['DISPLAY'], 'QT_QPA_PLATFORM':gui_env.get(b'QT_QPA_PLATFORM',b'').decode()})
            shot = await api.capture_x11_window_bounded(window['window_id'],launcher=launcher,
                environment={**environment, 'B22_CAPTURE_PLATFORM_RECORD':str(run_root/'capture-platform.json'),
                    'B22_CAPTURE_WINDOW_IDENTITY':json.dumps(capture.process_start_identity(window['pid']))},
                deadline=review_deadline,sink=sink,run_id=args.run_id,session_id=sid,
                helper_command_factory=lambda role, command: (
                    (sys.executable,str(Path(__file__).resolve()),'--capture-worker',command[-1])
                    if role == 'capture_helper' else command))
            image = run_root/'gui.png'
            capture.atomic_publish(image,shot.pop('png_bytes'))
            request = {'run_id':args.run_id,'session_id':sid,'nonce':secrets.token_hex(16),
                       'screenshot_path':str(image),'screenshot_sha256':shot['sha256'],
                       'deadline_ns':int(review_deadline*1e9),'window':window,'capture':shot,
                       'result_path':str(run_root/'codex-review.json')}
            request_bytes = json.dumps(request,sort_keys=True).encode()
            capture.atomic_publish(run_root/'review-request.json',request_bytes)
            while time.monotonic()<review_deadline:
                if evaluator.done(): await evaluator
                if monitor.done(): await monitor
                if (run_root/'review-request.json').read_bytes()!=request_bytes:
                    raise RuntimeError('review request changed')
                result = Path(request['result_path'])
                if result.exists():
                    data = capture.read_published(result)
                    accepted = review_result(request,capture.strict_json_loads(data),
                        image.read_bytes(),time.monotonic_ns(),request_bytes)
                    sink.record('codex_review_validated',{'request_sha256':digest(request_bytes),
                        'result_sha256':digest(data),'accepted':accepted,'owner_visual_review':'NOT_PERFORMED'})
                    if accepted: ack.set()
                    return accepted,str(result)
                await asyncio.sleep(.05)
            return False,'codex_review_timeout'

    async def publisher(batch, cleanup_deadline):
        def write():
            capture.atomic_publish(run_root/'cleanup-batch.json',json.dumps(
                {'batch_id':batch.batch_id,'events':batch.events},default=str).encode())
        await asyncio.to_thread(write)
        return sp.CleanupEvidenceAck(batch.batch_id,True)

    supervisor = sp.LocalTrainingProcessSupervisor(plan=plan,launcher=launcher,
        readiness=Readiness(),evidence_sink=sink,heartbeat_diagnostics_enabled=True,
        heartbeat_trace_directory=trace_dir,cleanup_evidence_publisher=publisher)
    passive = api.PassiveBackendObserver()
    # API observer lịch sử pin domain 83; chỉ chấp nhận đúng domain đó ở runner này.
    evaluator = monitor = None
    stop = asyncio.Event()
    clean = False
    try:
        if time.monotonic() >= deadline:
            raise TimeoutError('active deadline before ROS startup')
        passive.start()
        evaluator = asyncio.create_task(api.evaluate_observation(plan=plan,observer=passive,
            duration_s=60,ack_event=ack,deadline=deadline,sink=sink,
            expected_nodes=api.EXPECTED_ROS_NODES|{('b2_heartbeat_trace_observer','/')},
            readiness_complete_event=ready))
        monitor = asyncio.create_task(monitor_owned(supervisor,stop,deadline,api,sink))
        await supervisor._launch_owned_process('x11_display',
            ('Xephyr',f':{display_number}','-screen','1280x800','-nolisten','tcp','-noreset',
             '-auth',str(authority)),parent_environment)
        # Truy vấn cùng display qua process có ownership và file output riêng.
        ready_script = run_root/'display_ready.py'
        ready_script.write_text("import subprocess,sys,time\nfor _ in range(40):\n p=subprocess.run(['xdpyinfo'],capture_output=True,timeout=1)\n if p.returncode==0:sys.exit(0)\n time.sleep(.1)\nsys.exit(1)\n")
        await api._owned_helper(launcher,(sys.executable,'-B',str(ready_script)),
            environment,deadline=min(deadline,time.monotonic()+6),sink=sink)
        params = run_root/'rsp-params.json'
        params.write_text(json.dumps({'robot_state_publisher':{'ros__parameters':{
            'robot_description':(desc/'urdf/mecanum_b2_static.urdf').read_text(),'use_sim_time':True}}}))
        await supervisor._launch_owned_process('robot_state_publisher',
            ('/opt/ros/jazzy/lib/robot_state_publisher/robot_state_publisher','--ros-args',
             '--params-file',str(params)),environment)
        await await_start(supervisor,evaluator,monitor,deadline,total_deadline)
        observation = await api._wait_competing(asyncio.shield(evaluator),monitor,
                                               deadline,time.monotonic)
        outcomes['observation'] = observation
        outcomes['gui_review'] = 'PASS'
    except BaseException as error:
        failures.append({'type':type(error).__name__,'reason':str(error),
                         'at_ns':time.monotonic_ns()})
        raise
    finally:
        stop.set()
        tasks = [task for task in (evaluator,monitor) if task is not None]
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        try:
            passive.close(deadline=min(total_deadline,time.monotonic()+3))
        except BaseException as error:
            failures.append({'type':'ObserverClose','reason':str(error)})
        clean = await supervisor.cleanup(deadline=min(total_deadline,time.monotonic()+30))
        tracked_pending = tracked_residue(launcher)
        if tracked_pending or launcher.pending_spawn_tasks or launcher.late_spawn_cleanup_tasks:
            clean = False
            failures.append({'type':'TrackedResidue','pids':tracked_pending})
        snapshot = supervisor.cleanup_snapshot()
        (run_root/'cleanup.json').write_text(json.dumps(snapshot,indent=2,default=str))
        sink.record('final_observation',{'outcomes':outcomes,'failures':failures,
                    'cleanup_clean':clean,'elapsed_ns':time.monotonic_ns()-start_ns})
        sink.close()
        # Marker không phải verdict: receipt và terminal process được kiểm riêng.
        final_exit = publish_completion(run_root, {
            'outcomes':outcomes,'failures':failures,'cleanup_clean':clean,
            'trace_audit':'PENDING','owner_visual_review':'NOT_PERFORMED'}, start_ns)
    return final_exit


def capture_worker(window_id):
    """Đo platform/window ngay trước API capture đã khóa."""
    from PyQt5 import QtCore, QtGui
    app = QtGui.QGuiApplication([])
    record = {'platform':app.platformName(), 'DISPLAY':os.environ.get('DISPLAY'),
              'qt':QtCore.qVersion(), 'PyQt':QtCore.PYQT_VERSION_STR,
              'executable':sys.executable, 'identity':capture.process_start_identity(os.getpid()),
              'QtCore':QtCore.__file__, 'QtGui':QtGui.__file__,
              'at_ns':time.monotonic_ns()}
    record['libraries'] = sorted(set(line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
        if '/libqxcb' in line or '/libQt5Gui' in line))
    proc = subprocess.run(['xwininfo','-id',window_id],capture_output=True,timeout=2)
    record['xwininfo'] = {'exit':proc.returncode,'stdout':proc.stdout.decode(),'stderr':proc.stderr.decode()}
    props = subprocess.run(['xprop','-id',window_id,'_NET_WM_PID'],capture_output=True,timeout=2)
    record['xprop'] = {'exit':props.returncode,'stdout':props.stdout.decode(),'stderr':props.stderr.decode()}
    expected = json.loads(os.environ['B22_CAPTURE_WINDOW_IDENTITY'])
    record['window_identity'] = capture.process_start_identity(expected['pid'])
    if record['window_identity'] != expected:
        raise RuntimeError('capture window process identity changed')
    validate_window_metadata(proc.stdout.decode(), props.stdout.decode(),expected['pid'])
    capture.atomic_publish(Path(os.environ['B22_CAPTURE_PLATFORM_RECORD']),json.dumps(record).encode())
    if app.platformName() != 'xcb' or proc.returncode or props.returncode:
        raise RuntimeError('capture platform/window metadata invalid')
    return capture._capture_worker_mode(window_id)


def publish_review(request_path, verdict, notes):
    """Publisher review Codex độc lập với cleanup-evidence publisher."""
    request_path = Path(request_path).resolve(strict=True)
    request_bytes = capture.read_published(request_path)
    request = json.loads(request_bytes)
    image = Path(request['screenshot_path'])
    png = capture.read_published(image,max_bytes=32*1024*1024)
    result = {key:request[key] for key in ('run_id','session_id','nonce','screenshot_sha256')}
    result.update({'source':'codex_image_review','owner_visual_review':'NOT_PERFORMED',
                   'verdict':verdict,'notes':notes,'request_sha256':digest(request_bytes),
                   'publisher_identity':capture.process_start_identity(os.getpid()),
                   'at_ns':time.monotonic_ns()})
    review_result(request,result,png,time.monotonic_ns(),request_bytes)
    target = Path(request['result_path'])
    if target.parent != request_path.parent or image.parent != request_path.parent:
        raise ValueError('review paths must belong to this run')
    capture.atomic_publish(target,json.dumps(result,sort_keys=True).encode())
    print(json.dumps({'published':str(target),'sha256':digest(target.read_bytes())}))
    return 0


def main():
    if len(sys.argv) == 6 and sys.argv[1] == '--validate-terminal':
        return validate_terminal(Path(sys.argv[2]), Path(sys.argv[3]),
                                 Path(sys.argv[4]), sys.argv[5])
    if len(sys.argv) == 3 and sys.argv[1] == '--capture-worker':
        return capture_worker(sys.argv[2])
    if len(sys.argv) == 5 and sys.argv[1] == '--publish-review':
        return publish_review(sys.argv[2],sys.argv[3],sys.argv[4])
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--install',required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--authority',required=True)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--profile-sha256',required=True)
    parser.add_argument('--domain',type=int,choices=(83,),default=83)
    return asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
