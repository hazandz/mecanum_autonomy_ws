"""Offline design model; production baseline calls the source _Collector._tick and _features_from_path.
No ROS node, graph, Gazebo, Nav2, campaign process, or source edits are performed.
"""
from __future__ import annotations
import copy, importlib, json, math, sys
from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace as NS

REPO = Path('/home/hazan/step07-integrated-nav2-gateb-campaign-f7f98c6')
sys.path.insert(0, str(REPO / 'ros2_ws/src/mecanum_nav_rl'))
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path as NavPath
from tf2_ros import ExtrapolationException, ConnectivityException
from action_msgs.msg import GoalStatus
from mecanum_nav_rl.observations import step07_gate_b_observer_node as production

# Keep imports real except the pure Time(nanoseconds=...) factory used by _tick.
_original_import = importlib.import_module
class FakeTime:
    def __init__(self, *, nanoseconds: int): self.nanoseconds = nanoseconds
production.importlib.import_module = lambda name, *a, **kw: NS(Time=FakeTime) if name == 'rclpy.time' else _original_import(name, *a, **kw)
production.time.monotonic = lambda: 1.0

class Clock:
    def __init__(self, ns): self.ns = ns
    def now(self): return NS(nanoseconds=self.ns, to_msg=lambda: NS(sec=self.ns//10**9, nanosec=self.ns%10**9))
class Node:
    def __init__(self, ns): self.clock = Clock(ns)
    def get_clock(self): return self.clock
class FakeTF:
    def __init__(self, lower=0, upper=0, connected=True):
        self.lower, self.upper, self.connected = lower, upper, connected
        self.queries, self.lookups = [], []
    def can_transform(self, target, source, stamp):
        t=stamp.nanoseconds; self.queries.append((target, source, t))
        return self.connected and self.lower <= t <= self.upper
    def transform(self, pose, target):
        t=pose.header.stamp.sec*10**9+pose.header.stamp.nanosec
        self.lookups.append((target, pose.header.frame_id, t))
        if not self.connected: raise ConnectivityException('fake: graph edge unavailable')
        if t > self.upper: raise ExtrapolationException('fake: future extrapolation')
        if t < self.lower: raise ExtrapolationException('fake: past extrapolation')
        out=copy.deepcopy(pose); out.header.frame_id=target; return out

def make_path():
    p=NavPath(); p.header.frame_id='map'
    for x in (0.0, 1.0):
        q=PoseStamped(); q.header.frame_id='map'; q.pose.position.x=x; q.pose.orientation.w=1.0; p.poses.append(q)
    return p

def production_collector(now, tf):
    c=production._Collector.__new__(production._Collector)
    c.node=Node(now); c.tf_buffer=tf; c._finished=False; c.samples=[]; c.errors=[]; c.navigate_result=None
    c.diagnostics=production._new_collector_diagnostics(); c.deadline=10**99
    c._publish_ready_when_complete=lambda:None; c._read_goal_trigger=lambda:True
    c._compute_path_requested=False; c._navigate_requested=False; c.path=None
    c.latest_lifecycle=c.latest_scan=c.latest_odom=c.latest_receipt=None
    return c

@dataclass(frozen=True)
class Identity:
    episode_generation: int
    reset_epoch: int
    runtime_generation: int
    config_hash: str
@dataclass(frozen=True)
class InputSnapshot:
    snapshot_id: str
    identity: Identity
    cutoff_ros_ns: int
    scan_stamp_ns: int
    odom_stamp_ns: int
    lifecycle_stamp_ns: int
    receipt_stamp_ns: int
    receipt_sequence: int
    odom_record_id: str
    lifecycle_sequence: int
    action_barrier_ns: int
    reset_barrier_ns: int
    scan_received_steady_ns: int
    odom_received_steady_ns: int
    lifecycle_received_steady_ns: int
    receipt_received_steady_ns: int
    path_id: str
    path: object
    path_version: int = 1
    barrier_revision: int = 0

class FixedTimestampModel:
    """Proposal-only controller: pin timestamps/snapshot; poll in timer; never block."""
    LIMITS={'scan':500_000_000,'odom':250_000_000,'lifecycle':500_000_000,'receipt':500_000_000}
    def __init__(self, run_deadline_steady_ns):
        self.run_deadline=run_deadline_steady_ns; self.phase_a_stamp=None; self.pending=None
        self.state='IDLE'; self.last_ros_now=None; self.committed=[]; self.discards=[]
        self.action_callbacks=0; self.nav='PENDING'; self.planner='NOT_REQUESTED'
        self.planner_request_count=0; self.phase_a_poll_stamps=[]
    def trigger_phase_a(self, ros_now_ns, identity):
        if ros_now_ns <= 0: self.state='WAIT_CLOCK'; return False
        if self.phase_a_stamp is not None: return False
        self.phase_a_stamp=ros_now_ns; self.phase_a_identity=identity; self.state='PHASE_A_WAIT_TF'; return True
    def rearm_phase_a_query(self):
        # Re-arm only the asynchronous poll; preserve t_A and the once-only goal latch.
        if self.phase_a_stamp is None or self.planner_request_count:
            return False
        self.state='PHASE_A_WAIT_TF'
        return True
    def poll_phase_a(self, ros_now_ns, steady_ns, tf):
        if ros_now_ns <= 0: return 'WAIT_CLOCK'
        if self.last_ros_now is not None and ros_now_ns < self.last_ros_now: self.state='FAILED_CLOCK_ROLLBACK'; return self.state
        self.last_ros_now=ros_now_ns
        if steady_ns >= self.run_deadline: self.state='FAIL_EXISTING_RUN_DEADLINE'; return self.state
        self.phase_a_poll_stamps.append(self.phase_a_stamp)
        if tf.can_transform('base_link','map',FakeTime(nanoseconds=self.phase_a_stamp)):
            self.state='PHASE_A_READY'
            if self.planner_request_count == 0:
                self.planner_request_count=1; self.planner='REQUESTED_ONCE'
            return self.state
        return self.state
    def capture_sample(self, snapshot: InputSnapshot, ros_now_ns, steady_ns, active_identity):
        if ros_now_ns <= 0: self.discards.append({'snapshot_id':snapshot.snapshot_id,'reason':'CLOCK_NOT_STARTED'}); return False
        if self.last_ros_now is not None and ros_now_ns < self.last_ros_now:
            self.pending=None; self.discards.append({'snapshot_id':snapshot.snapshot_id,'reason':'CLOCK_ROLLBACK'}); return False
        self.last_ros_now=ros_now_ns
        if steady_ns >= self.run_deadline: self.discards.append({'snapshot_id':snapshot.snapshot_id,'reason':'RUN_DEADLINE'}); return False
        if snapshot.identity != active_identity: self.discards.append({'snapshot_id':snapshot.snapshot_id,'reason':'IDENTITY_MISMATCH_AT_CAPTURE'}); return False
        if not self._eligible(snapshot, ros_now_ns): self.discards.append({'snapshot_id':snapshot.snapshot_id,'reason':'INPUT_NOT_ELIGIBLE_AT_CAPTURE'}); return False
        # The proposed Phase B transform timestamp is the exact odometry stamp.
        # No message/header/path object is rewritten; identity and bytes stay pinned.
        self.pending={'snapshot':copy.deepcopy(snapshot),'tf_stamp_ns':snapshot.odom_stamp_ns,
                      'captured_identity':snapshot.identity,'captured_steady_ns':steady_ns,
                      'barrier_revision':snapshot.barrier_revision,'path_version':snapshot.path_version}
        return True
    def action_callback(self, name, state):
        # Models executor callback progress while a timer poll returns immediately.
        self.action_callbacks += 1
        if name=='navigate': self.nav=state
        elif name=='planner': self.planner=state
    def poll_sample(self, ros_now_ns, steady_ns, tf, active_identity, active_lifecycle_ok=True, active_barrier_revision=None, active_path_version=None):
        if self.pending is None: return 'NO_PENDING'
        snap=self.pending['snapshot']
        if ros_now_ns <= 0: return 'WAIT_CLOCK'
        if self.last_ros_now is not None and ros_now_ns < self.last_ros_now:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'CLOCK_ROLLBACK'}); self.pending=None; return 'DISCARDED_CLOCK_ROLLBACK'
        self.last_ros_now=ros_now_ns
        if snap.identity != active_identity:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'GENERATION_EPOCH_CONFIG_CHANGED'}); self.pending=None; return 'DISCARDED_IDENTITY'
        if not active_lifecycle_ok:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'LIFECYCLE_OR_BARRIER_CHANGED'}); self.pending=None; return 'DISCARDED_LIFECYCLE'
        if active_barrier_revision is not None and active_barrier_revision != self.pending['barrier_revision']:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'BARRIER_REVISION_CHANGED'}); self.pending=None; return 'DISCARDED_BARRIER'
        if active_path_version is not None and active_path_version != self.pending['path_version']:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'PATH_VERSION_CHANGED'}); self.pending=None; return 'DISCARDED_PATH_VERSION'
        if not self._eligible(snap, ros_now_ns):
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'INPUT_STALE_OR_FUTURE_AT_COMMIT'}); self.pending=None; return 'DISCARDED_FRESHNESS'
        if steady_ns >= self.run_deadline:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'EXISTING_RUN_DEADLINE'}); self.pending=None; return 'FAIL_EXISTING_RUN_DEADLINE'
        stamp=FakeTime(nanoseconds=self.pending['tf_stamp_ns'])
        if not tf.can_transform('base_link','map',stamp): return 'WAIT_TF_SAME_STAMP'
        # Production helper constructs a transformed copy and preserves input Path.
        features=production._features_from_path(copy.deepcopy(snap.path),tf,self.pending['tf_stamp_ns'])
        key=(snap.snapshot_id,snap.scan_stamp_ns,snap.odom_stamp_ns,snap.receipt_sequence,snap.lifecycle_sequence)
        vector_stamp=snap.cutoff_ros_ns
        if self.committed and vector_stamp <= self.committed[-1]['vector_stamp_ns']:
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'NONMONOTONIC_VECTOR_STAMP'}); self.pending=None; return 'DISCARDED_NONMONOTONIC'
        if any(row['key']==key for row in self.committed):
            self.discards.append({'snapshot_id':snap.snapshot_id,'reason':'DUPLICATE_SNAPSHOT'}); self.pending=None; return 'DISCARDED_DUPLICATE'
        self.committed.append({'key':key,'t_vector_ns':vector_stamp,'t_tf_ns':self.pending['tf_stamp_ns'],'t_odom_ns':snap.odom_stamp_ns,'t_commit_ros_ns':ros_now_ns,'vector_stamp_ns':vector_stamp,'tf_stamp_ns':self.pending['tf_stamp_ns'],
                               'receipt_sequence':snap.receipt_sequence,'odom_record_id':snap.odom_record_id,
                               'path_id':snap.path_id,'features':features,'dimension_contract':81})
        self.pending=None
        return 'COMMITTED'
    def _eligible(self,s,now):
        pairs=(('scan',s.scan_stamp_ns),('odom',s.odom_stamp_ns),('lifecycle',s.lifecycle_stamp_ns),('receipt',s.receipt_stamp_ns))
        for name,stamp in pairs:
            age=now-stamp
            if age < 0 or age > self.LIMITS[name]: return False
        if not (s.receipt_stamp_ns > s.action_barrier_ns and s.receipt_stamp_ns > s.reset_barrier_ns): return False
        if s.receipt_stamp_ns > s.cutoff_ros_ns: return False
        if s.identity.episode_generation < 0: return False
        return True
    def campaign_pass(self):
        return len(self.committed)==5 and self.nav=='SUCCEEDED' and self.planner=='SUCCEEDED'

