import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

from mecanum_nav_rl.observations.step07_gate_b_observer_node import (
    LIFECYCLE_STATE_QOS_CONTRACT, LIFECYCLE_STATE_TOPIC,
    lifecycle_state_qos_profile, validate_vector_samples,
)


def test_accepts_five_immutable_finite_observation81_samples():
    rows = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0] * 81}
            for i in range(1, 6)]
    assert validate_vector_samples(rows)


def test_rejects_partial_nonfinite_and_nonmonotonic_vectors():
    row = {"stamp_ns": 1, "dimension": 81, "dtype": "float32", "values": [0.0] * 81}
    assert not validate_vector_samples([row] * 4)
    assert not validate_vector_samples([dict(row, stamp_ns=i) for i in range(1, 7)])
    bad = [dict(row, stamp_ns=i, values=[0.0] * 80) for i in range(1, 6)]
    assert not validate_vector_samples(bad)
    bad = [dict(row, stamp_ns=i, values=[float("nan")] + [0.0] * 80) for i in range(1, 6)]
    assert not validate_vector_samples(bad)
    bad = [dict(row, stamp_ns=1, values=[0.0] * 81) for _ in range(5)]
    assert not validate_vector_samples(bad)


def test_runtime_observer_source_has_no_with_info_or_command_publisher():
    path = Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "step07_gate_b_observer_node.py"
    source = path.read_text(encoding="utf-8")
    assert "with_info" not in source
    assert "create_publisher" not in source
    assert "cmd_vel" not in source


def test_collector_error_waits_for_result_only_until_existing_deadline(monkeypatch):
    from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
    c=m._Collector.__new__(m._Collector)
    c._finished=False;c.samples=[];c.errors=["LOCAL_REFERENCE_INVALID"];c.navigate_result=None
    c.node=SimpleNamespace(get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=0)))
    c.deadline=10;done=[];c._finish=lambda:done.append(True)
    monkeypatch.setattr(m.time,'monotonic',lambda:1)
    c._tick();assert not done
    c.deadline=0;c._tick();assert done and 'GATE_B_SAMPLE_TIMEOUT' in c.errors


def test_local_reference_adapter_uses_successful_compute_path_result_only():
    source = (Path(__file__).parents[1] / "mecanum_nav_rl" / "observations" / "step07_gate_b_observer_node.py").read_text(encoding="utf-8")
    assert "STATUS_SUCCEEDED" in source
    assert "ComputePathToPose" in source
    assert "_features_from_path" in source
    assert '"map"' in source and '"base_link"' in source


def test_lifecycle_qos_is_reliable_volatile_keep_last_ten_and_separate_from_receipt():
    captured = {}
    def profile(**kwargs):
        captured.update(kwargs)
        return kwargs
    qos = SimpleNamespace(
        QoSProfile=profile,
        HistoryPolicy=SimpleNamespace(KEEP_LAST="KEEP_LAST"),
        ReliabilityPolicy=SimpleNamespace(RELIABLE="RELIABLE"),
        DurabilityPolicy=SimpleNamespace(VOLATILE="VOLATILE"),
    )
    assert lifecycle_state_qos_profile(qos) == {
        "history": "KEEP_LAST", "depth": 10,
        "reliability": "RELIABLE", "durability": "VOLATILE",
    }
    assert LIFECYCLE_STATE_QOS_CONTRACT == {
        "history": "KEEP_LAST", "depth": 10,
        "reliability": "RELIABLE", "durability": "VOLATILE",
    }
    assert LIFECYCLE_STATE_TOPIC == "/mecanum/safety_lifecycle_state"


