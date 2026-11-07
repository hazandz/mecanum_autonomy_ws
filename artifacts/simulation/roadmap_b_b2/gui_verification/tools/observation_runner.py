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
import subprocess
import sys
import time
import uuid

REPOSITORY = Path(__file__).resolve().parents[5]
HISTORICAL_TOOLS = REPOSITORY / 'artifacts/simulation/roadmap_b_b2/gui_observation_run008/tools'
sys.path.insert(0, str(HISTORICAL_TOOLS))
# Chỉ dùng API capture/binding; không gọi entry point hay capacity RUN008.
import observation_runner as capture
# Module hiện tại cần tên riêng khi import bằng importlib (CLI không tên observation_runner).


def digest(data):
    return hashlib.sha256(data).hexdigest()


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


def review_result(request, review, png, now_ns):
    """Kiểm review gắn request/ảnh và deadline; không suy human ACK."""
    if now_ns >= request['deadline_ns']:
        raise ValueError('review expired')
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


async def run(args):
    from mecanum_nav_bringup.local_training_launch_contract import build_launch_plan, write_bound_world
    from mecanum_nav_bringup import local_training_process_supervisor as sp
    from mecanum_nav_bringup import local_training_heartbeat_trace_observer as trace_api
    from observation_sink import ObservationEvidenceSink
    api = load_capture_api()
    root = Path(args.evidence).resolve(strict=True)
    if not re.fullmatch(r'[A-Za-z0-9_]+', args.run_id):
        raise ValueError('invalid run ID')
    # mkdir độc quyền là chốt; mỗi lượt dùng ID/path mới.
    run_root = root / args.run_id
    run_root.mkdir(mode=0o700)
    capture.atomic_publish(run_root / 'consumed.json', json.dumps({
        'run_id': args.run_id, 'authority': args.authority,
        'source_commit': args.source_commit, 'at_ns': time.monotonic_ns(),
    }).encode())
    prefix = Path(args.install).resolve(strict=True)
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
    cookie = secrets.token_hex(16)
    proc = await asyncio.create_subprocess_exec('xauth','-f',str(authority),'add',
        f':{display_number}','MIT-MAGIC-COOKIE-1',cookie,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    _, err = await asyncio.wait_for(proc.communicate(),3)
    if proc.returncode:
        raise RuntimeError('xauth preparation failed: '+err.decode()[:160])
    authority.chmod(0o600)
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
    (run_root/'bindings.json').write_text(json.dumps({'pins':pins,'origins':bindings,
        'environment':environment,'commands':plan.commands,'clock':trace_api.clock_context(),
        'source_commit':args.source_commit,'authority':args.authority},indent=2))
    ack = asyncio.Event()
    ready = asyncio.Event()
    start_ns = time.monotonic_ns()
    deadline = time.monotonic()+240
    total_deadline = deadline+60
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
                    accepted = review_result(request,json.loads(data),image.read_bytes(),time.monotonic_ns())
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
    passive.start()
    evaluator = asyncio.create_task(api.evaluate_observation(plan=plan,observer=passive,
        duration_s=60,ack_event=ack,deadline=deadline,sink=sink,
        expected_nodes=api.EXPECTED_ROS_NODES|{('b2_heartbeat_trace_observer','/')},
        readiness_complete_event=ready))
    stop = asyncio.Event()
    monitor = asyncio.create_task(monitor_owned(supervisor,stop,deadline,api,sink))
    clean = False
    try:
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
        for task in (evaluator,monitor):
            if not task.done(): task.cancel()
        await asyncio.gather(evaluator,monitor,return_exceptions=True)
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
        if time.monotonic() >= total_deadline:
            clean = False
            failures.append({'type':'TotalDeadline','reason':'completion exceeded 300 seconds'})
        # Completion nằm sau sink close; trace phải kiểm đủ coverage riêng trước khi chốt B2.2.
        capture.atomic_publish(run_root/'completion.json',json.dumps({
            'outcomes':outcomes,'failures':failures,'cleanup_clean':clean,
            'stream_sha256':digest((run_root/'observation.jsonl').read_bytes()),
            'trace_audit':'PENDING','owner_visual_review':'NOT_PERFORMED'},default=str).encode())
    return 0 if clean and not failures else 3


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
    review_result(request,result,png,time.monotonic_ns())
    target = Path(request['result_path'])
    if target.parent != request_path.parent or image.parent != request_path.parent:
        raise ValueError('review paths must belong to this run')
    capture.atomic_publish(target,json.dumps(result,sort_keys=True).encode())
    print(json.dumps({'published':str(target),'sha256':digest(target.read_bytes())}))
    return 0


def main():
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
    parser.add_argument('--domain',type=int,choices=(83,),default=83)
    return asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