def snapshot(i, stamp, *, identity=None, receipt_sequence=None, odom_id=None, path=None, odom_stamp=None, receipt_stamp=None, barrier_revision=0, path_version=1):
    identity=identity or Identity(3,2,7,'a'*64)
    path=path or make_path()
    return InputSnapshot(f'snap-{i}',identity,stamp,stamp,stamp if odom_stamp is None else odom_stamp,stamp,stamp if receipt_stamp is None else receipt_stamp,i if receipt_sequence is None else receipt_sequence,
                         f'odom-{i}' if odom_id is None else odom_id,i,0,0,stamp,stamp,stamp,stamp,'path-1',path,path_version,barrier_revision)

results=[]
def record(name, baseline, proposed, **details): results.append({'case':name,'baseline':baseline,'proposed':proposed,**details})

# 1. Production baseline: moving now misses a transform that arrives only after each query time.
base_counts=[]; tf=FakeTF()
for now,upper in ((10_000_000_000,9_980_000_000),(10_050_000_000,10_030_000_000),(10_100_000_000,10_080_000_000)):
    tf.upper=upper; c=production_collector(now,tf); c._tick()
    base_counts.append({'query_ns':tf.queries[-1][2],'tf_available':c.diagnostics['tf']['state']=='AVAILABLE','planner_requested':c._compute_path_requested})