def test_lifecycle_contract_is_consistent_across_publisher_both_observers_and_validator():
    root = Path(__file__).parents[4]
    py_observer = (root / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/observations/step07_gate_b_observer_node.py").read_text(encoding="utf-8")
    cpp_observer = (root / "ros2_ws/src/step07_nav2_baseline_runtime_observer/src/step07_nav2_baseline_runtime_observer.cpp").read_text(encoding="utf-8")
    publisher = (root / "ros2_ws/src/mecanum_nav_rl/mecanum_nav_rl/runtime_safety/safety_lifecycle_node.py").read_text(encoding="utf-8")
    validator = (root / "artifacts/simulation/step07_nav2_baseline_campaign/tools/step07_gate_b_evidence_validator.py").read_text(encoding="utf-8")
    canonical = "/mecanum/safety_lifecycle_state"
    obsolete = "/mecanum/safety/lifecycle_state"
    assert canonical in publisher and canonical in py_observer and canonical in cpp_observer
    assert 'SafetyLifecycleState, LIFECYCLE_STATE_TOPIC, self._lifecycle, lifecycle_qos' in py_observer
    assert 'SafetyLifecycleState>("/mecanum/safety_lifecycle_state", lifecycle_qos' in cpp_observer
    assert 'durability=qos.DurabilityPolicy.VOLATILE' in py_observer
    assert 'QoS(rclcpp::KeepLast(10)).reliable().durability_volatile()' in cpp_observer
    assert 'durability=DurabilityPolicy.VOLATILE' in publisher
    assert 'depth=10' in publisher and 'depth=10' in py_observer
    assert 'lifecycle_endpoint_qos_contract' in validator
    # The legacy string may appear only as a rejection/snapshot key, never as a subscription target.
    assert obsolete not in [line for line in py_observer.splitlines() if "create_subscription" in line]
    assert obsolete not in [line for line in cpp_observer.splitlines() if "create_subscription" in line]
    lifecycle_qos_body = py_observer.split("def lifecycle_state_qos_profile", 1)[1].split("def _json_bytes", 1)[0]
    assert "TRANSIENT_LOCAL" not in lifecycle_qos_body


def _isolated_ros(script):
    import subprocess
    import sys
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_real_generated_adapters_validator_assembly_and_memory_tf():
    _isolated_ros(r'''
from types import SimpleNamespace as NS
from dataclasses import replace
import math
import numpy as np
from geometry_msgs.msg import PoseStamped, TransformStamped
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry, Path
from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt, SafetyLifecycleState
from tf2_ros import Buffer
from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
from mecanum_nav_rl.observations.lidar import LidarAngularBinner
from mecanum_nav_rl.config.models import ObservationConfig
from mecanum_nav_rl.observations.v3_snapshot_validation import validate_observation_inputs
from mecanum_nav_rl.observations.v3_snapshot_types import ActiveLifecycleConfigContext, LIFECYCLE_BARRIER_CONTRACT_ID

buffer = Buffer()
tf = TransformStamped(); tf.header.frame_id="map"; tf.child_frame_id="base_link"
tf.transform.rotation.w=1.0
buffer.set_transform_static(tf,"fixture")
path=Path(); path.header.frame_id="map"
for x in (0.0, 1.0):
    pose=PoseStamped(); pose.header.frame_id="map"; pose.pose.position.x=x; pose.pose.orientation.w=1.0
    path.poses.append(pose)
assert m._features_from_path(path, buffer, 1000000000) == (1.0,0.0,1.0)
c=m._Collector.__new__(m._Collector)
c.node=NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=1000000000)))
c.tf_buffer=buffer; c.path=path; c.config_hash="a"*64
c._compute_path_requested=c._navigate_requested=True
c._compute_path_calls=c._navigate_calls=1
c._finished=False; c._last_measurement_key=None; c.samples=[]; c.errors=[]
c.args=NS()
c.deadline=m.time.monotonic()+10
c.binner=LidarAngularBinner(ObservationConfig())
c.lidar_binding=m.IngressMessageBinding(LaserScan,"/scan","sensor_msgs/msg/LaserScan","lidar_frame",c._sectorize,None)
c.odom_binding=m.IngressMessageBinding(Odometry,"/odometry/filtered","nav_msgs/msg/Odometry","odom",None,"base_link")
scan=LaserScan(); scan.header.frame_id="lidar_frame"; scan.header.stamp.sec=1
scan.angle_min=-math.pi; scan.angle_increment=2*math.pi/720; scan.range_min=0.1; scan.range_max=10.0; scan.ranges=[math.inf]*720
odom=Odometry(); odom.header.frame_id="odom"; odom.child_frame_id="base_link"; odom.header.stamp.sec=1
life=SafetyLifecycleState(); life.header.stamp.sec=1; life.primary_state=2; life.barrier_state=1; life.motion_permitted=True
life.episode_generation=1; life.reset_epoch=2; life.runtime_generation=3; life.sequence=1
receipt=FinalIssuedCommandReceipt(); receipt.header.stamp.sec=1
receipt.episode_generation=1; receipt.reset_epoch=2; receipt.runtime_generation=3; receipt.source=1; receipt.final_publish_sequence=1
c.latest_scan=scan; c.latest_odom=odom; c.latest_lifecycle=life; c.latest_receipt=receipt; c.navigate_result=None
c._tick()
assert len(c.samples)==1 and not c.errors, c.errors
assert c.samples[0]["dimension"]==81 and c.samples[0]["dtype"]=="float32"
ctx=ActiveLifecycleConfigContext(LIFECYCLE_BARRIER_CONTRACT_ID,1,2,3,c.config_hash)
lidar=m.adapt_lidar_message(scan,binding=c.lidar_binding,context=ctx)
twist=m.adapt_measured_twist_message(odom,binding=c.odom_binding,context=ctx)
local=m.adapt_local_reference_message(path,binding=m.IngressMessageBinding(Path,None,"nav_msgs/msg/Path","map",lambda _: (1.0,0.0,1.0),None),context=ctx)
rc=m.FinalIssuedReceiptContext(contract_id=LIFECYCLE_BARRIER_CONTRACT_ID,frame_contract_id=m.FRAME_TF_CONTRACT_ID,episode_generation=1,reset_epoch=2,runtime_generation=3,config_hash=c.config_hash,frame_id="base_link",final_command=(0.0,0.0,0.0),topic_claim=m.BINDING_CLAIMS.receipt_topic,type_claim=m.BINDING_CLAIMS.receipt_type)
assert validate_observation_inputs(context=ctx,lidar=lidar,local_reference=local,measured_twist=twist,receipt=rc) is None
admitted=validate_observation_inputs(context=ctx,lidar=lidar,local_reference=local,measured_twist=twist,receipt=rc,fixture_claims=m.BINDING_CLAIMS)
vector=m.assemble_observation(admitted)
assert vector.ready and vector.vector.dtype==np.float32 and not vector.vector.flags.writeable
assert validate_observation_inputs(context=ctx,lidar=lidar,local_reference=local,measured_twist=twist,receipt=rc,fixture_claims=replace(m.BINDING_CLAIMS,lidar_topic="/wrong")) is None
# Clock/future/identity/TF chưa sẵn sàng không được tạo sample giả.
c._last_measurement_key=None
for now in (0, 999999999, 2000000000):
    c.node=NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=now)))
    c._tick(); assert len(c.samples)==1
c.node=NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=1000000000)))
receipt.runtime_generation=4
c._tick(); assert len(c.samples)==1 and not c.errors
receipt.runtime_generation=3
c.tf_buffer=Buffer()
c._tick(); assert len(c.samples)==1 and not c.errors
''')


def test_clock_freshness_rejects_future_and_stale():
    from mecanum_nav_rl.observations.step07_gate_b_observer_node import fresh_stamp
    assert fresh_stamp(10, 10, 5) and fresh_stamp(10, 5, 5)
    assert not fresh_stamp(10, 11, 5)
    assert not fresh_stamp(10, 4, 5)
    assert not fresh_stamp(10, 0, 5)


def test_async_actions_sent_once_and_completion_verdict_uses_actual_results():
    from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
    c = m._Collector.__new__(m._Collector)
    calls = []
    client = SimpleNamespace(server_is_ready=lambda: False,
                             send_goal_async=lambda goal: calls.append(goal))
    c.compute = c.navigate = client
    c._compute_path_requested = c._navigate_requested = False
    c._compute_path_calls = c._navigate_calls = 0
    c.errors = []
    c._request_path_once(); c._navigate_once()
    assert not calls
    client.server_is_ready = lambda: True
    client.send_goal_async = lambda goal: (calls.append(goal) or SimpleNamespace(add_done_callback=lambda cb: None))
    c.ComputePathToPose = SimpleNamespace(Goal=lambda: SimpleNamespace())
    c.NavigateToPose = SimpleNamespace(Goal=lambda: SimpleNamespace())
    c._goal_pose = lambda: object()
    c._request_path_once(); c._request_path_once()
    c._navigate_once(); c._navigate_once()
    assert len(calls) == 2 and c._compute_path_calls == c._navigate_calls == 1
    assert c.errors == ["NAVIGATE_TO_POSE_RETRY_FORBIDDEN"]
    c._finished = c._peer_verified = True; c.path = object()
    c.samples = [{"stamp_ns": i, "dimension": 81, "dtype": "float32", "values": [0.0]*81} for i in range(1, 6)]
    c.navigate_result = {"succeeded": False}
    c.errors = []
    assert not c.passed()
    c.navigate_result = {"succeeded": True}
    assert c.passed()
    c._navigate_calls = 0
    assert not c.passed()


def test_goal_trigger_is_config_bound_and_required_before_action_start(tmp_path):
    import json
    from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
    c = m._Collector.__new__(m._Collector)
    c.args = SimpleNamespace(start_path=tmp_path / "trigger.json")
    c.config_hash = "a" * 64
    assert not c._read_goal_trigger()
    c.args.start_path.write_text(json.dumps({"state": "TRIGGER_GOAL", "config_hash": "b" * 64,
                                            "collector_ready": True}), encoding="utf-8")
    assert not c._read_goal_trigger()
    c.args.start_path.write_text(json.dumps({"state": "TRIGGER_GOAL", "config_hash": "a" * 64,
        "collector_ready": True, "navigate_to_pose_action_server_ready": True,
        "ready_collectors": ["step07_nav2_baseline_runtime_observer", "step07_gate_b_observer",
                             "navigation_evidence_chain_collector"]}), encoding="utf-8")
    assert c._read_goal_trigger()


def test_peer_lifetime_atomic_once_early_and_late_goal_and_failures(tmp_path, monkeypatch):
    import json
    import pytest
    from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
    for early in (True, False):
        peer = tmp_path / f"peer-{early}.json"
        output = tmp_path / f"gate-{early}.json"
        events = []
        c = m._Collector.__new__(m._Collector)
        c.args = SimpleNamespace(output=output, peer_evidence_path=peer, peer_timeout_sec=10)
        c.config_hash = "a"*64; c._finished = c._closed = c._peer_verified = False
        c.samples=[{"stamp_ns":i,"dimension":81,"dtype":"float32","values":[0.0]*81} for i in range(1,6)]
        c.raw={}; c.errors=[]; c.path=SimpleNamespace(header=SimpleNamespace(frame_id="map")); c.path_transcript={}
        c._compute_path_requested=c._navigate_requested=True
        c._compute_path_calls=c._navigate_calls=1
        c.navigate_result={"accepted":True,"succeeded":True,"status":4}
        c.node=SimpleNamespace(destroy_node=lambda: events.append("destroy"))
        c.timer=SimpleNamespace(cancel=lambda: events.append("cancel"))
        c.rclpy=SimpleNamespace(ok=lambda: True, shutdown=lambda: events.append("shutdown"))
        if not early:
            peer.write_text(json.dumps({"schema_version":"1.0","config_hash": c.config_hash, "acceptance": {"graph": True}}))
        c._finish()
        original = output.read_bytes()
        assert all(json.loads(original)["acceptance"].values())
        assert c._closed is (not early)
        if early:
            peer.write_text(json.dumps({"schema_version":"1.0","config_hash": c.config_hash, "acceptance": {"graph": True}}))
            c._wait_peer()
        assert c._peer_verified and c._closed and events == ["cancel", "destroy", "shutdown"]
        c._finish(); assert output.read_bytes() == original
    peer.write_text(json.dumps({"schema_version":"1.0","config_hash": "b"*64, "acceptance": {"graph": True}}))
    with pytest.raises(ValueError, match="GATE_B_PEER_CONFIG_HASH_MISMATCH"):
        m.peer_evidence_ready(peer, "a"*64)
    c._closed=False; c._peer_verified=False; c.errors=[]
    c._wait_peer(); assert c._closed and c.errors == ["GATE_B_PEER_CONFIG_HASH_MISMATCH"]
    peer.unlink(); c._closed=False; c.errors=[]; c._peer_deadline=0
    c._wait_peer(); assert c._closed and c.errors == ["GATE_B_PEER_EVIDENCE_TIMEOUT"]
    c.errors.append("OBSERVER_INTERRUPTED")
    assert not c.passed()


def test_constructor_sim_clock_buffer_binding_and_steady_watchdog_without_graph():
    _isolated_ros(r'''
from types import SimpleNamespace as NS
from unittest.mock import patch
import rclpy, rclpy.action, tf2_ros
from rclpy.clock import ClockType
from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
captured={}; subscriptions=[]; sends=[]
node=NS(create_subscription=lambda *args: subscriptions.append(args),
        create_timer=lambda interval,callback,**kw: captured.update(timer=kw) or NS(cancel=lambda:None),
        get_clock=lambda:NS(now=lambda:NS(nanoseconds=0)))
def create_node(name,**kwargs):
    captured.update(node_options=kwargs); return node
def buffer(**kwargs): captured.update(buffer_options=kwargs); return NS()
def action(*args):
    return NS(server_is_ready=lambda:False,send_goal_async=lambda goal:sends.append(goal))
args=NS(config_hash="a"*64,goal_x=-4.,goal_y=0.,goal_yaw=0.,timeout_sec=10)
with patch.object(rclpy,"create_node",create_node), patch.object(tf2_ros,"Buffer",buffer), patch.object(tf2_ros,"TransformListener",lambda *args:None), patch.object(rclpy.action,"ActionClient",action):
    c=m._Collector(args)
assert captured["node_options"]["parameter_overrides"][0].name=="use_sim_time"
assert captured["node_options"]["parameter_overrides"][0].value is True
assert captured["buffer_options"]=={"node":node}
assert captured["timer"]["clock"].clock_type==ClockType.STEADY_TIME
assert len(subscriptions)==4 and not sends
c._tick(); assert not sends and not c.samples
finished=[]; c._finish=lambda:finished.append(True)
c.deadline=0
c._tick(); assert finished and c.errors==["GATE_B_SAMPLE_TIMEOUT"]
c.navigate_result={"accepted":False,"status":"REJECTED"}
c._tick(); assert finished and c.errors==["GATE_B_SAMPLE_TIMEOUT"]
''')


def test_interruption_writes_rejected_result_once_and_closes_without_action_retry(tmp_path, monkeypatch):
    import json
    import sys
    import signal
    from types import ModuleType
    from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
    c=m._Collector.__new__(m._Collector)
    c.args=SimpleNamespace(output=tmp_path/"gate.json",peer_evidence_path=tmp_path/"peer.json",
        peer_timeout_sec=10,ready_path=tmp_path/"ready.json",start_path=tmp_path/"start.json")
    c.config_hash="a"*64; c._finished=c._closed=c._peer_verified=False
    c.samples=[]; c.raw={}; c.errors=[]; c.path=None; c.path_transcript=None
    c._compute_path_requested=c._navigate_requested=False; c._compute_path_calls=c._navigate_calls=0
    c.navigate_result=None
    events=[]
    c.node=SimpleNamespace(destroy_node=lambda:events.append("destroy"))
    c.timer=SimpleNamespace(cancel=lambda:events.append("cancel"))
    c._peer_deadline=0
    c.navigate_result=None
    c.GoalStatus=SimpleNamespace()
    c.rclpy=SimpleNamespace(ok=lambda:True)
    c.node.destroy_node=lambda:events.append("destroy")
    signals=ModuleType("rclpy.signals"); signals.SignalHandlerOptions=SimpleNamespace(NO="NO")
    ros_state={"ok":True}
    def shutdown():
        events.append("shutdown"); ros_state["ok"]=False
    ros=SimpleNamespace(init=lambda **kwargs:None,spin_once=lambda *args,**kwargs:None,
        create_node=lambda *args,**kwargs:c.node,ok=lambda:ros_state["ok"],shutdown=shutdown)
    c.rclpy=ros
    previous=signal.getsignal(signal.SIGINT)
    fired={"value":False}
    def fake_signal(signum, handler):
        old=previous
        if signum == signal.SIGINT and callable(handler) and not fired["value"]:
            fired["value"]=True
            handler(signum,None)
        return old
    monkeypatch.setattr(signal,"signal",fake_signal)
    monkeypatch.setitem(sys.modules,"rclpy",ros)
    monkeypatch.setitem(sys.modules,"rclpy.signals",signals)
    monkeypatch.setattr(m,"_Collector",lambda args:c)
    assert m.main(["--output",str(c.args.output),"--config-hash",c.config_hash,
                   "--peer-evidence-path",str(c.args.peer_evidence_path),"--invocation-id","offline-fixture",
                   "--ready-path",str(c.args.ready_path),"--start-path",str(c.args.start_path)]) == 2
    doc=json.loads(c.args.output.read_bytes())
    assert doc["errors"] == ["GATE_B_COLLECTOR_INTERRUPTED"]
    assert not doc["acceptance"]["navigate_to_pose_requested_once"]
    assert events == ["cancel","destroy","shutdown"]
    assert c._navigate_calls == c._compute_path_calls == 0


def test_gate_b_readiness_explicitly_records_live_process_context_and_subscriptions():
    from types import SimpleNamespace as NS
    from mecanum_nav_rl.observations.step07_gate_b_observer_node import _Collector

    collector = _Collector.__new__(_Collector)
    collector.rclpy = NS(ok=lambda: True)
    collector.node = NS(context=NS(ok=lambda: True))
    collector.subscriptions = [object()] * 4
    collector.navigate = NS(server_is_ready=lambda: True)
    collector.config_hash = "a" * 64
    ready = collector._ready_document()
    assert ready["state"] == "READY"
    assert ready["process_alive"] is True
    assert ready["ros_context_valid"] is True
    assert len(ready["subscriptions_created"]) == 4
    assert ready["navigate_to_pose_action_server_ready"] is True


def _peer_pending_collector(tmp_path, finish=True):
    from mecanum_nav_rl.observations import step07_gate_b_observer_node as m
    c=m._Collector.__new__(m._Collector)
    c.args=SimpleNamespace(output=tmp_path/'gate_b_vectors.json',peer_evidence_path=tmp_path/'runtime_observer.json',
        terminal_output=tmp_path/'gate_b_terminal.json',peer_timeout_sec=60,invocation_id='offline-fixture')
    c.config_hash='a'*64;c._finished=c._closed=c._peer_verified=False
    c.samples=[{'stamp_ns':i,'dimension':81,'dtype':'float32','values':[0.0]*81} for i in range(1,6)]
    c.raw={};c.errors=[];c.path=SimpleNamespace(header=SimpleNamespace(frame_id='map'));c.path_transcript={}
    c._compute_path_requested=c._navigate_requested=True;c._compute_path_calls=c._navigate_calls=1
    c.navigate_result={'accepted':True,'succeeded':True,'status':4}
    events=[];c.node=SimpleNamespace(destroy_node=lambda:events.append('destroy'))
    c.timer=SimpleNamespace(cancel=lambda:None);c.rclpy=SimpleNamespace(ok=lambda:True,shutdown=lambda:None)
    if finish:c._finish()
    return c,m,events


def test_peer_failures_after_collection_have_distinct_immutable_terminal_evidence(tmp_path,monkeypatch):
    import json
    for failure in ('timeout','config','invocation','malformed','snapshot'):
        target=tmp_path/failure;target.mkdir()
        c,m,events=_peer_pending_collector(target);original=c.args.output.read_bytes()
        assert not c.args.terminal_output.exists() and not c._closed
        if failure=='timeout':c._peer_deadline=0
        elif failure=='malformed':c.args.peer_evidence_path.write_bytes(b'{')
        else:
            peer={'schema_version':'1.0','config_hash':c.config_hash,'invocation_id':c.args.invocation_id,
                'snapshot_complete':True,'acceptance':{'graph':True}}
            peer[{'config':'config_hash','invocation':'invocation_id','snapshot':'snapshot_complete'}[failure]]='wrong'
            c.args.peer_evidence_path.write_text(json.dumps(peer))
        c._wait_peer()
        assert c._closed and events==['destroy'] and not c.passed()
        terminal=json.loads(c.args.terminal_output.read_bytes())
        assert terminal['status']=='FAIL' and terminal['errors'] and not terminal['peer_verified']
        assert c.args.output.read_bytes()==original
        assert json.loads(original)['protocol_phase']=='COLLECTION_COMPLETE_AWAITING_PEER'
        final=c.args.terminal_output.read_bytes();c._close();assert c.args.terminal_output.read_bytes()==final


def test_missing_action_result_deadline_finishes_without_fabricating_navigation(tmp_path,monkeypatch):
    import json
    c,m,events=_peer_pending_collector(tmp_path,finish=False)
    c.samples=[];c.navigate_result=None
    c._publish_ready_when_complete=lambda:None
    c.node.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=0))
    c.deadline=0;c._tick()
    doc=json.loads(c.args.output.read_bytes())
    assert doc['navigate_to_pose']['status']=='NO_RESULT'
    assert not doc['acceptance']['navigate_to_pose_succeeded'] and 'GATE_B_SAMPLE_TIMEOUT' in doc['errors']
    c._peer_deadline=0;c._tick()
    terminal=json.loads(c.args.terminal_output.read_bytes())
    assert terminal['status']=='FAIL' and 'GATE_B_SAMPLE_TIMEOUT' in terminal['errors']