model=FixedTimestampModel(20_000_000_000); ident=Identity(3,2,7,'a'*64); model.trigger_phase_a(10_000_000_000,ident)
phase_a=[]
for now,upper in ((10_000_000_000,9_980_000_000),(10_050_000_000,10_000_000_000),(10_100_000_000,10_080_000_000)):
    tf.upper=upper; phase_a.append({'now_ns':now,'fixed_query_ns':model.phase_a_stamp,'state':model.poll_phase_a(now,now,tf)})
record('phase_a_late_tf_within_existing_window',base_counts,phase_a,planner_request_once=model.planner=='REQUESTED_ONCE')

# 2. Phase B late TF: baseline production uses moving now and fails; proposal pins odom stamp.
path=make_path(); tf=FakeTF(upper=10_000_000_000)
production_fail=[]
for now,upper in ((10_050_000_000,10_000_000_000),(10_100_000_000,10_050_000_000)):
    tf.upper=upper
    try: production._features_from_path(path,tf,now); production_fail.append('PASS')
    except ValueError as e: production_fail.append(str(e))
model=FixedTimestampModel(20_000_000_000); s=snapshot(1,10_000_000_000,path=path); model.capture_sample(s,10_000_000_000,10_000_000_000,s.identity)
late=[]
for now,upper in ((10_050_000_000,9_980_000_000),(10_100_000_000,10_000_000_000)):
    tf.upper=upper; late.append(model.poll_sample(now,now,tf,s.identity))
record('phase_b_tf_arrives_after_selection_but_data_fresh',production_fail,late,committed=model.committed)

# 2b. Production helper mutates the selected input pose header; proposal transforms a deep copy.
path_input=make_path(); path_input.poses[1].header.stamp.sec=2; before=(path_input.poses[1].header.stamp.sec,path_input.poses[1].header.stamp.nanosec)
exact_tf=FakeTF(lower=0,upper=4_000_000_000); production._features_from_path(path_input,exact_tf,3_000_000_004)
after=(path_input.poses[1].header.stamp.sec,path_input.poses[1].header.stamp.nanosec)
proposal_input=make_path(); proposal_input.poses[1].header.stamp.sec=2; proposal_before=(proposal_input.poses[1].header.stamp.sec,proposal_input.poses[1].header.stamp.nanosec)
production._features_from_path(copy.deepcopy(proposal_input),exact_tf,3_000_000_004)
proposal_after=(proposal_input.poses[1].header.stamp.sec,proposal_input.poses[1].header.stamp.nanosec)
record('path_pose_input_immutability',{'input_mutated':before!=after,'before':before,'after':after},{'input_mutated':proposal_before!=proposal_after,'before':proposal_before,'after':proposal_after})

# 3. Never arrives: wait is bounded by the existing whole-run steady deadline, no new TF budget.
model=FixedTimestampModel(30); s=snapshot(1,10_000_000_000); model.capture_sample(s,10_000_000_000,10, s.identity); tf=FakeTF(upper=0)
states=[model.poll_sample(10_020_000_000,20,tf,s.identity),model.poll_sample(10_030_000_000,30,tf,s.identity)]
record('tf_never_arrives',None,states,discard=model.discards,run_deadline_steady_ns=model.run_deadline)

# 4. TF arrives only after odometry freshness (250 ms) expires: no commit.
model=FixedTimestampModel(2_000_000_000); s=snapshot(1,10_000_000_000); model.capture_sample(s,10_000_000_000,10,s.identity); tf=FakeTF(upper=10_000_000_000)
state=model.poll_sample(10_300_000_001,20,tf,s.identity)
record('tf_after_input_expiry',None,state,discard=model.discards,existing_odom_limit_ns=model.LIMITS['odom'])

# 5. Future, past and disconnected conditions never get converted into data; wait ends at existing deadline.
for label,lower,upper,connected,t in [('future',0,9_000_000_000,True,10_000_000_000),('past',11_000_000_000,20_000_000_000,True,10_000_000_000),('missing_connectivity',0,20_000_000_000,False,10_000_000_000)]:
    f=FakeTF(lower,upper,connected); m2=FixedTimestampModel(100); ss=snapshot(1,t); m2.capture_sample(ss,t,1,ss.identity)
    state=m2.poll_sample(t+10,2,f,ss.identity)

    try:
        production._features_from_path(make_path(),f,t); wrapped='NO_ERROR'
    except ValueError as e:
        wrapped=f'{e};cause={type(e.__cause__).__name__}'
    record(label,None,state,tf_query_calls=len(f.queries),tf_lookup_calls=len(f.lookups),no_commit=len(m2.committed)==0,production_wrapped_failure=wrapped)

# 6. Clock zero, rollback, forward jump.
for label,first,second in [('clock_zero',0,10_000_000_000),('clock_rollback',10_000_000_000,9_900_000_000),('clock_forward_stales_inputs',10_000_000_000,10_300_000_001)]:
    m2=FixedTimestampModel(10**12); ss=snapshot(1,10_000_000_000); captured=m2.capture_sample(ss,first,1,ss.identity) if first>0 else m2.capture_sample(ss,first,1,ss.identity)
    f=FakeTF(upper=20_000_000_000); state=m2.poll_sample(second,2,f,ss.identity) if captured else 'NO_PENDING_CLOCK_ZERO'
    record(label,None,state,captured=captured,discards=m2.discards)

# 7. Lifecycle identity change and input updates while waiting: never mix latest records.
old=Identity(3,2,7,'a'*64); new=Identity(3,3,8,'a'*64); ss=snapshot(1,10_000_000_000,identity=old,receipt_sequence=91,odom_id='odom-exact-77')
m2=FixedTimestampModel(10**12); m2.capture_sample(ss,10_000_000_000,1,old); latest={'receipt_sequence':92,'odom_record_id':'odom-new-78','identity':new}; f=FakeTF(upper=20_000_000_000)
state=m2.poll_sample(10_010_000_000,2,f,latest['identity'])
record('generation_epoch_change_during_wait',None,state,latest_not_used=True,discards=m2.discards)
old=Identity(3,2,7,'a'*64); ss=snapshot(1,10_000_000_000,identity=old,receipt_sequence=91,odom_id='odom-exact-77')
m2=FixedTimestampModel(10**12); m2.capture_sample(ss,10_000_000_000,1,old); latest={'receipt_sequence':92,'odom_record_id':'odom-new-78'}; f=FakeTF(upper=10_000_000_000)
state=m2.poll_sample(10_010_000_000,2,f,old)
record('receipt_odom_update_while_pending',None,state,latest=latest,committed=m2.committed,assert_pinned=(m2.committed[0]['receipt_sequence']==91 and m2.committed[0]['odom_record_id']=='odom-exact-77'))

# 8. Action callbacks run between nonblocking polls; navigation states do not imply sample acceptance.
m2=FixedTimestampModel(10**12); ss=snapshot(1,10_000_000_000); m2.capture_sample(ss,10_000_000_000,1,ss.identity); m2.action_callback('navigate','PENDING'); f=FakeTF(upper=10_000_000_000); state=m2.poll_sample(10_010_000_000,2,f,ss.identity)
record('action_callback_during_tf_wait',None,state,callback_count=m2.action_callbacks,navigate=m2.nav)

# 9. Exact sample time, duplicates, increasing stamps, five samples, navigation terminal outcomes.
m2=FixedTimestampModel(10**12); f=FakeTF(upper=20_000_000_000); commit_states=[]
for i in range(1,6):
    t=10_000_000_000+i*10_000_000; ss=snapshot(i,t); m2.capture_sample(ss,t,t,ss.identity); commit_states.append(m2.poll_sample(t,t,f,ss.identity))
# Duplicate last exact snapshot rejected without a sixth sample.
last=replace(snapshot(5,10_050_000_000),cutoff_ros_ns=10_060_000_000); m2.capture_sample(last,10_050_000_000,10_050_000_000,last.identity); duplicate=m2.poll_sample(10_051_000_000,10_051_000_000,f,last.identity)
m2.planner='SUCCEEDED'; m2.nav='PENDING'; pending_pass=m2.campaign_pass(); m2.action_callback('navigate','ABORTED'); failed_pass=m2.campaign_pass()
m3=FixedTimestampModel(10**12); f3=FakeTF(upper=21_000_000_000)
for i in range(1,6):
    t=20_000_000_000+i*10_000_000; ss=snapshot(i,t); m3.capture_sample(ss,t,t,ss.identity); m3.poll_sample(t,t,f3,ss.identity)
m3.planner='SUCCEEDED'; m3.nav='SUCCEEDED'; success_pass=m3.campaign_pass()
record('five_monotonic_samples_and_navigation_gating',None,commit_states,duplicate=duplicate,sample_count=len(m2.committed),vector_stamps=[x['vector_stamp_ns'] for x in m2.committed],pending_nav_campaign_pass=pending_pass,terminal_fail_campaign_pass=failed_pass,nav_success_campaign_pass=success_pass)

# Additional design cases required for the review packet.
# A. Trigger precedes the first buffered TF; target later falls outside/behind buffer.
ident=Identity(3,2,7,'a'*64); t_trigger=40_000_000_000
m=FixedTimestampModel(steady_ns:=100); assert m.trigger_phase_a(t_trigger,ident)
tf_evicted=FakeTF(lower=t_trigger+20_000_000,upper=t_trigger+100_000_000)
first=m.poll_phase_a(t_trigger,1,tf_evicted); second=m.poll_phase_a(t_trigger+30_000_000,2,tf_evicted)
record('trigger_before_first_tf_and_target_evicted',None,{'first':first,'second':second,'query_stamps':m.phase_a_poll_stamps,'deadline':m.poll_phase_a(t_trigger+50_000_000,steady_ns,tf_evicted)},target_stamp_ns=t_trigger)

# Re-arming a pending exact-time poll never changes the query or resends an action.
m=FixedTimestampModel(10**12); m.trigger_phase_a(50_000_000_000,ident); tf_late=FakeTF(upper=49_000_000_000)
states=[m.poll_phase_a(50_000_000_000+i*10_000_000, i+1, tf_late) for i in range(2)]
assert m.rearm_phase_a_query()  # poll re-arm preserves the pinned target
states.append(m.poll_phase_a(50_020_000_000,3,FakeTF(upper=50_000_000_000)))
record('phase_a_query_rearm_does_not_retry_action',None,states,query_stamps=m.phase_a_poll_stamps,planner_request_count=m.planner_request_count)

# Receipt can be newer than odom and vector cutoff only if it is still <= cutoff.
base=60_000_000_000; ss=snapshot(11,base,odom_stamp=base-20_000_000,receipt_stamp=base-10_000_000)
m=FixedTimestampModel(10**12); cap=m.capture_sample(ss,base,1,ss.identity); tf_ok=FakeTF(upper=base)
state=m.poll_sample(base+1_000_000,2,tf_ok,ss.identity)
record('receipt_newer_than_odom_but_not_after_vector_cutoff',None,state,captured=cap,t_vector_ns=base,t_odom_ns=ss.odom_stamp_ns,t_receipt_ns=ss.receipt_stamp_ns,committed=len(m.committed)==1)

# Fresh at acquisition, stale by commit: exact old snapshot is discarded, never replaced.
base=70_000_000_000; ss=snapshot(12,base); m=FixedTimestampModel(10**12); captured=m.capture_sample(ss,base,1,ss.identity)
state=m.poll_sample(base+250_000_001,2,FakeTF(upper=base),ss.identity)
record('fresh_at_acquisition_stale_at_commit',None,state,captured=captured,committed=len(m.committed),discards=m.discards)

# Path identity/version is pinned. Replan version change invalidates pending sample.
base=80_000_000_000; ss=snapshot(13,base,path_version=4); m=FixedTimestampModel(10**12); m.capture_sample(ss,base,1,ss.identity)
state=m.poll_sample(base+1,2,FakeTF(upper=base),ss.identity,active_path_version=5)
record('path_version_changes_while_waiting',None,state,pinned_path_version=4,active_path_version=5,committed=len(m.committed))

# Barrier revision is monotonic; a change and restoration of values still changes revision.
base=90_000_000_000; ss=snapshot(14,base,barrier_revision=8); m=FixedTimestampModel(10**12); m.capture_sample(ss,base,1,ss.identity)
barrier_values_restored=True; state=m.poll_sample(base+1,2,FakeTF(upper=base),ss.identity,active_barrier_revision=10)
record('barrier_changed_then_values_returned',None,state,values_look_equal=barrier_values_restored,pinned_revision=8,current_revision=10,committed=len(m.committed))

# Non-mutating transform request: production helper changes the copied pose only.
source_path=make_path(); source_path.poses[1].header.stamp.sec=2; source_before=copy.deepcopy(source_path)
production._features_from_path(copy.deepcopy(source_path),FakeTF(upper=4_000_000_000),3_000_000_004)
record('transform_request_does_not_mutate_raw_path',{'unchanged':source_path==source_before},{'unchanged':source_path==source_before},production_helper_used=True)

# Timer polling returns without blocking, allowing action callback completion.
base=100_000_000_000; ss=snapshot(15,base); m=FixedTimestampModel(10**12); m.capture_sample(ss,base,1,ss.identity)
waiting=m.poll_sample(base+1,2,FakeTF(upper=base-1),ss.identity); m.action_callback('navigate','SUCCEEDED')
after_callback=m.poll_sample(base+2,3,FakeTF(upper=base),ss.identity)
record('callbacks_progress_while_nonblocking_tf_wait',None,{'first_poll':waiting,'callback_count':m.action_callbacks,'navigate':m.nav,'next_poll':after_callback})

# Recheck identity after arrival: future/past/missing connectivity fail without commit.
for label,lo,hi,connected in [('tf_future',0,base-1,True),('tf_past',base+1,base+10,True),('tf_missing_connectivity',0,base+10,False)]:
    ss=snapshot(16,base); m=FixedTimestampModel(10**12); m.capture_sample(ss,base,1,ss.identity)
    state=m.poll_sample(base+1,2,FakeTF(lo,hi,connected),ss.identity)
    record(label,None,state,committed=len(m.committed),failure_is_fail_closed=len(m.committed)==0)

# Stable explicit assertions for the proposal matrix.
assert all(not x['planner_requested'] for x in base_counts)
assert model is not None
assert results[0]['proposed'][-1]['state']=='PHASE_A_READY'
assert 'COMMITTED' in next(x for x in results if x['case']=='phase_b_tf_arrives_after_selection_but_data_fresh')['proposed'] and next(x for x in results if x['case']=='phase_b_tf_arrives_after_selection_but_data_fresh')['committed'][0]['tf_stamp_ns']==10_000_000_000
assert next(x for x in results if x['case']=='tf_never_arrives')['proposed'][-1]=='FAIL_EXISTING_RUN_DEADLINE'
assert next(x for x in results if x['case']=='path_pose_input_immutability')['proposed']['input_mutated'] is False
assert next(x for x in results if x['case']=='tf_after_input_expiry')['proposed']=='DISCARDED_FRESHNESS'
assert next(x for x in results if x['case']=='receipt_odom_update_while_pending')['assert_pinned'] is True
assert next(x for x in results if x['case']=='action_callback_during_tf_wait')['callback_count']==1
assert next(x for x in results if x['case']=='trigger_before_first_tf_and_target_evicted')['proposed']['deadline']=='FAIL_EXISTING_RUN_DEADLINE'
assert next(x for x in results if x['case']=='phase_a_query_rearm_does_not_retry_action')['planner_request_count']==1
assert next(x for x in results if x['case']=='receipt_newer_than_odom_but_not_after_vector_cutoff')['committed'] is True
assert next(x for x in results if x['case']=='fresh_at_acquisition_stale_at_commit')['proposed']=='DISCARDED_FRESHNESS'
assert next(x for x in results if x['case']=='path_version_changes_while_waiting')['proposed']=='DISCARDED_PATH_VERSION'
assert next(x for x in results if x['case']=='barrier_changed_then_values_returned')['proposed']=='DISCARDED_BARRIER'
assert next(x for x in results if x['case']=='transform_request_does_not_mutate_raw_path')['proposed']['unchanged'] is True
assert next(x for x in results if x['case']=='callbacks_progress_while_nonblocking_tf_wait')['proposed']['callback_count']==1
assert all(next(x for x in results if x['case']==name)['failure_is_fail_closed'] for name in ('tf_future','tf_past','tf_missing_connectivity'))
five=next(x for x in results if x['case']=='five_monotonic_samples_and_navigation_gating')
assert five['sample_count']==5 and five['pending_nav_campaign_pass'] is False and five['terminal_fail_campaign_pass'] is False and five['nav_success_campaign_pass'] is True
out=Path(__file__).with_name('offline_validation_results.json')
out.write_text(json.dumps({'model':'PROPOSAL_ONLY_NOT_PRODUCTION','production_baseline':{'executed_separately':True,'methods':['source _Collector._tick()','source _features_from_path()'],'purpose':'fake-object baseline only; not a running ROS node'},'runtime_or_campaign':False,'freshness_limits_ns':FixedTimestampModel.LIMITS,'tf_wait_budget':'none added; all waits end at existing whole-run steady deadline','case_count':len(results),'cases':results},indent=2,sort_keys=True)+'\n')
print(json.dumps(results,indent=2)); print('RESULT_JSON',out)
