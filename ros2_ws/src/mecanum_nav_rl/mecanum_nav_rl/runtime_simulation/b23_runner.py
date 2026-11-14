"""Runner campaign B2.3, quyền runtime từ packet/guard do Owner cấp trước.

Import module không tạo ROS context hoặc tiến trình. Worker chỉ được khởi tạo
sau khi controller đã consume đúng packet và pin context của transient unit.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import time

MODULE = 'mecanum_nav_rl.runtime_simulation.b23_runner'
SERVICE_PROPERTIES = ('Type=exec','Restart=no','RemainAfterExit=yes','MemoryMax=5G',
    'OOMPolicy=stop','RuntimeMaxSec=180s','TimeoutStartSec=5s','TimeoutStopSec=2s',
    'KillMode=control-group','KillSignal=SIGTERM','SendSIGKILL=yes',
    'FinalKillSignal=SIGKILL','RuntimeRandomizedExtraSec=0')


class FinalPublicationView:
    """Đọc receipt của FinalTwistPublisher process riêng; không publish actuator."""
    def __init__(self, publisher_instance_id):
        if type(publisher_instance_id) is not int or publisher_instance_id <= 0:
            raise ValueError('actual final publisher boot identity required')
        self.publisher_instance_id = publisher_instance_id
        self.ingress = None

    @property
    def last_publication(self):
        from rclpy.serialization import deserialize_message
        from mecanum_nav_rl_interfaces.msg import FinalIssuedCommandReceipt
        if self.ingress is None or not self.ingress.receipts:
            return None
        sequence = self.ingress.receipts[-1].final_publish_sequence
        return deserialize_message(self.ingress._receipt_bytes[sequence], FinalIssuedCommandReceipt)


class TrainingWorkerIO:
    """ROS I/O của một worker sở hữu riêng context, nodes, executor và RPC."""

    def __init__(self, descriptor, document, asset_manifest, emit):
        import rclpy
        from rclpy.context import Context
        from rclpy.node import Node
        from rclpy.parameter import Parameter
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import LaserScan
        from mecanum_nav_rl_interfaces.msg import (
            SafetyLifecycleState, SimulationContactState, FinalIssuedCommandReceipt, SafetyState,
            LocalTrainingSafetyInput, CommandEnvelope,
        )
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from ros_gz_interfaces.srv import ControlWorld, SetEntityPose
        from std_srvs.srv import Trigger
        from mecanum_nav_rl.runtime_safety.safety_lifecycle_node import SafetyLifecycleNode
        from mecanum_nav_rl.runtime_safety.safety_supervisor_node import SafetySupervisorNode
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import LocalTrainingIngress
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendSessionIdentity, BackendControlSession
        from mecanum_nav_rl.runtime_simulation.local_training_ports import LocalTrainingBackendControlPort
        import secrets
        self.descriptor, self.document, self.asset = copy.deepcopy(descriptor), document, asset_manifest
        self.emit = emit
        self.now, self.pause = time.monotonic_ns, asyncio.sleep
        self.deadline_ns = descriptor['active_deadline_ns']
        self.context = Context()
        self.nodes, self.calls = [], []
        self.executor = None
        self.pump_task = None
        self.pump_error = None
        self.stop_requested = False
        self.abort_requested = None
        self.subscriptions = []
        self.expected_paused = True
        self.last_clock_ns, self.last_clock_advance_ns = 0, self.now()
        self._native_offset, self._native_partial = 0, b''
        self._native_input_watermark = 0
        try:
            rclpy.init(context=self.context)
            self.executor = SingleThreadedExecutor(context=self.context)
            base_params = [Parameter('use_sim_time', value=True)]
            mode_params = base_params + [Parameter('navigation_mode', value='LOCAL_TRAINING')]
            self.node = Node('b23_coordinator_ingress', context=self.context, parameter_overrides=base_params)
            self.nodes.append(self.node)
            self.policy_source_id, self.safe_stop_source_id = secrets.randbelow(2**63 - 1) + 1, secrets.randbelow(2**63 - 1) + 1
            if self.policy_source_id == self.safe_stop_source_id:
                raise RuntimeError('source nonce collision')
            self.final = FinalPublicationView(descriptor['final_publisher_instance_id'])
            self.life = SafetyLifecycleNode(context=self.context, parameter_overrides=mode_params)
            self.nodes.append(self.life)
            identity = BackendSessionIdentity(descriptor['session_id'], descriptor['config_hash'],
                descriptor['asset_manifest_sha256'], descriptor['coordinator_ingress_instance_id'], descriptor['backend_instance_id'])
            safety_context = dict(session_id=identity.session_id, config_hash=identity.config_hash,
                ingress_instance_id=identity.coordinator_ingress_instance_id, backend_instance_id=identity.backend_instance_id,
                policy_source_instance_id=self.policy_source_id, safe_stop_source_instance_id=self.safe_stop_source_id,
                profile=document['training']['local_training'], sensor=asset_manifest['sensor'],
                sim_estop_release_authorized=True)
            self.safety = SafetySupervisorNode(context=self.context, parameter_overrides=mode_params,
                local_training_context=safety_context, evidence_sink=emit)
            self.nodes.append(self.safety)
            self.safety.local_training.set_stream_enabled(False)
            reliable = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            backend_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=50,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
            receipt_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            sensor_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=5,
                reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
            self.safety_publisher = self.node.create_publisher(LocalTrainingSafetyInput,
                '/mecanum/local_training/safety_input', reliable)
            self.policy_publisher = self.node.create_publisher(CommandEnvelope, '/mecanum/cmd_policy', reliable)
            self.ingress = LocalTrainingIngress(identity, document['training']['local_training'],
                final_publisher_id=self.final.publisher_instance_id, policy_source_id=self.policy_source_id,
                safe_stop_source_id=self.safe_stop_source_id, safety_publish=self.safety_publisher.publish,
                emit=emit, now_ros_ns=self.ros_now)
            self.final.ingress = self.ingress
            for message, topic, callback, qos in (
                (Odometry, '/mecanum/internal/ground_truth/odom', self.ingress.on_ground_truth, backend_qos),
                (LaserScan, '/scan', self.ingress.on_scan, sensor_qos),
                (SafetyLifecycleState, '/mecanum/safety_lifecycle_state', self.ingress.bind_lifecycle, reliable),
                (SimulationContactState, '/mecanum/local_training/backend_state', self.ingress.on_backend, backend_qos),
                (FinalIssuedCommandReceipt, '/mecanum/final_issued_command', self.ingress.on_receipt, receipt_qos),
                (SafetyState, '/mecanum/safety_state', self.ingress.on_safety_state, reliable),
            ):
                self.subscriptions.append(self.node.create_subscription(message, topic,
                    self.observed_callback(message, topic, callback), qos, raw=True))
            self.safety.local_training.state_observer = lambda state: self.ingress.register_safety_publication(
                state, source_instance_id=self.safe_stop_source_id)
            self.control = BackendControlSession(LocalTrainingBackendControlPort.from_node(self.node), identity, emit=emit)
            self.control_world_type, self.pose_type, self.trigger_type = ControlWorld, SetEntityPose, Trigger
            self.world_client = self.node.create_client(ControlWorld, '/world/b2_training_arena/control')
            self.pose_client = self.node.create_client(SetEntityPose, '/world/b2_training_arena/set_pose')
            self.reset_client = self.node.create_client(Trigger, '/mecanum/safety/request_reset')
            self.rearm_client = self.node.create_client(Trigger, '/mecanum/safety/rearm')
            for node in self.nodes:
                self.executor.add_node(node)
            self.emit('WORKER_SOURCES', {'policy_source_instance_id': self.policy_source_id,
                'safe_stop_source_instance_id': self.safe_stop_source_id,
                'final_publisher_instance_id': self.final.publisher_instance_id,
                'coordinator_ingress_instance_id': identity.coordinator_ingress_instance_id,
                'backend_instance_id': identity.backend_instance_id})
        except BaseException:
            self.close_context()
            raise

    def observed_callback(self, message_type, topic, callback):
        """Giữ CDR do DDS trả trước decode/validator; không sửa payload nguồn."""
        from rclpy.serialization import deserialize_message
        def receive(raw, info):
            if not isinstance(raw,(bytes,bytearray,memoryview)):
                raise TypeError('raw subscription did not return serialized bytes')
            wire=bytes(raw)
            self.emit('INGRESS_WIRE_RECEIVED', {'topic':topic,
                'received_ns':self.now(), 'wire_cdr_hex':wire.hex(),
                'message_info':{key:value for key,value in info.items() if type(value) is int}})
            try:
                return callback(deserialize_message(wire,message_type))
            except BaseException as error:
                self.emit('INGRESS_CALLBACK_ERROR', {'topic':topic,'error':repr(error),
                    'wire_sha256':hashlib.sha256(wire).hexdigest(),'detected_ns':self.now()})
                raise
        return receive

    def ros_now(self):
        return self.node.get_clock().now().nanoseconds

    def start_pump(self):
        if self.pump_task is not None:
            raise RuntimeError('executor pump already started')
        self.pump_task = asyncio.create_task(self._pump(), name='b23-owned-ros-pump')

    async def _pump(self):
        try:
            while not self.stop_requested:
                for _ in range(16):
                    self.executor.spin_once(timeout_sec=0.)
                await self.pause(0.001)
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self.pump_error = error
            raise

    def check(self):
        if self.stop_requested or self.abort_requested is not None:
            raise RuntimeError('worker stop requested: ' + str(self.abort_requested))
        if self.pump_error is not None:
            raise RuntimeError('executor callback failed') from self.pump_error
        now, ros = self.now(), self.ros_now()
        if now >= self.deadline_ns:
            raise TimeoutError('B23 active deadline reached')
        if ros < self.last_clock_ns:
            raise RuntimeError('ROS clock rolled backward')
        if ros > self.last_clock_ns:
            self.last_clock_ns, self.last_clock_advance_ns = ros, now
        if not self.expected_paused and now - self.last_clock_advance_ns > 1_000_000_000:
            raise RuntimeError('unexpected clock stall exceeded 1 s')
        if self.ingress.fault:
            raise RuntimeError('ingress fault: ' + self.ingress.fault)
        if self.ingress.backend_state is not None and self.ingress.backend_state.fault_flags:
            raise RuntimeError('native fault flags=' + str(self.ingress.backend_state.fault_flags))

    async def until(self, predicate, *, deadline_ns, phase):
        deadline_ns = min(deadline_ns, self.deadline_ns)
        while self.now() < deadline_ns:
            self.check()
            value = predicate()
            if value:
                if self.now() >= deadline_ns:
                    raise TimeoutError(phase + ': observation completed late')
                return value
            before = self.now()
            duration = min(0.002, max(0., (deadline_ns - before) / 1e9))
            if duration > 0:
                await self.pause(duration)
                if self.now() <= before:
                    raise RuntimeError('worker pause did not advance monotonic clock')
        raise TimeoutError(phase + ': deadline expired')

    async def call(self, client, request, *, timeout_s, phase):
        from rclpy.serialization import serialize_message
        started = self.now()
        deadline = min(self.deadline_ns, started + int(timeout_s * 1e9))
        await self.until(client.service_is_ready, deadline_ns=deadline, phase=phase + ' service ready')
        if self.now() >= deadline:
            raise TimeoutError(phase + ': no remaining submit budget')
        self.emit('RPC_REQUEST', {'phase': phase, 'request_cdr_hex': serialize_message(request).hex(),
            'started_ns': started, 'deadline_ns': deadline})
        future = client.call_async(request)
        self.calls.append(future)
        try:
            await self.until(future.done, deadline_ns=deadline, phase=phase + ' ACK')
            response = future.result()
            self.emit('RPC_RESPONSE', {'phase': phase, 'response_cdr_hex': serialize_message(response).hex(),
                'received_ns': self.now(), 'deadline_ns': deadline})
            if self.now() >= deadline or type(response.success) is not bool or not response.success:
                raise RuntimeError(phase + ': late/negative actual ACK')
            return response
        finally:
            if not future.done():
                future.cancel()
            if future.done():
                self.calls.remove(future)

    async def control_world(self, *, world_name, pause, timeout_s):
        if world_name != 'b2_training_arena' or type(pause) is not bool:
            raise ValueError('world control target invalid')
        request = self.control_world_type.Request()
        request.world_control.pause = pause
        await self.call(self.world_client, request, timeout_s=timeout_s, phase='world_pause' if pause else 'world_resume')
        return True

    async def set_entity_pose(self, *, world_name, entity_name, target, timeout_s):
        from ros_gz_interfaces.msg import Entity
        if world_name != 'b2_training_arena' or entity_name != 'mecanum_b2':
            raise ValueError('only bound robot reset pose is allowed')
        request = self.pose_type.Request()
        request.entity.name, request.entity.type = entity_name, Entity.MODEL
        request.pose.position.x, request.pose.position.y, request.pose.position.z = target.x_m, target.y_m, target.z_m
        request.pose.orientation.w, request.pose.orientation.z = math.cos(target.yaw_rad / 2), math.sin(target.yaw_rad / 2)
        if not hasattr(self, 'pause_ack'):
            raise RuntimeError('robot pose request has no actual native pause ACK')
        self.ingress.begin_pose_mutation(self.pause_ack)
        await self.call(self.pose_client, request, timeout_s=timeout_s, phase='robot_set_pose')
        return True

    async def lifecycle_event(self, *, rearm, deadline_ns):
        old = self.ingress.lifecycle
        previous = old.sequence if old is not None else 0
        client = self.rearm_client if rearm else self.reset_client
        budget = min(1., (deadline_ns - self.now()) / 1e9)
        if budget <= 0:
            raise TimeoutError('lifecycle event has no remaining budget')
        await self.call(client, self.trigger_type.Request(), timeout_s=budget,
                        phase='lifecycle_rearm' if rearm else 'lifecycle_reset')
        state = await self.until(lambda: self.ingress.lifecycle if self.ingress.lifecycle is not None
            and self.ingress.lifecycle.sequence > previous else None, deadline_ns=deadline_ns, phase='lifecycle source event')
        if state.barrier_state != (state.BARRIER_READY if rearm else state.BARRIER_NON_READY):
            raise RuntimeError('actual lifecycle event did not reach requested barrier')
        return copy.deepcopy(state)

    async def pin_graph(self, *, deadline_ns):
        def endpoints():
            cmd = self.node.get_publishers_info_by_topic('/cmd_vel')
            safety = self.node.get_publishers_info_by_topic('/mecanum/safety_state')
            ingress = self.node.get_publishers_info_by_topic('/mecanum/local_training/safety_input')
            self.emit('GRAPH_OBSERVATION', {name: [{'node': item.node_name,
                'namespace': item.node_namespace, 'type': item.topic_type,
                'gid_hex': bytes(item.endpoint_gid).hex()} for item in values]
                for name, values in [('cmd_vel',cmd),('safety',safety),('ingress',ingress)]})
            if not (len(cmd) == len(safety) == len(ingress) == 1):
                return None
            # RMW DDS 3.1.1 trả sentinel khi endpoint đã thấy nhưng node chưa discovery.
            # Chưa đủ ownership: đợi trong cùng deadline, không bind hoặc đổi ngưỡng.
            if any(item.node_name == '_NODE_NAME_UNKNOWN_' or
                    item.node_namespace == '_NODE_NAMESPACE_UNKNOWN_'
                    for item in (cmd[0],safety[0],ingress[0])):
                return None
            if (cmd[0].node_name != 'final_twist_publisher' or safety[0].node_name != 'safety_supervisor'
                    or ingress[0].node_name != 'b23_coordinator_ingress'):
                raise RuntimeError('unexpected graph publisher ownership')
            return cmd, safety, ingress
        cmd, safety, ingress = await self.until(endpoints, deadline_ns=deadline_ns, phase='source graph binding')
        self.ingress.bind_safety_publisher_gid(safety[0].endpoint_gid)
        self.emit('GRAPH_BOUND', {name: [{'node': item.node_name, 'namespace': item.node_namespace,
                'type': item.topic_type, 'gid_hex': bytes(item.endpoint_gid).hex()} for item in values]
            for name, values in [('cmd_vel', cmd), ('safety', safety), ('ingress', ingress)]})

    async def paused_state(self, paused, timeout):
        status = await self.until(lambda: self.ingress.backend_state if self.ingress.backend_state is not None
            and self.ingress.backend_state.paused is paused else None,
            deadline_ns=self.now() + int(timeout * 1e9), phase='paused' if paused else 'resumed')
        self.expected_paused = paused
        if not paused:
            self.last_clock_advance_ns = self.now()
        self.emit('PAUSE_STATE_OBSERVED', {'paused': paused, 'status_sequence': status.status_sequence,
            'iteration': status.physics_iteration, 'steady_ns': self.now()})
        return True

    def read_native_input_watermark(self):
        path = Path(self.descriptor['native_events_path'])
        if not path.exists():
            return self._native_input_watermark
        with path.open('rb') as stream:
            stream.seek(self._native_offset)
            raw = self._native_partial + stream.read(1_048_576)
            self._native_offset = stream.tell()
        lines = raw.split(b'\n'); self._native_partial = lines.pop()
        for line in lines:
            record = json.loads(line)
            if record['kind'] not in ('B23_SAFETY_INPUT_OBSERVED', 'B23_ADMISSION_ACCEPTED'):
                continue
            fields = record['fields']
            if (fields['session'] != self.descriptor['session_id']
                    or int(fields['backend']) != self.descriptor['backend_instance_id']
                    or int(fields['ingress']) != self.descriptor['coordinator_ingress_instance_id']
                    or record['server_leader_pid'] != self.descriptor['server_leader_pid']
                    or record['invocation_id'] != self.descriptor['invocation_id']):
                raise RuntimeError('native input evidence ownership mismatch')
            self._native_input_watermark = max(self._native_input_watermark, int(fields['sample']))
        return self._native_input_watermark

    async def freeze_admission(self, *, deadline_ns):
        self.ingress.pause_admission_publication()
        target = self.ingress.last_published_sample_sequence
        if target:
            await self.until(lambda: self.read_native_input_watermark() >= target,
                             deadline_ns=deadline_ns, phase='native safety-input drain')
        self.emit('ADMISSION_STREAM_FROZEN', {'last_sample_sequence': target, 'steady_ns': self.now()})

    async def freeze_zero(self, *, deadline_ns):
        from mecanum_nav_rl.simulation.local_training_reset import AppliedZeroReceiptFact
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        adapter = self.safety.local_training
        adapter.set_policy_hold(True)
        initial_unarmed = (self.ingress.lifecycle is not None
            and self.ingress.lifecycle.episode_generation == 0 and not self.ingress._noise_ready
            and self.ingress.observation0_ack is None and self.ingress.last_published_sample_sequence == 0)
        sample_before = self.ingress.last_published_sample_sequence
        if not initial_unarmed:
            self.ingress.inhibit()
            await self.until(lambda: self.ingress.last_published_sample_sequence > sample_before
                and self.ingress.last_published_admission_state == 0,
                deadline_ns=deadline_ns, phase='closing admission publication')
        # Đợi ít nhất một tick SAFE_STOP trước khi khóa stream.
        previous = adapter.safe_stop_sequence
        await self.until(lambda: adapter.safe_stop_sequence > previous, deadline_ns=deadline_ns, phase='SAFE_STOP tick')
        await self.freeze_admission(deadline_ns=deadline_ns)
        adapter.set_stream_enabled(False)
        target = adapter.safe_stop_sequence
        receipt = await self.until(lambda: self.final.last_publication if self.final.last_publication is not None
            and self.final.last_publication.source == self.final.last_publication.SOURCE_SAFE_STOP
            and self.final.last_publication.sequence == target else None,
            deadline_ns=deadline_ns, phase='final SAFE_STOP drain')
        def applied():
            for pair in reversed(self.ingress.physics_pairs):
                from rclpy.serialization import deserialize_message
                from mecanum_nav_rl_interfaces.msg import SimulationContactState
                state = deserialize_message(pair.backend_bytes, SimulationContactState)
                if (state.applied_receipt_valid and not state.local_zero_override
                        and state.applied_final_publisher_instance_id == receipt.final_publisher_instance_id
                        and state.applied_final_publish_sequence == receipt.final_publish_sequence):
                    return pair, state
            return None
        pair, state = await self.until(applied, deadline_ns=deadline_ns, phase='native applied SAFE_STOP')
        identity = self.ingress.lifecycle
        fact = AppliedZeroReceiptFact(self.descriptor['session_id'], self.descriptor['config_hash'],
            self.descriptor['backend_instance_id'], receipt.episode_generation, receipt.reset_epoch,
            receipt.runtime_generation, receipt.final_publisher_instance_id, receipt.final_publish_sequence,
            receipt.source, receipt.source_instance_id, receipt.sequence, receipt.step_index, receipt.transition_id,
            (receipt.final_command.linear.x, receipt.final_command.linear.y, receipt.final_command.linear.z,
             receipt.final_command.angular.x, receipt.final_command.angular.y, receipt.final_command.angular.z),
            stamp_ns(identity.barrier_stamp), stamp_ns(receipt.header.stamp), state.applied_receipt_valid,
            state.applied_final_publisher_instance_id, state.applied_final_publish_sequence,
            state.applied_physics_iteration, stamp_ns(state.applied_sim_stamp), state.local_zero_override,
            pair.backend_received_steady_ns)
        self.emit('ZERO_STREAM_FROZEN', {'publish_sequence': fact.final_publish_sequence,
            'safe_stop_sequence': fact.source_sequence, 'application_iteration': fact.applied_physics_iteration,
            'application_stamp_ns': fact.applied_sim_stamp_ns, 'application_received_ns': fact.receive_steady_ns,
            'steady_ns': self.now()})
        return fact

    async def stop(self, *, deadline_ns):
        """Đóng ingress trước khi hủy RPC/pump; không nhận cancel là ACK native."""
        errors = []
        self.safety.local_training.set_policy_hold(True)
        self.ingress.inhibit()
        self.ingress.pause_admission_publication()
        self.safety.local_training.set_stream_enabled(False)
        for subscription in self.subscriptions:
            self.node.destroy_subscription(subscription)
        self.subscriptions.clear()
        if self.pump_task is not None and self.pump_task.done():
            try:
                self.pump_task.result()
            except BaseException as error:
                errors.append('original_pump_error:' + repr(error))
            # Chỉ còn RPC callbacks; thu ACK thực trước khi đóng executor.
            self.pump_task = asyncio.create_task(self._pump(), name='b23-owned-cleanup-rpc-pump')
        try:
            await self.control.inhibit(deadline_ns=min(deadline_ns, self.now() + 1_000_000_000))
        except BaseException as error:
            errors.append('inhibit:' + repr(error))
        self.safety.local_training.set_stream_enabled(False)
        self.ingress.pause_admission_publication()
        self.control.cancel_pending_calls()
        for future in self.calls:
            if not future.done(): future.cancel()
        self.stop_requested = True
        if self.pump_task is not None:
            self.pump_task.cancel()
            try:
                await asyncio.wait_for(self.pump_task, timeout=max(0., (deadline_ns - self.now()) / 1e9))
            except asyncio.CancelledError:
                pass
            except BaseException as error:
                errors.append('pump_join:' + repr(error))
        errors.extend(self.close_context())
        if self.now() > deadline_ns:
            errors.append('worker_cleanup_deadline_exceeded')
        self.emit('WORKER_CLEANUP', {'errors': errors, 'owned_calls_pending': len(self.control.owned_calls),
            'rpc_pending': sum(not call.done() for call in self.calls),
            'pump_joined': self.pump_task is None or self.pump_task.done(), 'steady_ns': self.now()})
        self.cleanup_errors = tuple(errors)
        return not errors

    def close_context(self):
        errors = []
        for node in reversed(self.nodes):
            try:
                if self.executor is not None: self.executor.remove_node(node)
                node.destroy_node()
            except BaseException as error:
                errors.append(repr(error))
        self.nodes.clear()
        if self.executor is not None:
            try:
                if not self.executor.shutdown(timeout_sec=0.):
                    errors.append('executor_shutdown_not_joined')
            except BaseException as error: errors.append(repr(error))
        try:
            if self.context.ok(): self.context.shutdown()
        except BaseException as error:
            errors.append(repr(error))
        if errors:
            self.emit('ROS_CONTEXT_CLEANUP_ERRORS', {'errors': errors})
        return errors

    async def startup(self):
        from rclpy.lifecycle import TransitionCallbackReturn
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields
        if (self.life.trigger_configure() != TransitionCallbackReturn.SUCCESS
                or self.life.trigger_activate() != TransitionCallbackReturn.SUCCESS):
            raise RuntimeError('actual lifecycle configure/activate failed')
        await self.pin_graph(deadline_ns=min(self.deadline_ns, self.now() + 5_000_000_000))
        await self.control_world(world_name='b2_training_arena', pause=False, timeout_s=1.)
        await self.paused_state(False, 2.)
        await self.until(lambda: self.ros_now() > 0, deadline_ns=self.now() + 2_000_000_000, phase='advancing startup clock')
        life = await self.lifecycle_event(rearm=True, deadline_ns=self.now() + 1_000_000_000)
        ack = await self.control.transact(Control.Request.OP_BIND_SESSION,
            deadline_ns=self.now() + 1_000_000_000, **lifecycle_request_fields(life),
            final_publisher_instance_id=self.final.publisher_instance_id,
            policy_source_instance_id=self.policy_source_id, safe_stop_source_instance_id=self.safe_stop_source_id,
            next_safe_stop_sequence=1)
        await self.bind_final_process(ack)
        self.emit('SESSION_BOUND', {'request_sequence': ack.request.request_sequence,
            'revision': ack.response.applied_binding_revision, 'steady_ns': self.now()})
        self.safety.local_training.set_stream_enabled(True)
        await self.contact_capability()

    async def contact_capability(self):
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        started, last = self.now(), None
        deadline = min(self.deadline_ns, started + 5_000_000_000)
        work_deadline = deadline - 1_000_000_000
        start_ack = await self.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
            deadline_ns=min(work_deadline, self.now() + 1_000_000_000),
            probe_action=Control.Request.PROBE_ACTION_START,
            **lifecycle_request_fields(self.ingress.lifecycle))
        reference = start_ack.request.request_sequence
        try:
            while self.now() < work_deadline:
                last = await self.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
                    deadline_ns=min(work_deadline, self.now() + 1_000_000_000),
                    probe_action=Control.Request.PROBE_ACTION_QUERY, probe_start_request_sequence=reference)
                proof = last.response
                if proof.contact_capability_state == proof.CAPABILITY_VERIFIED:
                    registry = ''.join(row['collision'] + ('|wheel\n' if row['wheel_floor_ignore'] else '|solid\n')
                        for row in sorted(self.asset['collision_registry']['tracked_collisions'], key=lambda row: row['collision']))
                    expected = dict(proof_session_id=self.descriptor['session_id'],
                        proof_backend_instance_id=self.descriptor['backend_instance_id'],
                        proof_config_hash=self.descriptor['config_hash'],
                        proof_asset_manifest_sha256=self.descriptor['asset_manifest_sha256'],
                        proof_world_name='b2_training_arena',
                        proof_collision_registry_sha256=hashlib.sha256(registry.encode()).hexdigest(),
                        proof_physics_engine_fingerprint_sha256=self.descriptor['physics_engine_sha256'])
                    for name, value in expected.items():
                        if getattr(proof, name) != value:
                            raise RuntimeError('actual contact proof mismatch: ' + name)
                    if not proof.proof_gz_sim_version.startswith('8.') or not proof.proof_physics_engine_plugin:
                        raise RuntimeError('contact proof has no pinned engine provenance')
                    for name, value in dict(probe_model_scoped_name='b2_training_arena::b2_capability_probe',
                        probe_collision_scoped_name='b2_training_arena::b2_capability_probe::link::collision',
                        floor_collision_scoped_name='b2_training_arena::ground_plane::link::collision').items():
                        if getattr(proof, name) != value:
                            raise RuntimeError('contact proof exact entity name mismatch')
                    ids = (proof.probe_model_entity_id, proof.probe_collision_entity_id, proof.floor_collision_entity_id)
                    if any(value == 0 for value in ids) or len(set(ids)) != 3:
                        raise RuntimeError('contact proof entity IDs missing/aliased')
                    for prefix, count in [('contact', proof.contact_sample_count), ('empty', proof.covered_empty_sample_count)]:
                        first, final = getattr(proof, prefix + '_first_iteration'), getattr(proof, prefix + '_last_iteration')
                        if (count < 3 or first == 0 or final - first + 1 != count
                                or stamp_ns(getattr(proof, prefix + '_last_stamp')) - stamp_ns(getattr(proof, prefix + '_first_stamp')) < 20_000_000):
                            raise RuntimeError('contact proof sample coverage invalid')
                    if proof.empty_first_iteration <= proof.contact_last_iteration:
                        raise RuntimeError('contact separation ordering invalid')
                    self.emit('CONTACT_CAPABILITY_VERIFIED', {'request_cdr_hex': last.request_bytes.hex(),
                        'response_cdr_hex': last.response_bytes.hex(), 'started_ns': started,
                        'completed_ns': self.now(), 'deadline_ns': deadline})
                    self.contact_ack = last
                    return last
                if proof.contact_capability_state in (proof.CAPABILITY_FAILED, proof.CAPABILITY_INVALIDATED):
                    raise RuntimeError('native contact capability failed/invalidated')
                await self.pause(min(0.01, max(0., (work_deadline - self.now()) / 1e9)))
            raise TimeoutError('normal contact proof not verified before cleanup reserve')
        finally:
            if (last is None or last.response.contact_capability_state != Control.Response.CAPABILITY_VERIFIED):
                try:
                    await self.control.transact(Control.Request.OP_VERIFY_CONTACT_CAPABILITY,
                        deadline_ns=min(deadline, self.now() + 1_000_000_000),
                        probe_action=Control.Request.PROBE_ACTION_ABORT, probe_start_request_sequence=reference)
                except BaseException as error:
                    self.emit('CONTACT_ABORT_ERROR', {'error': repr(error), 'steady_ns': self.now()})

    def fresh_reset_scan(self, *, now_ros_ns, now_steady_ns, at_or_before_ns=None,
                         at_or_after_ns=None):
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        if self.ingress.lifecycle is None:
            return None
        barrier = max(stamp_ns(self.ingress.lifecycle.barrier_stamp), self.ingress.scan_reset_stamp_ns)
        for stamp, sample in reversed(list(self.ingress.scans.items())):
            if at_or_before_ns is not None and stamp > at_or_before_ns:
                continue
            if at_or_after_ns is not None and stamp < at_or_after_ns:
                continue
            if stamp <= barrier:
                continue
            try:
                validate_dual_clock_freshness(source_ros_ns=stamp, now_ros_ns=now_ros_ns,
                    receive_steady_ns=sample.received_steady_ns, now_steady_ns=now_steady_ns,
                    max_age_ns=self.ingress.profile['scan_max_age_ms'] * 1_000_000)
            except ValueError:
                continue
            return sample
        return None

    def scan_clearance(self, *, now_ros_ns, now_steady_ns):
        from sensor_msgs.msg import LaserScan
        from rclpy.serialization import deserialize_message
        from rclpy.time import Time
        from mecanum_nav_rl.simulation.local_training_io import validate_dual_clock_freshness
        saved = self.fresh_reset_scan(now_ros_ns=now_ros_ns, now_steady_ns=now_steady_ns)
        if saved is None:
            raise RuntimeError('reset has no fresh post-barrier scan for clearance')
        validate_dual_clock_freshness(source_ros_ns=saved.stamp_ns, now_ros_ns=now_ros_ns,
            receive_steady_ns=saved.received_steady_ns, now_steady_ns=now_steady_ns,
            max_age_ns=self.ingress.profile['scan_max_age_ms'] * 1_000_000)
        scan = deserialize_message(saved.message_bytes, LaserScan)
        transform = self.safety._tf_buffer.lookup_transform('base_link', 'lidar_frame', Time())
        t, q = transform.transform.translation, transform.transform.rotation
        expected = self.asset['sensor']['extrinsic_xyz_m']
        if (any(abs(a - b) > 1e-9 for a, b in zip((t.x, t.y, t.z), expected))
                or any(abs(value) > 1e-9 for value in (q.x, q.y, q.z)) or abs(abs(q.w) - 1.) > 1e-9):
            raise RuntimeError('reset scan transform differs from asset')
        points = ((t.x + (scan.range_max if value == math.inf else value) * math.cos(scan.angle_min + i * scan.angle_increment),
                   t.y + (scan.range_max if value == math.inf else value) * math.sin(scan.angle_min + i * scan.angle_increment))
                  for i, value in enumerate(scan.ranges))
        return min(math.hypot(x, y) for x, y in points) - self.ingress.profile['robot_bounding_radius_m']

    async def measurements(self, *, deadline_ns, after_iteration):
        from nav_msgs.msg import Odometry
        from rclpy.serialization import deserialize_message
        from mecanum_nav_rl_interfaces.msg import SimulationContactState
        from mecanum_nav_rl.simulation.local_training_reset import ResetMeasurement
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import quaternion_rpy
        last = after_iteration
        # Sau reset_noise, buffer scan rỗng; đợi mẫu thật trong deadline gốc.
        await self.until(lambda: self.fresh_reset_scan(now_ros_ns=self.ros_now(), now_steady_ns=self.now()),
            deadline_ns=deadline_ns, phase='fresh reset scan')
        while self.now() < deadline_ns:
            pair = await self.until(lambda: next((value for value in self.ingress.physics_pairs
                if value.iteration > last), None), deadline_ns=deadline_ns, phase='fresh reset physics pair')
            oracle = deserialize_message(pair.oracle_bytes, Odometry)
            status = deserialize_message(pair.backend_bytes, SimulationContactState)
            pose, twist = oracle.pose.pose, oracle.twist.twist
            roll, pitch, yaw = quaternion_rpy(pose.orientation)
            clearance = self.scan_clearance(now_ros_ns=self.ros_now(), now_steady_ns=self.now())
            sample = ResetMeasurement(pair.iteration, pair.stamp_ns, pose.position.x, pose.position.y,
                pose.position.z, roll, pitch, yaw, (twist.linear.x, twist.linear.y, twist.linear.z),
                (twist.angular.x, twist.angular.y, twist.angular.z),
                status.contact_source_healthy and status.coverage_complete
                    and status.required_collision_mask != 0 and status.required_collision_mask == status.observed_collision_mask,
                status.contact_active, clearance >= self.ingress.profile['reset_footprint_clearance_expansion_m'],
                status.session_id, status.config_hash, status.backend_instance_id, status.reset_epoch,
                pair.backend_received_steady_ns, status.episode_generation, status.runtime_generation,
                pair.oracle_received_steady_ns, pair.stamp_ns)
            last = pair.iteration
            self.emit('RESET_MEASUREMENT', {'iteration': sample.iteration, 'stamp_ns': sample.stamp_ns,
                'position_xyz': [sample.x_m, sample.y_m, sample.z_m], 'rpy': [roll, pitch, yaw],
                'linear_xyz': list(sample.linear_xyz_mps), 'angular_xyz': list(sample.angular_xyz_radps),
                'clearance_m': clearance, 'contact_healthy': sample.contact_healthy,
                'contact_active': sample.contact_active, 'backend_received_ns': sample.receive_steady_ns,
                'oracle_received_ns': sample.oracle_receive_steady_ns, 'steady_ns': self.now()})
            yield sample
        raise TimeoutError('reset measurement stream deadline expired')

    async def reset_episode(self, b1, *, seed, target, paused_hold_s=0.):
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        from mecanum_nav_rl.simulation.local_training_reset import LocalTrainingResetAdapter
        started = self.now()
        deadline = min(self.deadline_ns, started + 15_000_000_000)
        w0 = await self.freeze_zero(deadline_ns=min(deadline, started + 5_000_000_000))
        self.emit('RESET_W0', {'publish_sequence': w0.final_publish_sequence,
            'safe_stop_sequence': w0.source_sequence, 'steady_ns': self.now(), 'reset_deadline_ns': deadline})
        l1 = await self.lifecycle_event(rearm=False, deadline_ns=min(deadline, self.now() + 1_000_000_000))
        await self.control.transact(Control.Request.OP_BIND_RESET_CONTEXT,
            deadline_ns=min(deadline, self.now() + 1_000_000_000), **lifecycle_request_fields(l1),
            final_publisher_instance_id=self.final.publisher_instance_id, policy_source_instance_id=self.policy_source_id,
            safe_stop_source_instance_id=self.safe_stop_source_id,
            next_safe_stop_sequence=self.safety.local_training.safe_stop_sequence + 1)
        if not self.ingress._noise_ready:
            self.ingress.reset_noise(seed)
        self.ingress.inhibit()
        self.safety.local_training.set_stream_enabled(True)
        await self.until(lambda: self.ingress.physics_pairs and self.ingress.physics_pairs[-1],
                         deadline_ns=deadline, phase='L1 actual physics context')
        before = self.ingress.physics_pairs[-1].iteration
        async def native_pause(fact, timeout):
            budget_ms = min(100, max(0, (deadline - self.now()) // 1_000_000))
            if budget_ms == 0:
                raise TimeoutError('native pause enter has no remaining budget')
            pause_deadline = min(deadline, self.now() + int(timeout * 1e9))
            self.ingress.begin_pause_transition(final_sequence=fact.final_publish_sequence, deadline_ns=pause_deadline)
            self.expected_paused = True  # Chỉ sau khi bắt đầu giao dịch pause native.
            ack = await self.control.transact(Control.Request.OP_PREPARE_RESET_PAUSE,
                deadline_ns=pause_deadline,
                **lifecycle_request_fields(self.ingress.lifecycle),
                final_publisher_instance_id=self.final.publisher_instance_id,
                pause_fence_final_publish_sequence=fact.final_publish_sequence,
                pause_enter_budget_ms=int(budget_ms))
            self.ingress.confirm_pause_transition(ack)
            self.pause_ack = ack
            self.emit('NATIVE_PAUSE_CONFIRMED', {'request_cdr_hex': ack.request_bytes.hex(),
                'response_cdr_hex': ack.response_bytes.hex(), 'steady_ns': self.now()})
            return True
        async def w1():
            result = await self.freeze_zero(deadline_ns=min(deadline, self.now() + 1_000_000_000))
            self.emit('RESET_W1', {'publish_sequence': result.final_publish_sequence,
                'safe_stop_sequence': result.source_sequence, 'steady_ns': self.now()})
            return result
        adapter = LocalTrainingResetAdapter(self, self.paused_state,
            lambda: self.measurements(deadline_ns=deadline, after_iteration=(
                self.ingress.physics_pairs[-1].iteration if self.ingress.physics_pairs else 0)),
            expected_session_id=self.descriptor['session_id'], expected_config_hash=self.descriptor['config_hash'],
            expected_backend_instance_id=self.descriptor['backend_instance_id'],
            expected_reset_epoch=l1.reset_epoch, expected_episode_generation=l1.episode_generation,
            expected_runtime_generation=l1.runtime_generation, expected_final_publisher_instance_id=self.final.publisher_instance_id,
            expected_safe_stop_source_instance_id=self.safe_stop_source_id,
            expected_barrier_stamp_ns=stamp_ns(l1.barrier_stamp),
            monotonic=lambda: self.now() / 1e9, sleep=self.pause,
            oracle_max_age_ns=self.ingress.profile['oracle_max_age_ms'] * 1_000_000,
            now_ros_ns=self.ros_now, native_pause=native_pause)
        facts = await adapter.execute_async(target=target,
            measured_standstill=self.measurements(deadline_ns=deadline, after_iteration=before),
            applied_zero_receipt=w1, reset_emulator_and_buffers=lambda: self.ingress.reset_noise(seed),
            reset_deadline=deadline / 1e9, paused_hold_s=paused_hold_s,
            stop_deadline=min(deadline, started+5_000_000_000)/1e9,
            braking_start_stamp_ns=w0.applied_sim_stamp_ns)
        l2 = await self.lifecycle_event(rearm=True, deadline_ns=min(deadline, self.now() + 1_000_000_000))
        await self.control.transact(Control.Request.OP_BIND_RESET_CONTEXT,
            deadline_ns=min(deadline, self.now() + 1_000_000_000), **lifecycle_request_fields(l2),
            final_publisher_instance_id=self.final.publisher_instance_id, policy_source_instance_id=self.policy_source_id,
            safe_stop_source_instance_id=self.safe_stop_source_id,
            next_safe_stop_sequence=self.safety.local_training.safe_stop_sequence + 1)
        # Sau L2, phát và xác minh một zero SAFE_STOP mới để B1 dùng
        # receipt còn mới tại cutoff, thay vì W1 đã cũ qua pause/resume.
        b1.begin_reset()
        self.ingress.inhibit()
        self.safety.local_training.set_stream_enabled(True)
        observation0_zero = await self.freeze_zero(deadline_ns=deadline)
        self.emit('OBSERVATION0_ZERO_ANCHOR', {'publish_sequence': observation0_zero.final_publish_sequence,
            'application_stamp_ns': observation0_zero.applied_sim_stamp_ns,
            'application_iteration': observation0_zero.applied_physics_iteration, 'steady_ns': self.now()})
        # Giữ Safety stream chạy ở inhibit để refresh receipt SAFE_STOP trong
        # lúc chờ exact sensor join và CONFIRM; POLICY vẫn chưa được bind.
        self.safety.local_training.set_stream_enabled(True)
        observation, cutoff = await self.commit_and_confirm_observation0(
            b1, deadline_ns=deadline, zero_receipt=observation0_zero)
        self.emit('RESET_COMPLETE', {'seed': seed, 'observation0_cutoff_ns': cutoff,
            'W0': w0.final_publish_sequence, 'W1': facts.applied_zero_receipt.final_publish_sequence,
            'l1_sequence': l1.sequence, 'l2_sequence': l2.sequence,
            'started_ns': started, 'completed_ns': self.now(), 'deadline_ns': deadline})
        return observation

    async def commit_and_confirm_observation0(self, b1, *, deadline_ns, zero_receipt=None):
        """Commit B1, xác nhận backend và chỉ giao observation khi ACK hợp lệ."""
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import lifecycle_request_fields, B1SnapshotPending
        last_pending = None
        while self.now() < deadline_ns:
            self.check()
            scan = self.fresh_reset_scan(now_ros_ns=self.ros_now(), now_steady_ns=self.now(),
                at_or_after_ns=None if zero_receipt is None else zero_receipt.applied_sim_stamp_ns)
            for cutoff in ([scan.stamp_ns] if scan is not None else []):
                try:
                    observation, selection = b1.commit_observation0(cutoff)
                except B1SnapshotPending as error:
                    last_pending = str(error); continue
                ack = await self.control.transact(Control.Request.OP_CONFIRM_OBSERVATION0,
                    deadline_ns=min(deadline_ns, self.now() + 1_000_000_000),
                    **lifecycle_request_fields(self.ingress.lifecycle),
                    observation0_cutoff=self._time_msg(cutoff),
                    selected_zero_final_publisher_instance_id=self.final.publisher_instance_id,
                    selected_zero_final_publish_sequence=selection.receipt.final_publish_sequence,
                    adjacent_boundary_final_publisher_instance_id=self.final.publisher_instance_id,
                    adjacent_boundary_final_publish_sequence=selection.adjacent_receipt.final_publish_sequence)
                self.ingress.confirm_observation0(ack)
                return observation, cutoff
            await self.pause(min(0.002, max(0., (deadline_ns - self.now()) / 1e9)))
        raise TimeoutError('observation0 did not confirm within reset deadline: ' + str(last_pending))

    @staticmethod
    def _time_msg(ns):
        from builtin_interfaces.msg import Time
        return Time(sec=ns // 10**9, nanosec=ns % 10**9)

    async def bind_final_process(self, ack):
        """Chuyển ACK gốc sang child đã pin boot nonce; chờ xác nhận của child."""
        import os
        record = {'schema': 'b23_final_source_binding/v1', 'run_id': self.descriptor['run_id'],
            'invocation_id': self.descriptor['invocation_id'],
            'final_publisher_instance_id': self.final.publisher_instance_id,
            'request_cdr_hex': ack.request_bytes.hex(), 'response_cdr_hex': ack.response_bytes.hex(),
            'ack_observed_ns': ack.observed_steady_ns}
        raw = json.dumps(record, sort_keys=True, separators=(',', ':')).encode() + b'\n'
        path = Path(self.descriptor['final_binding_path'])
        write_record_once(path, record)
        digest = hashlib.sha256(raw).hexdigest()
        result_path = Path(self.descriptor['final_binding_ack_path'])
        def observed():
            if not result_path.exists():
                return None
            result = json.loads(result_path.read_bytes())
            if (result.get('binding_file_sha256') != digest
                    or result.get('invocation_id') != self.descriptor['invocation_id']
                    or result.get('publisher_instance_id') != self.final.publisher_instance_id
                    or result.get('pid') != self.descriptor['final_publisher_pid']
                    or result.get('source_binding_applied') is not True):
                raise RuntimeError('final publisher binding ACK ownership mismatch')
            return result
        await self.until(observed, deadline_ns=min(self.deadline_ns, self.now() + 1_000_000_000),
                         phase='final source binding ACK')
        self.emit('FINAL_BINDING_CONFIRMED', {'binding_file_sha256': digest, 'steady_ns': self.now()})


    async def freeze_step_streams(self, *, deadline_ns):
        """Không xen SAFE_STOP giữa các step; chờ publication cũ rời hàng đợi.

        Timer bị khóa trước khi chờ. Receipt cũ cùng slot vẫn hợp lệ; một
        SAFE_STOP đã phát phải tới native trước khi mở pending slot mới.
        """
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope
        self.safety.local_training.set_stream_enabled(False)
        last = copy.deepcopy(self.safety.local_training.last_output)
        await self.freeze_admission(deadline_ns=deadline_ns)
        if last is None:
            raise RuntimeError('step has no actual Safety publication anchor')
        def drained():
            receipt = self.final.last_publication
            if (receipt is None or receipt.source != last.source
                    or receipt.source_instance_id != last.source_instance_id
                    or receipt.sequence < last.sequence):
                return None
            return receipt
        receipt = await self.until(drained, deadline_ns=deadline_ns, phase='Final publication drain')
        if last.source == CommandEnvelope.SOURCE_SAFE_STOP:
            await self.until(lambda: self.ingress.backend_state if self.ingress.backend_state is not None
                and self.ingress.backend_state.applied_final_publish_sequence == receipt.final_publish_sequence
                and self.ingress.backend_state.applied_final_publisher_instance_id == self.final.publisher_instance_id
                and not self.ingress.backend_state.local_zero_override else None,
                deadline_ns=deadline_ns, phase='SAFE_STOP application before pending step')
        self.emit('STEP_STREAMS_FROZEN', {'source': last.source, 'source_sequence': last.sequence,
            'publish_sequence': receipt.final_publish_sequence, 'steady_ns': self.now()})

    async def policy_step(self, b1, action):
        """Một issuance thật qua Safety, application thật rồi transaction B1."""
        from mecanum_nav_rl_interfaces.msg import CommandEnvelope, LocalTrainingSafetyInput
        from mecanum_nav_rl_interfaces.srv import LocalTrainingBackendControl as Control
        from mecanum_nav_rl.runtime_simulation.local_training_coordinator import B1SnapshotPending
        from mecanum_nav_rl.runtime_simulation.local_training_ingress import stamp_ns
        if (not isinstance(action, (tuple, list)) or len(action) != 3
                or any(type(v) not in (float, int) or not math.isfinite(v) or not -1 <= v <= 1 for v in action)):
            raise ValueError('action requires three finite normalized values in [-1, 1]')
        started = self.now()
        deadline = min(self.deadline_ns, started + 2_000_000_000)
        await self.freeze_step_streams(deadline_ns=deadline)
        token = b1.begin_step()
        barrier = self.ros_now()
        if barrier <= stamp_ns(self.ingress.lifecycle.barrier_stamp):
            raise RuntimeError('action barrier is not after authoritative lifecycle barrier')
        ack = await self.control.transact(Control.Request.OP_BIND_PENDING_STEP,
            deadline_ns=deadline, pending_step_index=token.step_index,
            pending_source_sequence=token.step_index, pending_transition_id=token.transition_id,
            action_barrier_stamp=self._time_msg(barrier))
        self.ingress.arm_pending(ack)
        await self.until(lambda: self.safety.local_training.noisy if self.safety.local_training.noisy is not None
            and self.safety.local_training.noisy.admission_state == LocalTrainingSafetyInput.ADMISSION_POLICY_OPEN
            and bytes(self.safety.local_training.noisy.admission_token) == bytes(ack.response.pending_admission_token)
            and self.ingress.last_published_sample_sequence == self.safety.local_training.noisy.sample_sequence
            else None, deadline_ns=deadline, phase='post-ACK admission delivered to Safety')
        life = self.ingress.lifecycle
        envelope = CommandEnvelope()
        envelope.header.frame_id, envelope.header.stamp = 'base_link', self._time_msg(self.ros_now())
        envelope.source, envelope.source_instance_id, envelope.sequence = (
            envelope.SOURCE_POLICY, self.policy_source_id, token.step_index)
        envelope.episode_generation, envelope.reset_epoch, envelope.runtime_generation = (
            life.episode_generation, life.reset_epoch, life.runtime_generation)
        scales = self.document['training']['local_training']
        envelope.twist.linear.x = float(action[0]) * scales['max_vx_mps']
        envelope.twist.linear.y = float(action[1]) * scales['max_vy_mps']
        envelope.twist.angular.z = float(action[2]) * scales['max_wz_radps']
        self.policy_publisher.publish(envelope)
        b1.record_issuance(envelope, action_barrier_ns=barrier)
        await self.until(lambda: self.safety.local_training.command if self.safety.local_training.command is not None
            and self.safety.local_training.command.sequence == token.step_index
            and self.safety.local_training.command.source_instance_id == self.policy_source_id else None,
            deadline_ns=deadline, phase='actual adapter issuance delivered to Safety')
        self.safety.local_training.set_policy_hold(False)
        self.safety.local_training.set_stream_enabled(True)
        target_cutoff = stamp_ns(envelope.header.stamp) + 100_000_000
        last_pending = None
        while self.now() < deadline:
            self.check()
            candidates = [stamp for stamp in self.ingress.scans if stamp >= target_cutoff]
            if candidates:
                cutoff = max(candidates)
                try:
                    transition = b1.commit_step(cutoff)
                except B1SnapshotPending as error:
                    last_pending = str(error)
                else:
                    if self.now() >= deadline:
                        self.emit('B1_STEP_COMMITTED_LATE', {'step_index':token.step_index,
                            'transition_id':token.transition_id,'observed_ns':self.now(),'deadline_ns':deadline})
                        raise TimeoutError('B1 commit completed after step deadline')
                    self.emit('POLICY_STEP_COMPLETE', {'step_index': token.step_index,
                        'transition_id': token.transition_id, 'started_ns': started,
                        'completed_ns': self.now(), 'deadline_ns': deadline, 'cutoff_ns': cutoff})
                    if self.now() >= deadline:
                        raise TimeoutError('completion evidence published after step deadline')
                    return transition
            await self.pause(min(0.002, max(0., (deadline - self.now()) / 1e9)))
        raise TimeoutError('POLICY step missing facts before deadline: ' + str(last_pending))



def evidence_json_value(value):
    """Giữ fields của DTO cleanup; không thay object thiếu bằng trạng thái sạch."""
    from dataclasses import is_dataclass, fields
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name:getattr(value, item.name) for item in fields(value)}
    if isinstance(value, Path):
        return str(value)
    raise TypeError('unsupported evidence value: ' + type(value).__name__)


def write_record_once(path, record):
    """Evidence bất biến: không ghi đè kể cả khi lần trước chưa hoàn tất."""
    import os
    raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False, default=evidence_json_value).encode() + b'\n'
    import tempfile
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.b23-publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path, follow_symlinks=False)  # Atomic, EEXIST không ghi đè.
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        os.unlink(temporary)  # Chỉ file tạm có nonce vừa được chính hàm tạo.
    return hashlib.sha256(raw).hexdigest()


def process_identity(pid):
    """Đọc bytes gốc cùng identity; lỗi đọc không được coi là PID vắng."""
    root = Path('/proc') / str(pid)
    raw = {name: (root/name).read_bytes() for name in ('stat', 'status', 'cmdline', 'cgroup')}
    fields = raw['stat'].rsplit(b')', 1)[1].split()
    uid = next(line.split()[1:] for line in raw['status'].splitlines() if line.startswith(b'Uid:'))
    return {'pid': pid, 'uid': int(uid[0]), 'state': fields[0].decode(),
        'ppid': int(fields[1]), 'pgid': int(fields[2]), 'sid': int(fields[3]),
        'start_ticks': int(fields[19]), 'argv': [v.decode() for v in raw['cmdline'].split(b'\0') if v],
        'raw_hex': {name: data.hex() for name, data in raw.items()}}


class RunEvidence:
    """Sổ riêng từng process, raw stdout native và bốn book không gộp số đếm."""
    BOOKS = frozenset(('policy_adapter_issued', 'policy_final_published',
                      'policy_backend_applied', 'b1_transition_committed'))

    def __init__(self, root, role, *, run_id, invocation_id):
        self.root, self.role, self.run_id, self.invocation_id = Path(root), role, run_id, invocation_id
        self.streams = {}
        self.errors = []
        self.closed = False

    def append(self, filename, record):
        if self.closed:
            raise RuntimeError('evidence sink already closed')
        if filename not in self.streams:
            self.streams[filename] = (self.root/filename).open('x', encoding='utf-8')
        raw = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False, default=evidence_json_value)
        self.streams[filename].write(raw + '\n')
        self.streams[filename].flush()

    def record(self, event, facts):
        record = {'event': event, 'facts': facts, 'run_id': self.run_id,
            'invocation_id': self.invocation_id, 'role': self.role,
            'collected_ns': time.monotonic_ns()}
        self.append(self.role + '-events.jsonl', record)
        if event in self.BOOKS:
            self.append(event + '.jsonl', record)
        if event == 'owned_process_output' and facts.get('process') == 'server':
            import re
            text = re.sub(r'\x1b\[[0-9;]*m', '', facts['text'])
            match = re.search(r'\b(B23_[A-Z_]+)\s+(.*)', text)
            if match:
                fields = dict(re.findall(r'(\w+)=([^\s]+)', match[2]))
                self.append('native-events.jsonl', {'kind': match[1], 'fields': fields,
                    'raw_record': record, 'server_leader_pid': facts['pid'],
                    'invocation_id': self.invocation_id, 'collected_ns': time.monotonic_ns()})

    async def cleanup_publisher(self, batch, deadline):
        """ACK chỉ sau batch đúng ID đã được ghi và các sổ đã flush/fsync."""
        from mecanum_nav_bringup.local_training_process_supervisor import CleanupEvidenceAck
        if time.monotonic() >= deadline:
            raise TimeoutError('cleanup publication budget expired before write')
        write_record_once(self.root/'cleanup-batch.json', {'batch_id': batch.batch_id, 'events': batch.events})
        self.sync()
        if time.monotonic() >= deadline:
            raise TimeoutError('cleanup publication completed after deadline')
        write_record_once(self.root/'cleanup-ack.json', {'batch_id': batch.batch_id,
            'acknowledged': True, 'run_id': self.run_id, 'invocation_id': self.invocation_id,
            'acknowledged_ns': time.monotonic_ns()})
        if time.monotonic() >= deadline:
            raise TimeoutError('cleanup ACK completed after deadline')
        return CleanupEvidenceAck(batch.batch_id, True)

    def sync(self):
        import os
        for stream in self.streams.values():
            stream.flush(); os.fsync(stream.fileno())

    def close(self):
        try:
            self.sync()
        finally:
            self.closed = True
            for stream in self.streams.values():
                stream.close()


def load_child_descriptor(path, role):
    """Child chỉ thuộc unit/parent/packet đã consume; không là CLI bypass guard."""
    import os
    raw = Path(path).resolve(strict=True).read_bytes()
    document = json.loads(raw)
    if (document.get('schema') != 'b23_owned_child/v1' or document.get('role') != role
            or document.get('invocation_id') != os.environ.get('INVOCATION_ID')
            or not document.get('invocation_id') or os.getuid() != 1000
            or document['parent_identity']['pid'] != os.getppid()):
        raise RuntimeError('child authority/profile/parent mismatch')
    current = process_identity(os.getppid())
    for key in ('pid', 'uid', 'start_ticks', 'argv'):
        if current[key] != document['parent_identity'][key]:
            raise RuntimeError('child parent identity changed: ' + key)
    packet_raw = Path(document['packet_path']).read_bytes()
    if hashlib.sha256(packet_raw).hexdigest() != document['packet_sha256']:
        raise RuntimeError('child packet bytes changed')
    packet = json.loads(packet_raw)
    if document.get('session_id') != packet.get('session_id'):
        raise RuntimeError('child session UUID does not match packet')
    consumed = json.loads(Path(packet['guard_path']).joinpath('consumed.json').read_bytes())
    if (consumed['run_id'] != document['run_id'] or consumed['packet_sha256'] != document['packet_sha256']
            or document['active_deadline_ns'] != consumed['active_deadline_ns']
            or document['total_deadline_ns'] != consumed['total_deadline_ns']
            or time.monotonic_ns() >= document['active_deadline_ns']
            or packet['unit'] not in Path('/proc/self/cgroup').read_text()):
        raise RuntimeError('child consumed guard/deadline/cgroup mismatch')
    return document, packet


def final_child(path):
    """Process Final riêng; boot không phát gì trước source binding APPLIED."""
    import os
    import signal
    import rclpy
    from rclpy.context import Context
    from rclpy.parameter import Parameter
    from rclpy.executors import SingleThreadedExecutor
    from mecanum_nav_rl.runtime_safety.final_twist_publisher_node import FinalTwistPublisherNode
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import BackendControlAck, BackendSessionIdentity
    descriptor, packet = load_child_descriptor(path, 'final')
    sink = RunEvidence(descriptor['run_root'], descriptor['evidence_role'],
        run_id=descriptor['run_id'], invocation_id=descriptor['invocation_id'])
    context = Context(); node = executor = None
    stop = False
    def stopping(_sig, _frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, stopping); signal.signal(signal.SIGINT, stopping)
    error = None
    try:
        rclpy.init(context=context)
        node = FinalTwistPublisherNode(context=context, parameter_overrides=[
            Parameter('use_sim_time', value=True), Parameter('navigation_mode', value='LOCAL_TRAINING'),
            Parameter('session_id', value=descriptor['session_id'])], evidence_sink=sink.record)
        executor = SingleThreadedExecutor(context=context); executor.add_node(node)
        write_record_once(descriptor['final_boot_path'], {'schema': 'b23_final_boot/v1',
            'run_id': descriptor['run_id'], 'invocation_id': descriptor['invocation_id'],
            'identity': process_identity(os.getpid()), 'publisher_instance_id': node.publisher_instance_id})
        applied = False
        active_cutoff = False
        while not stop and time.monotonic_ns() < descriptor['total_deadline_ns']:
            if not active_cutoff and time.monotonic_ns() >= descriptor['active_deadline_ns']:
                node._local_admitted = False
                active_cutoff = True
                sink.record('FINAL_ACTIVE_CUTOFF', {'steady_ns':time.monotonic_ns()})
            executor.spin_once(timeout_sec=0.002)
            binding_path = Path(descriptor['final_binding_path'])
            if not active_cutoff and not applied and binding_path.exists():
                raw = binding_path.read_bytes(); binding = json.loads(raw)
                if (binding['schema'] != 'b23_final_source_binding/v1'
                        or binding['run_id'] != descriptor['run_id']
                        or binding['invocation_id'] != descriptor['invocation_id']
                        or binding['final_publisher_instance_id'] != node.publisher_instance_id):
                    raise RuntimeError('final source binding file ownership mismatch')
                ack = BackendControlAck(bytes.fromhex(binding['request_cdr_hex']),
                    bytes.fromhex(binding['response_cdr_hex']), binding['ack_observed_ns'])
                req = ack.request
                identity = BackendSessionIdentity(descriptor['session_id'], packet['config_hash'],
                    packet['asset_manifest_sha256'], packet['coordinator_ingress_instance_id'], descriptor['backend_instance_id'])
                # Chờ DDS lifecycle/clock đến đúng context; không sửa ACK hoặc deadline.
                life = node._identity
                if life is None or node.get_clock().now().nanoseconds < ack.response.applied_sim_stamp.sec*10**9+ack.response.applied_sim_stamp.nanosec:
                    continue
                if (life.sequence, life.episode_generation, life.reset_epoch, life.runtime_generation) != (
                        req.lifecycle_sequence, req.episode_generation, req.reset_epoch, req.runtime_generation):
                    if life.sequence < req.lifecycle_sequence:
                        continue
                    raise RuntimeError('final source binding lifecycle changed')
                node.bind_backend_session(ack, identity)
                write_record_once(descriptor['final_binding_ack_path'], {'source_binding_applied': True,
                    'binding_file_sha256': hashlib.sha256(raw).hexdigest(),
                    'publisher_instance_id': node.publisher_instance_id, 'pid': os.getpid(),
                    'invocation_id': descriptor['invocation_id']})
                applied = True
        if not stop:
            raise TimeoutError('final publisher cleanup deadline expired')
    except BaseException as exc:
        error = repr(exc)
        sink.record('FINAL_CHILD_ERROR', {'error': error})
    finally:
        if executor is not None:
            executor.shutdown(timeout_sec=0.)
        if node is not None:
            node.destroy_node()
        if context.ok(): context.shutdown()
        sink.close()
    return 0 if error is None else 1


async def training_child(path):
    """Worker normal R01a; quyết định dùng facts từ đường production."""
    from rclpy.time import Time
    from mecanum_nav_rl.tasks.scenario_artifact import ScenarioArtifactLoader
    from mecanum_nav_rl.runtime_simulation.local_training_coordinator import LocalTrainingB1Adapter
    from mecanum_nav_rl.simulation.local_training_reset import ResetTarget
    descriptor, packet = load_child_descriptor(path, 'worker')
    sink = RunEvidence(descriptor['run_root'], 'worker', run_id=descriptor['run_id'],
        invocation_id=descriptor['invocation_id'])
    io = None
    primary, cleanup_errors, outcome = None, [], None
    try:
        document = json.loads(Path(packet['resolved_config']).read_bytes())
        asset = json.loads(Path(packet['asset_manifest']).read_bytes())
        io = TrainingWorkerIO(descriptor, document, asset, sink.record)
        loop = asyncio.get_running_loop()
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, setattr, io, 'abort_requested', sig.name)
        io.start_pump()
        await io.startup()
        artifact = ScenarioArtifactLoader(expected_gazebo_world_name=asset['world_id'],
            expected_world_file_sha256=asset['world_file_sha256']).load(Path(packet['scenario']).read_text())
        b1 = LocalTrainingB1Adapter(io.ingress, artifact, asset,
            scan_transform=lambda: io.safety._tf_buffer.lookup_transform('base_link', 'lidar_frame', Time()), emit=sink.record)
        if packet['case'] != 'R01a':
            raise RuntimeError('case not implemented by this worker; cannot launch other hooks')
        target = ResetTarget(**packet['reset_target'])
        await io.reset_episode(b1, seed=packet['episode_seeds'][0], target=target, paused_hold_s=.250)
        transition = await io.policy_step(b1, (0.4, 0., 0.))
        if transition.termination.terminated or transition.termination.truncated:
            raise RuntimeError('R01a first POLICY terminated before active reset')
        await io.reset_episode(b1, seed=packet['episode_seeds'][1], target=target, paused_hold_s=.250)
        outcome = {'case': 'R01a', 'resets_confirmed': 2, 'policy_steps_committed': 1,
            'completed_ns': time.monotonic_ns()}
        if outcome['completed_ns'] >= descriptor['active_deadline_ns']:
            raise TimeoutError('smoke completed after active deadline')
    except BaseException as exc:
        primary = repr(exc)
        sink.record('WORKER_PRIMARY_ERROR', {'error': primary})
    finally:
        cleanup_started = time.monotonic_ns()
        cleanup_deadline = min(descriptor['total_deadline_ns'], cleanup_started + 60_000_000_000)
        write_record_once(Path(descriptor['run_root'])/'worker-cleanup-start.json', {
            'run_id':descriptor['run_id'], 'invocation_id':descriptor['invocation_id'],
            'started_ns':cleanup_started, 'deadline_ns':cleanup_deadline})
        if io is not None:
            try:
                clean = await io.stop(deadline_ns=cleanup_deadline)
                cleanup_errors.extend(io.cleanup_errors)
                if not clean and not cleanup_errors:
                    cleanup_errors.append('worker_cleanup_not_clean')
            except BaseException as exc:
                cleanup_errors.append(repr(exc))
                cleanup_errors.extend(io.close_context())
        result = {'primary_error': primary, 'cleanup_errors': cleanup_errors, 'outcome': outcome,
            'cleanup_started_ns': cleanup_started, 'cleanup_deadline_ns': cleanup_deadline,
            'completed_ns': time.monotonic_ns(), 'run_id': descriptor['run_id'],
            'invocation_id': descriptor['invocation_id']}
        write_record_once(Path(descriptor['run_root'])/'worker-result.json', result)
        sink.close()
    return 0 if primary is None and not cleanup_errors and outcome is not None else 1


def verify_packet(path, expected_sha256):
    """Pin mọi input trước spawn; packet không tự cấp thêm phase/hook."""
    import os
    import sys
    import re
    import pwd
    from mecanum_nav_bringup.local_training_launch_contract import load_bound_config
    raw = Path(path).resolve(strict=True).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('packet digest mismatch')
    packet = json.loads(raw)
    import uuid
    try:
        if str(uuid.UUID(packet['session_id'])) != packet['session_id'] or packet['launch_plan']['session_id'] != packet['session_id']:
            raise ValueError('session mismatch')
    except (KeyError,ValueError,TypeError,AttributeError) as error:
        raise ValueError('packet requires matching canonical session UUID') from error
    prefix = Path(packet['install_prefix']).resolve(strict=True)
    if (packet['schema'] != 'b23_packet/v1' or packet['case'] != 'R01a'
            or packet['fault_hooks'] != [] or packet['gui'] is not False
            or packet.get('world_seed') != 20261029 or packet.get('episode_seeds') != [2026102900,2026102901]
            or packet['authority'] != 'OWNER_B23_CAMPAIGN_APPROVED'
            or (packet['active_s'], packet['cleanup_s']) != (120, 60)
            or not re.fullmatch(r'B23_[A-Z0-9_]+', packet['run_id'])
            or len(packet['run_id']) > 64
            or not re.fullmatch(r'b23-[a-z0-9-]+\.service', packet['unit'])
            or os.getuid() != 1000 or pwd.getpwuid(os.getuid()).pw_name != 'hazan'
            or sys.version_info[:3] != (3,12,3) or str(Path(sys.executable).absolute()) != packet['python']):
        raise ValueError('packet authority/profile/phase mismatch')
    import importlib
    for name in ('mecanum_nav_rl.runtime_simulation.b23_runner',
                 'mecanum_nav_rl.runtime_simulation.local_training_coordinator',
                 'mecanum_nav_rl.runtime_simulation.local_training_ingress',
                 'mecanum_nav_rl.runtime_safety.final_twist_publisher_node',
                 'mecanum_nav_bringup.local_training_process_supervisor',
                 'mecanum_nav_rl_interfaces.srv'):
        origin = Path(importlib.import_module(name).__file__).resolve(strict=True)
        if not origin.is_relative_to(prefix) or str(origin) not in packet['input_sha256']:
            raise ValueError('runtime import is outside pinned install: ' + str(origin))
    for filename, digest in packet['input_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise ValueError('runtime input bytes changed: ' + filename)
    document, config_hash, asset_hash, scenario_id = load_bound_config(Path(packet['resolved_config']))
    if (config_hash != packet['config_hash'] or asset_hash != packet['asset_manifest_sha256']
            or scenario_id != 'B2_SOAK_V1' or document['map_identity']['training_binding']['binding_status'] != 'BOUND'):
        raise ValueError('packet config/asset/scenario binding mismatch')
    root = Path(packet['run_root']).resolve(strict=True)
    canonical = Path('/home/hazan/mecanum_runtime_evidence').resolve(strict=True)
    if not root.is_relative_to(canonical) or root == canonical:
        raise ValueError('runtime evidence root outside canonical root')
    if Path(packet['guard_path']).parent != Path('/home/hazan/.local/state/ros2_nav2_drl/b23'):
        raise ValueError('guard outside campaign state root')
    if packet['launch_plan']['commands'] != [list(b23_server_argv(packet['launch_plan']['world_file']))]:
        raise ValueError('Gazebo server argv/seed do not match pinned R01a profile')
    if (packet.get('service_properties') != list(SERVICE_PROPERTIES)
            or packet.get('launch_argv_template') != service_launch_command(packet, str(root/'packet.json'), '{PACKET_SHA256}')):
        raise ValueError('packet launch argv/properties do not match source-reviewed template')
    return packet


async def run_parent(packet_path, packet_sha256):
    """Sở hữu tất cả launch qua supervisor đã audit; không override start()."""
    import os
    import sys
    import signal
    from mecanum_nav_bringup import local_training_process_supervisor as sp
    from mecanum_nav_bringup.local_training_launch_contract import LaunchPlan
    packet = verify_packet(packet_path, packet_sha256)
    invocation = os.environ.get('INVOCATION_ID', '')
    if (not invocation or packet['unit'] not in Path('/proc/self/cgroup').read_text()
            or len(invocation) != 32):
        raise RuntimeError('parent is not inside exact transient invocation')
    consumed = json.loads((Path(packet['guard_path'])/'consumed.json').read_bytes())
    if consumed['packet_sha256'] != packet_sha256 or consumed['run_id'] != packet['run_id']:
        raise RuntimeError('parent consumed guard mismatch')
    active_end, total_end = consumed['active_deadline_ns'], consumed['total_deadline_ns']
    root = Path(packet['run_root'])
    sink = RunEvidence(root, 'parent', run_id=packet['run_id'], invocation_id=invocation)
    identity = process_identity(os.getpid())
    write_record_once(root/'parent-identity.json', {'identity': identity,
        'packet_sha256': packet_sha256, 'invocation_id': invocation, 'run_id': packet['run_id'],
        'active_deadline_ns': active_end, 'total_deadline_ns': total_end})
    values = dict(packet['launch_plan'])
    for name in ('world_file', 'gui_config', 'resolved_config'):
        values[name] = Path(values[name])
    values['commands'] = tuple(tuple(command) for command in values['commands'])
    values['bridge_command'] = tuple(values['bridge_command'])
    plan = LaunchPlan(**values)
    supervisor = sp.LocalTrainingProcessSupervisor(plan=plan, launcher=sp.SubprocessProcessLauncher(),
        readiness=sp.RclpyReadiness(), evidence_sink=sink, heartbeat_diagnostics_enabled=True,
        heartbeat_trace_directory=root/'trace', cleanup_evidence_publisher=sink.cleanup_publisher)
    abort = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, abort.set)
    primary, clean, worker_exit = None, False, None
    startup_task = abort_task = None
    shared_cleanup_end = total_end
    cleanup_seen = False
    owned_identities = []
    async def wait_for(predicate, label):
        nonlocal shared_cleanup_end, cleanup_seen
        while time.monotonic_ns() < (shared_cleanup_end if cleanup_seen else active_end):
            marker = root/'worker-cleanup-start.json'
            if marker.exists():
                record = json.loads(marker.read_bytes())
                shared_cleanup_end = min(shared_cleanup_end, cleanup_window_deadline(record,
                    run_id=packet['run_id'], invocation=invocation, total_end=total_end, now_ns=time.monotonic_ns()))
                cleanup_seen = True
            if abort.is_set(): raise RuntimeError('parent cancellation requested')
            for process in supervisor.owned:
                if process.process.returncode is not None and process.name not in ('worker',):
                    raise RuntimeError('owned process exited: ' + process.name + '=' + str(process.process.returncode))
            observer = supervisor._heartbeat_observer_process
            if observer is not None and observer.returncode is not None:
                raise RuntimeError('owned heartbeat observer exited: ' + str(observer.returncode))
            if supervisor._heartbeat_trace_error is not None:
                raise RuntimeError('heartbeat trace error: ' + str(supervisor._heartbeat_trace_error))
            value = predicate()
            if value:
                if time.monotonic_ns() >= (shared_cleanup_end if cleanup_seen else active_end):
                    raise TimeoutError(label + ' observed late')
                return value
            await asyncio.sleep(min(.01, max(0., ((shared_cleanup_end if cleanup_seen else active_end)-time.monotonic_ns())/1e9)))
        raise TimeoutError(label + ' exceeded active deadline')
    async def launch(role, command):
        record = await supervisor._launch_owned_process(role, tuple(command), dict(plan.environment))
        observed = process_identity(record.pid)
        owned_identities.append(observed)
        sink.record('OWNED_IDENTITY', {'role': role, 'identity': observed, 'command': list(command)})
        return record
    descriptor_base = dict(schema='b23_owned_child/v1', run_id=packet['run_id'], session_id=packet['session_id'],
        packet_path=str(Path(packet_path).resolve()), packet_sha256=packet_sha256,
        invocation_id=invocation, run_root=str(root), parent_identity=identity,
        active_deadline_ns=active_end, total_deadline_ns=total_end,
        coordinator_ingress_instance_id=packet['coordinator_ingress_instance_id'],
        config_hash=packet['config_hash'], asset_manifest_sha256=packet['asset_manifest_sha256'],
        native_events_path=str(root/'native-events.jsonl'))
    try:
        if time.monotonic_ns() >= active_end:
            raise TimeoutError('active deadline expired before supervisor start')
        startup_task = asyncio.create_task(supervisor.start(), name='b23-owned-supervisor-start')
        abort_task = asyncio.create_task(abort.wait(), name='b23-owned-start-abort')
        done, _ = await asyncio.wait((startup_task, abort_task),
            timeout=max(0., (active_end-time.monotonic_ns())/1e9), return_when=asyncio.FIRST_COMPLETED)
        if abort_task in done:
            raise RuntimeError('parent cancellation requested during startup')
        if startup_task not in done:
            raise TimeoutError('supervisor startup exceeded active deadline')
        await startup_task
        abort_task.cancel()
        try: await abort_task
        except asyncio.CancelledError: pass
        status = supervisor.readiness.accepted_backend_status
        backend_id = status['backend_instance_id']
        server = next(row for row in supervisor.owned if row.name == 'server')
        descriptor_base.update(backend_instance_id=backend_id, server_leader_pid=server.pid,
            physics_engine_sha256=packet['physics_engine_sha256'])
        await launch('robot_state_publisher', packet['robot_state_publisher_argv'])
        final_descriptor = dict(descriptor_base, role='final', evidence_role='final',
            final_boot_path=str(root/'final-boot.json'), final_binding_path=str(root/'final-binding.json'),
            final_binding_ack_path=str(root/'final-binding-ack.json'))
        write_record_once(root/'final-descriptor.json', final_descriptor)
        final = await launch('final', [sys.executable, '-B', '-m', MODULE, 'final',
            '--descriptor', str(root/'final-descriptor.json')])
        def booted():
            path = root/'final-boot.json'
            if not path.exists(): return None
            record = json.loads(path.read_bytes())
            if (record['run_id'] != packet['run_id'] or record['invocation_id'] != invocation
                    or record['identity'] != process_identity(final.pid) or record['publisher_instance_id'] <= 0):
                # /proc state có thể thay đổi; đối chiếu identity bất biến bên dưới.
                current = process_identity(final.pid)
                if (record['run_id'] != packet['run_id'] or record['invocation_id'] != invocation
                        or any(record['identity'][key] != current[key] for key in ('pid','uid','start_ticks','argv','pgid','sid'))
                        or record['publisher_instance_id'] <= 0):
                    raise RuntimeError('final boot record ownership mismatch')
            return record
        boot = await wait_for(booted, 'final actual boot')
        worker_descriptor = dict(descriptor_base, role='worker',
            final_publisher_instance_id=boot['publisher_instance_id'], final_publisher_pid=final.pid,
            final_binding_path=str(root/'final-binding.json'), final_binding_ack_path=str(root/'final-binding-ack.json'))
        write_record_once(root/'worker-descriptor.json', worker_descriptor)
        worker = await launch('worker', [sys.executable, '-B', '-m', MODULE, 'worker',
            '--descriptor', str(root/'worker-descriptor.json')])
        await wait_for(lambda: worker.process.returncode is not None, 'worker terminal')
        worker_exit = await worker.process.wait()
        outcome = json.loads((root/'worker-result.json').read_bytes())
        if (worker_exit != 0 or outcome['primary_error'] is not None or outcome['cleanup_errors']
                or outcome['outcome'] is None or outcome['run_id'] != packet['run_id']
                or outcome['invocation_id'] != invocation or outcome['outcome']['completed_ns'] >= active_end):
            raise RuntimeError('worker did not complete cleanly: ' + repr(outcome))
    except BaseException as error:
        primary = repr(error)
        sink.record('PARENT_PRIMARY_ERROR', {'error': primary})
    finally:
        started = time.monotonic_ns()
        marker = root/'worker-cleanup-start.json'
        if marker.exists():
            try:
                shared_cleanup_end = min(shared_cleanup_end, cleanup_window_deadline(
                    json.loads(marker.read_bytes()), run_id=packet['run_id'], invocation=invocation,
                    total_end=total_end, now_ns=started))
            except BaseException as error:
                sink.record('CLEANUP_WINDOW_BINDING_ERROR', {'error':repr(error)})
                shared_cleanup_end = min(shared_cleanup_end, started)
        deadline = min(total_end, shared_cleanup_end, started + 60_000_000_000)
        try:
            clean = await supervisor.cleanup(deadline=deadline/1e9)
        except BaseException as error:
            sink.record('PARENT_CLEANUP_ERROR', {'error': repr(error)})
        for task in (startup_task, abort_task):
            if task is not None:
                pending = not task.done()
                if pending: task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=max(0., (deadline-time.monotonic_ns())/1e9))
                except asyncio.CancelledError:
                    pass
                except BaseException as error:
                    sink.record('PARENT_TASK_FINALIZATION', {'task':task.get_name(), 'error':repr(error)})
                    if pending: clean = False
        cleanup = supervisor.cleanup_snapshot()
        result = {'run_id': packet['run_id'], 'invocation_id': invocation,
            'packet_sha256': packet_sha256, 'primary_error': primary, 'worker_exit': worker_exit,
            'cleanup_clean': clean, 'cleanup': cleanup, 'cleanup_started_ns': started,
            'cleanup_deadline_ns': deadline, 'completed_ns': time.monotonic_ns(),
            'owned_identities': owned_identities, 'containment_terminal_requires_external_readback': True}
        write_record_once(root/'parent-result.json', result)
        sink.close()
    return 0 if primary is None and clean and result['completed_ns'] <= total_end else 1




def cleanup_window_deadline(record, *, run_id, invocation, total_end, now_ns):
    """Một ngân sách 60 s cho worker và parent, không làm mới qua biên IPC."""
    if (record.get('run_id') != run_id or record.get('invocation_id') != invocation
            or type(record.get('started_ns')) is not int or type(record.get('deadline_ns')) is not int
            or not 0 <= record['started_ns'] <= now_ns
            or record['deadline_ns'] != min(total_end, record['started_ns'] + 60_000_000_000)):
        raise ValueError('worker cleanup deadline identity/budget invalid')
    return record['deadline_ns']


def launch_plan_record(plan):
    """Serialize plan bất biến mà không deepcopy MappingProxyType của env."""
    from dataclasses import fields
    return {item.name: (str(value) if isinstance(value, Path)
        else dict(value) if item.name == 'environment' else value)
        for item in fields(plan) for value in (getattr(plan, item.name),)}


def command_record(argv, *, timeout_s):
    """Lệnh quản trị có timeout và raw outcome; không sửa cấu hình khi lỗi."""
    import subprocess
    started = time.monotonic_ns()
    record = {'argv': list(argv), 'started_ns': started, 'timeout_s': timeout_s}
    if timeout_s <= 0:
        return dict(record, error='no_remaining_budget', returncode=None, stdout='', stderr='', completed_ns=time.monotonic_ns())
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout_s, check=False)
        record.update(returncode=result.returncode, stdout_hex=result.stdout.hex(), stderr_hex=result.stderr.hex(),
            stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace'), error=None)
    except subprocess.TimeoutExpired as error:
        record.update(returncode=None, stdout_hex=(error.stdout or b'').hex(), stderr_hex=(error.stderr or b'').hex(),
            stdout=(error.stdout or b'').decode(errors='replace'), stderr=(error.stderr or b'').decode(errors='replace'), error='timeout')
    record['completed_ns'] = time.monotonic_ns()
    return record


def prepare_packet(args):
    """Chuẩn bị R01a offline từ commit/install đã build và JUnit không lỗi."""
    import os
    import sys
    import secrets
    import uuid
    import xml.etree.ElementTree as ET
    from dataclasses import replace
    from mecanum_nav_bringup.local_training_launch_contract import build_launch_plan, write_bound_world, load_bound_config
    from mecanum_nav_bringup.local_training_process_supervisor import _physics_engine_plugin_path
    prefix, repo = Path(args.install).resolve(strict=True), Path(args.repo).resolve(strict=True)
    commit_record = command_record(['git', '-C', str(repo), 'rev-parse', 'HEAD'], timeout_s=5.)
    if commit_record['returncode'] != 0 or commit_record['stdout'].strip() != args.commit:
        raise ValueError('prepare source commit mismatch')
    branch = command_record(['git', '-C', str(repo), 'branch', '--show-current'], timeout_s=5.)
    dirty = command_record(['git', '-C', str(repo), 'status', '--porcelain'], timeout_s=5.)
    if (branch['returncode'] != 0 or branch['stdout'].strip() != 'roadmap-b-b23-local-training-integration'
            or dirty['returncode'] != 0 or dirty['stdout']):
        raise ValueError('runtime source worktree must be exact clean B23 candidate')
    build_binding_raw = Path(args.build_binding).resolve(strict=True).read_bytes()
    build_binding = json.loads(build_binding_raw)
    if (build_binding['source_commit'] != args.commit or build_binding['build_exit'] != 0
            or Path(build_binding['install_prefix']).resolve(strict=True) != prefix):
        raise ValueError('build/install provenance incomplete')
    for filename, digest in build_binding['input_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise ValueError('build input/output bytes changed: ' + filename)
    evidence = {}
    for filename in args.junit:
        path = Path(filename).resolve(strict=True)
        raw = path.read_bytes(); tree = ET.fromstring(raw)
        cases = tree.findall('.//testcase')
        if not cases or tree.findall('.//failure') or tree.findall('.//error') or tree.findall('.//skipped'):
            raise ValueError('offline JUnit incomplete/not green: ' + filename)
        evidence[str(path)] = hashlib.sha256(raw).hexdigest()
    if not evidence:
        raise ValueError('offline evidence required before packet preparation')
    rl, desc, bringup = (prefix/'share'/name for name in ('mecanum_nav_rl','ROBOT_URDF_final_description','mecanum_nav_bringup'))
    document, config_hash, asset_hash, _ = load_bound_config(rl/'config/v3/resolved/sim_train_local_training_soak.resolved.json')
    import re
    if not re.fullmatch(r'B23_[A-Z0-9_]{1,60}', args.run_id):
        raise ValueError('run ID invalid')
    root = Path('/home/hazan/mecanum_runtime_evidence')/args.run_id
    root.mkdir(mode=0o700)  # EEXIST giữ toàn bộ lượt cũ, không retry.
    (root/'trace').mkdir(mode=0o700)
    guard = Path('/home/hazan/.local/state/ros2_nav2_drl/b23')/args.run_id
    guard.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    guard.mkdir(mode=0o700)
    session_id = str(uuid.uuid4())
    ingress = secrets.randbelow(2**63-1)+1
    engine_dir = _physics_engine_plugin_path()
    engine_files = sorted({path.resolve(strict=True) for path in engine_dir.glob('*dartsim-plugin.so*') if path.is_file()})
    if len(engine_files) != 1:
        raise ValueError('DART binary missing or ambiguous')
    engine_file = engine_files[0]
    plan = build_launch_plan(gui='false', resolved_config=rl/'config/v3/resolved/sim_train_local_training_soak.resolved.json',
        world_file=desc/'worlds/b2_training_arena.sdf', gui_config=bringup/'config/gui/local_training.config',
        session_id=session_id, partition='mecanum_' + args.run_id.lower(),
        bridge_config=bringup/'config/bridge/local_training.runtime.yaml',
        resource_paths=(desc.parent, desc/'models'), plugin_path=prefix/'lib', physics_engine_plugin_path=engine_dir,
        asset_manifest_file=desc/'manifests/b2/asset_manifest.json', scenario_directory=rl/'scenarios/local_training',
        runtime_world_directory=root, coordinator_ingress_instance_id=ingress)
    plan = replace(plan, environment={**plan.environment, 'ROS_DOMAIN_ID': '84'},
        commands=(b23_server_argv(plan.world_file),))
    write_bound_world(plan, desc/'worlds/b2_training_arena.sdf', desc/'models/mecanum_b2/model.sdf')
    # Điểm tựa hình học từ bốn wheel cylinder hiện hành; measurement reset vẫn
    # phải kiểm z/roll/pitch/twist thật theo tolerance đã khóa.
    model = ET.parse(desc/'models/mecanum_b2/model.sdf')
    supports = []
    for name in ('Wheel_LF_1','Wheel_RF_1','Wheel_RB_1','Wheel_LB_1'):
        link = model.find(f".//link[@name='{name}']")
        pose = [float(v) for v in link.findtext('pose').split()]
        radius = float(link.findtext('collision/geometry/cylinder/radius'))
        supports.append(radius-pose[2])
    if max(supports)-min(supports) > 1e-9:
        raise ValueError('reset support geometry not uniform')
    inputs = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in prefix.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    import importlib
    from rclpy.impl.implementation_singleton import rclpy_implementation
    dependency_origins = {name: str(Path(importlib.import_module(name).__file__).resolve(strict=True))
        for name in ('rclpy','pydantic','numpy','yaml','ros_gz_interfaces.srv._control_world',
                     'ros_gz_interfaces.srv._set_entity_pose','std_srvs.srv._trigger')}
    dependency_origins['rclpy_native'] = str(Path(rclpy_implementation.__file__).resolve(strict=True))
    dependency_origins['python_binary'] = str(Path(sys.executable).resolve(strict=True))
    inputs.update({path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in dependency_origins.values()})
    inputs.update({str(Path(args.build_binding).resolve()): hashlib.sha256(build_binding_raw).hexdigest(), **evidence,
        str(plan.world_file): hashlib.sha256(plan.world_file.read_bytes()).hexdigest(),
        str(engine_file): hashlib.sha256(engine_file.read_bytes()).hexdigest()})
    environment_keys = ('HOME','USER','LOGNAME','PATH','LANG','LC_ALL','LD_LIBRARY_PATH','PYTHONPATH',
        'AMENT_PREFIX_PATH','CMAKE_PREFIX_PATH','COLCON_PREFIX_PATH','ROS_DISTRO','ROS_VERSION','ROS_PYTHON_VERSION',
        'RMW_IMPLEMENTATION','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','LIBGL_ALWAYS_SOFTWARE','GZ_CONFIG_PATH')
    environment = {k: os.environ[k] for k in environment_keys if k in os.environ}
    environment.update(ROS_DOMAIN_ID='84', ROS_HOME=str(root/'ros-home'), ROS_LOG_DIR=str(root/'ros-log'),
        PYTHONPYCACHEPREFIX=str(root/'pycache'))
    values = launch_plan_record(plan)
    packet = {'schema': 'b23_packet/v1', 'run_id': args.run_id, 'session_id':session_id, 'unit': args.run_id.lower().replace('_','-')+'.service',
        'case': 'R01a', 'gui': False, 'fault_hooks': [], 'world_seed':20261029,
        'episode_seeds':[2026102900,2026102901], 'authority': 'OWNER_B23_CAMPAIGN_APPROVED',
        'authority_reference': 'Owner approval B23_CAMPAIGN and standing authorization in task conversation',
        'source_commit': args.commit, 'source_repo': str(repo), 'install_prefix': str(prefix),
        'build_binding_sha256': hashlib.sha256(build_binding_raw).hexdigest(), 'python': str(Path(sys.executable).absolute()),
        'run_root': str(root), 'guard_path': str(guard), 'active_s':120, 'cleanup_s':60,
        'resolved_config': str(plan.resolved_config), 'config_hash':config_hash, 'asset_manifest_sha256':asset_hash,
        'asset_manifest':str(desc/'manifests/b2/asset_manifest.json'), 'scenario':str(rl/'scenarios/local_training/B2_SOAK_V1.json'),
        'coordinator_ingress_instance_id':ingress, 'physics_engine_sha256':inputs[str(engine_file)],
        'launch_plan':values, 'environment':environment, 'input_sha256':inputs,
        'reset_target':{'x_m':0.,'y_m':0.,'z_m':supports[0],'yaw_rad':0.},
        'robot_state_publisher_argv':['/opt/ros/jazzy/lib/robot_state_publisher/robot_state_publisher',
            '--ros-args','-p','use_sim_time:=true','-p','robot_description:='+(desc/'urdf/mecanum_b2_static.urdf').read_text()],
        'offline_evidence':evidence, 'dependency_origins':dependency_origins,
        'owner_decisions':{'L2-PAUSE':'APPROVED','L2-ADMISSION':'APPROVED','D03':'APPROVED','D04':'APPROVED',
            'D05':'APPROVED','offline_and_git':'APPROVED','runtime':'B23_CAMPAIGN_APPROVED',
            'phase':'smoke','excluded_actions':['R07b time_only rollback','R09b active fixture SetEntityPose','B22 contact-only runtime'],
            'quoted_approval':'Smoke: R01a, dùng profile headless và tắt fault hook.'},
        'source_preflight':[commit_record,branch,dirty]}
    packet['service_properties'] = list(SERVICE_PROPERTIES)
    packet['launch_argv_template'] = service_launch_command(packet, str(root/'packet.json'), '{PACKET_SHA256}')
    digest = write_record_once(root/'packet.json', packet)
    write_record_once(guard/'authority.json', {'run_id':args.run_id, 'capacity':1, 'packet_sha256':digest,
        'authority':packet['authority'], 'phase':'smoke', 'consumed':False})
    print(json.dumps({'packet':str(root/'packet.json'), 'packet_sha256':digest, 'guard':str(guard)}))
    return 0


def unit_properties(unit, *, timeout_s):
    names = ('Id','LoadState','ActiveState','SubState','Result','InvocationID','ControlGroup',
        'MainPID','ExecMainPID','ExecMainCode','ExecMainStatus','ExecStart','Type','KillMode',
        'RuntimeMaxUSec','RuntimeRandomizedExtraUSec','TimeoutStartUSec','TimeoutStopUSec',
        'SendSIGKILL','KillSignal','FinalKillSignal','Restart','RemainAfterExit','ExecMainExitTimestampMonotonic',
        'MemoryMax','MemoryCurrent','MemoryPeak','OOMPolicy')
    record = command_record(['systemctl','--user','show',unit,'--no-pager',
        '--property='+','.join(names)], timeout_s=timeout_s)
    properties = {}
    if record['returncode'] == 0 and record['error'] is None:
        for line in record['stdout'].splitlines():
            key, separator, value = line.partition('=')
            if not separator or key in properties:
                raise ValueError('ambiguous systemd property output')
            properties[key] = value
    return properties, record



def verify_unit_configuration(properties):
    """Đối chiếu giá trị thực; định dạng ngoài tập chính xác phải dừng."""
    expected = {'Type':{'exec'}, 'Restart':{'no'}, 'KillMode':{'control-group'},
        'RemainAfterExit':{'yes'}, 'MemoryMax':{'5368709120'}, 'OOMPolicy':{'stop'}, 'RuntimeMaxUSec':{'3min','180s','180000000us'},
        'RuntimeRandomizedExtraUSec':{'0','0us','0s'}, 'TimeoutStartUSec':{'5s','5000000us'},
        'TimeoutStopUSec':{'2s','2000000us'}, 'SendSIGKILL':{'yes'},
        'KillSignal':{'15','SIGTERM','TERM'}, 'FinalKillSignal':{'9','SIGKILL','KILL'}}
    for key, values in expected.items():
        if properties.get(key) not in values:
            raise ValueError('unit property missing/unrecognized/mismatched: ' + key + '=' + repr(properties.get(key)))


def scan_pinned_cgroup(cgroup):
    """Không dùng path cuối rỗng hoặc lỗi đọc thay cho scan hoàn tất."""
    import os
    if not isinstance(cgroup, str) or not cgroup.startswith('/user.slice/') or '..' in Path(cgroup).parts:
        raise ValueError('unverified cgroup path')
    path = Path('/sys/fs/cgroup')/cgroup.lstrip('/')
    result = {'path':str(path), 'started_ns':time.monotonic_ns(), 'files':{}, 'errors':[], 'members':[]}
    try:
        path.stat()
    except FileNotFoundError:
        # ENOENT của chính path đã pin là fact; không suy từ lỗi walk.
        result.update(status='path_removed_confirmed', completed_ns=time.monotonic_ns())
        return result
    except OSError as error:
        result['errors'].append(repr(error))
    def onerror(error): result['errors'].append(repr(error))
    if not result['errors']:
        for directory, directories, filenames in os.walk(path, onerror=onerror, followlinks=False):
            try:
                for name in directories:
                    if Path(directory, name).is_symlink():
                        raise ValueError('unexpected symlink under pinned cgroup')
                raw = Path(directory, 'cgroup.procs').read_bytes()
                result['files'][str(Path(directory,'cgroup.procs'))] = raw.hex()
                result['members'].extend(int(value) for value in raw.split())
            except (OSError, ValueError) as error:
                result['errors'].append(repr(error))
    result['members'] = sorted(set(result['members']))
    result['status'] = 'incomplete' if result['errors'] or not result['files'] else 'complete_members' if result['members'] else 'complete_empty'
    result['completed_ns'] = time.monotonic_ns()
    return result




def b23_server_argv(world_file):
    """CLI Harmonic cài thật truyền --seed xuống runServer; không chỉ ghi nhãn."""
    return ('gz','sim','-v','3','--seed','20261029','--force-version','8','-s',
            '--headless-rendering',str(world_file))


def unit_parent_command(packet, packet_path, packet_sha256):
    """Giữ InvocationID thật từ systemd trong env sạch, không expand argv packet."""
    wrapper = 'exec /usr/bin/env -i "INVOCATION_ID=${INVOCATION_ID:?}" "$@"'
    return ['/bin/bash','-c',wrapper,'b23-owned-env',
        *[key+'='+value for key,value in sorted(packet['environment'].items())],
        packet['python'],'-B','-m',MODULE,'parent','--packet',packet_path,
        '--packet-sha256',packet_sha256]



def service_launch_command(packet, packet_path, packet_sha256):
    """Mẫu đã pin trong packet; chỉ thay self-hash sau khi xuất packet bất biến."""
    return ['systemd-run','--user','--unit='+packet['unit'],'--expand-environment=no',
        *['--property='+value for value in SERVICE_PROPERTIES],
        *unit_parent_command(packet, packet_path, packet_sha256)]


def launch_packet(args):
    """Đúng một unit/consume; terminal và residue do controller ngoài unit đo."""
    import os
    import sys
    import fcntl
    packet = verify_packet(args.packet, args.packet_sha256)
    root, guard = Path(packet['run_root']), Path(packet['guard_path'])
    log = RunEvidence(root, 'controller', run_id=packet['run_id'], invocation_id='OUTER_CONTROLLER')
    state = guard.parent
    lock = Path('/home/hazan/.local/state/ros2_nav2_drl/b22-simulation-runtime.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    primary, cleanup_error, unit, invocation, pinned_cgroup = None, None, packet['unit'], None, None
    metadata_cleanup_error = None
    identities, terminal, consumed, launch = {}, None, None, None
    try:
        for previous in state.iterdir():
            if previous.is_dir() and (previous/'consumed.json').exists():
                verified = previous/'terminal-verified.json'
                if not verified.exists() or json.loads(verified.read_bytes()).get('residue_absent') is not True:
                    raise RuntimeError('previous consumed run has unverified residue: ' + str(previous))
        preflight = command_record(['systemctl','--user','show','--property=SystemState','--value'], timeout_s=5.)
        log.record('USER_MANAGER', preflight)
        if preflight['returncode'] != 0 or preflight['stdout'].strip() != 'running':
            raise RuntimeError('user manager unavailable; no permission/environment changes attempted')
        properties, record = unit_properties(unit, timeout_s=5.)
        log.record('UNIT_COLLISION_CHECK', record)
        if properties.get('LoadState') != 'not-found':
            raise RuntimeError('unit name already exists or collision query incomplete')
        authority = json.loads((guard/'authority.json').read_bytes())
        if authority['packet_sha256'] != args.packet_sha256 or authority['capacity'] != 1:
            raise RuntimeError('capacity-one authority does not match packet')
        started = time.monotonic_ns()
        consumed = {'run_id':packet['run_id'], 'packet_sha256':args.packet_sha256, 'consumed_ns':started,
            'active_deadline_ns':started+packet['active_s']*10**9,
            'total_deadline_ns':started+(packet['active_s']+packet['cleanup_s'])*10**9}
        write_record_once(guard/'consumed.json', consumed)
        command = service_launch_command(packet, str(Path(args.packet).resolve()), args.packet_sha256)
        write_record_once(root/'launch-argv.json', {'argv':command, 'packet_sha256':args.packet_sha256})
        launch = command_record(command, timeout_s=min(5., (consumed['active_deadline_ns']-time.monotonic_ns())/1e9))
        log.record('SERVICE_LAUNCH', launch)
        # timeout/nonzero không chứng minh unit chưa được tạo; vẫn đối chiếu.
        end = consumed['total_deadline_ns']
        while time.monotonic_ns() < end:
            props, record = unit_properties(unit, timeout_s=min(2., max(0.,(end-time.monotonic_ns())/1e9)))
            log.record('UNIT_OBSERVATION', record)
            if props.get('InvocationID'):
                if invocation is None:
                    if (props.get('Id') != unit or args.packet_sha256 not in props.get('ExecStart','')
                            or str(Path(args.packet).resolve()) not in props.get('ExecStart','')):
                        raise RuntimeError('launched unit ownership cannot be verified')
                    invocation = props['InvocationID']
                elif invocation != props['InvocationID']:
                    raise RuntimeError('unit invocation changed')
            if props.get('ControlGroup'):
                if pinned_cgroup is None and invocation is not None:
                    candidate = props['ControlGroup']
                    if Path(candidate).name != unit:
                        raise RuntimeError('unit cgroup ownership mismatch')
                    pinned_cgroup = candidate
                elif props['ControlGroup'] != pinned_cgroup:
                    raise RuntimeError('unit cgroup changed')
            try:
                log.record('HOST_MEMORY', {'meminfo_hex':Path('/proc/meminfo').read_bytes().hex(),
                    'collected_ns':time.monotonic_ns()})
            except OSError as error:
                log.record('HOST_MEMORY_ERROR', {'error':repr(error)})
            if invocation is not None and props:
                verify_unit_configuration(props)
            if pinned_cgroup:
                scan = scan_pinned_cgroup(pinned_cgroup)
                log.record('CGROUP_OBSERVATION', scan)
                for pid in scan['members']:
                    try:
                        identity = process_identity(pid)
                        key = (pid,identity['start_ticks'])
                        if identity['argv'] or key not in identities:
                            identities[key] = identity
                        log.record('PID_OBSERVATION', identity)
                    except OSError as error:
                        log.record('PID_READ_ERROR', {'pid':pid,'error':repr(error)})
            if invocation is not None and (props.get('ActiveState') in ('inactive','failed')
                    or (props.get('ActiveState') == 'active' and props.get('SubState') == 'exited'
                        and props.get('MainPID') == '0' and int(props.get('ExecMainExitTimestampMonotonic','0')) > 0)):
                terminal = props
                break
            remaining = end-time.monotonic_ns()
            if remaining > 0: time.sleep(min(.2, remaining/1e9))
        if launch['returncode'] != 0:
            raise RuntimeError('service launch did not return success: ' + str(launch['returncode']))
        if terminal is None:
            raise RuntimeError('unit terminal not observed inside total deadline')
    except BaseException as error:
        primary = repr(error)
        log.record('CONTROLLER_PRIMARY_ERROR', {'error':primary})
    finally:
        # Chỉ invocation đã pin, sau khi đọc lại command+identity; không dò tên
        # process để kill. Ngân sách này không gia hạn total deadline.
        if consumed is not None:
            end = consumed['total_deadline_ns']
            try:
                if invocation is not None and (terminal is None or terminal.get('ActiveState') in ('active','failed')) and time.monotonic_ns() < end:
                    props, record = unit_properties(unit, timeout_s=min(1., (end-time.monotonic_ns())/1e9))
                    log.record('PRE_STOP_BINDING', record)
                    if (props.get('InvocationID') != invocation or props.get('Id') != unit
                            or (props.get('ControlGroup') != pinned_cgroup
                                and not (terminal is not None and props.get('ControlGroup') == ''
                                    and props.get('ActiveState') in ('active','inactive','failed') and props.get('MainPID') == '0'))
                            or args.packet_sha256 not in props.get('ExecStart','')):
                        raise RuntimeError('ownership changed/unverified: no stop dispatched')
                    record = command_record(['systemctl','--user','stop',unit],
                        timeout_s=min(2., max(0.,(end-time.monotonic_ns())/1e9)))
                    log.record('GUARDED_STOP', record)
                    if record['returncode'] != 0: raise RuntimeError('guarded stop incomplete')
                if invocation is None or pinned_cgroup is None:
                    raise RuntimeError('missing invocation/cgroup binding; residue UNKNOWN')
                scan = scan_pinned_cgroup(pinned_cgroup)
                log.record('FINAL_CGROUP', scan)
                absent = scan['status'] in ('complete_empty','path_removed_confirmed') and not scan['errors'] and not scan['members']
                pid_states = []
                for (pid, ticks), saved in identities.items():
                    try:
                        current = process_identity(pid)
                        same = current['start_ticks'] == ticks
                        pid_states.append({'saved':saved,'current':current,'same_identity':same})
                        if same: absent = False  # live hoặc zombie đều chưa sạch.
                    except FileNotFoundError:
                        pid_states.append({'saved':saved,'absent':True})
                    except OSError as error:
                        absent = False; pid_states.append({'saved':saved,'error':repr(error)})
                verified = {'run_id':packet['run_id'], 'packet_sha256':args.packet_sha256,
                    'invocation_id':invocation,'pinned_cgroup':pinned_cgroup,'terminal':terminal,
                    'residue_absent':absent,'scan':scan,'pid_states':pid_states,'completed_ns':time.monotonic_ns()}
                write_record_once(guard/'terminal-verified.json', verified)
                write_record_once(root/'terminal-evidence.json', verified)
                if not absent: raise RuntimeError('residue not verified absent; next run blocked')
            except BaseException as error:
                cleanup_error = repr(error)
                log.record('CONTROLLER_CLEANUP_ERROR', {'error':cleanup_error})
            journal = command_record(['journalctl','--user','-u',unit,'--no-pager','-o','json',
                *(['_SYSTEMD_INVOCATION_ID='+invocation] if invocation else [])], timeout_s=3.)
            log.record('JOURNAL_SUPPORT', journal)
            if terminal is not None and terminal.get('ActiveState') == 'failed' and cleanup_error is None:
                try:
                    clear_owned_failed_state(unit, invocation, terminal['ExecMainPID'], args.packet_sha256,
                        deadline_ns=end, emit=log.record)
                except BaseException as error:
                    metadata_cleanup_error = repr(error)
                    log.record('OWNED_FAILED_STATE_CLEAR_ERROR', {'error':metadata_cleanup_error})
        result = {'run_id':packet['run_id'], 'packet_sha256':args.packet_sha256,
            'primary_error':primary,'cleanup_error':cleanup_error, 'metadata_cleanup_error':metadata_cleanup_error, 'launch_record':launch,
            'terminal':terminal, 'completed_ns':time.monotonic_ns()}
        write_record_once(root/'controller-result.json', result)
        log.close(); fcntl.flock(lock, fcntl.LOCK_UN); lock.close()
    parent = json.loads((root/'parent-result.json').read_bytes()) if (root/'parent-result.json').exists() else None
    success = (primary is None and cleanup_error is None and metadata_cleanup_error is None and terminal is not None
        and terminal.get('Result') == 'success' and terminal.get('ExecMainCode') == str(os.CLD_EXITED)
        and terminal.get('ExecMainStatus') == '0' and parent is not None
        and parent['primary_error'] is None and parent['cleanup_clean']
        and parent['run_id'] == packet['run_id'] and parent['invocation_id'] == invocation
        and consumed is not None and parent['completed_ns'] <= consumed['total_deadline_ns']
        and json.loads((guard/'terminal-verified.json').read_bytes())['completed_ns'] <= consumed['total_deadline_ns'])
    parent_identity = json.loads((root/'parent-identity.json').read_bytes()) if (root/'parent-identity.json').exists() else None
    binding_errors = terminal_binding_errors(packet, terminal, parent_identity, identities, invocation, args.packet_sha256)
    success = success and not binding_errors
    assessment = {'run_id':packet['run_id'], 'technical_outcome':'R01a_COMPLETED' if success else 'INCOMPLETE',
        'evidence':str(root),'primary_error':primary,'cleanup_error':cleanup_error,
        'terminal_binding_errors':binding_errors, 'metadata_cleanup_error':metadata_cleanup_error,
        'parent_primary_error':None if parent is None else parent.get('primary_error'), 'assessed_ns':time.monotonic_ns()}
    write_record_once(root/'r01a-assessment.json', assessment)
    hashes = {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob('*') if path.is_file()}
    guard_hashes = {str(path):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in guard.iterdir() if path.is_file()}
    write_record_once(root/'evidence-manifest.json', {'schema':'b23_evidence_manifest/v1',
        'run_id':packet['run_id'],'source_commit':packet['source_commit'],
        'packet_sha256':args.packet_sha256,'files':hashes,'guard_files':guard_hashes})
    print(json.dumps(assessment))
    return 0 if success else 1




def clear_owned_failed_state(unit, invocation, terminal_pid, packet_sha256, *, deadline_ns, emit,
                             now_ns=time.monotonic_ns):
    """Chỉ metadata unit đã thất bại, sau raw journal và proof không còn process.

    Không reset guard, không đổi verdict và không chạm failed unit khác.
    """
    remaining = (deadline_ns-now_ns())/1e9
    if remaining <= 0: raise TimeoutError('owned failed-state cleanup budget expired')
    properties, record = unit_properties(unit, timeout_s=min(1., remaining))
    emit('PRE_FAILED_STATE_CLEAR_BINDING', record)
    if (properties.get('Id') != unit or properties.get('InvocationID') != invocation
            or properties.get('ExecMainPID') != str(terminal_pid) or properties.get('MainPID') != '0'
            or properties.get('ActiveState') not in ('failed','inactive')
            or properties.get('ControlGroup') != '' or packet_sha256 not in properties.get('ExecStart','')):
        raise RuntimeError('failed-state ownership changed/unverified; no reset dispatched')
    remaining = (deadline_ns-now_ns())/1e9
    if remaining <= 0: raise TimeoutError('owned failed-state cleanup budget expired before reset')
    record = command_record(['systemctl','--user','reset-failed',unit], timeout_s=min(1.,remaining))
    emit('OWNED_FAILED_STATE_CLEAR_RESULT', record)
    if record['returncode'] != 0 or record['error'] is not None:
        raise RuntimeError('own failed-state clear failed')


def terminal_binding_errors(packet, terminal, parent_record, observed, invocation, packet_sha256):
    """Nối terminal unit tới PID/start ticks/argv đã đo, không dùng tên chung."""
    errors = []
    if terminal is None or parent_record is None:
        return ['missing unit terminal or actual parent identity record']
    identity = parent_record.get('identity', {})
    pid, ticks = identity.get('pid'), identity.get('start_ticks')
    saved = observed.get((pid,ticks))
    if (parent_record.get('invocation_id') != invocation or parent_record.get('run_id') != packet['run_id']
            or parent_record.get('packet_sha256') != packet_sha256
            or terminal.get('InvocationID') != invocation or terminal.get('Id') != packet['unit']
            or terminal.get('ExecMainPID') != str(pid)):
        errors.append('unit/InvocationID/ExecMainPID/packet binding mismatch')
    expected = [packet['python'],'-B','-m',MODULE,'parent','--packet',str(Path(packet['run_root'])/'packet.json'),
                '--packet-sha256',packet_sha256]
    if (saved is None or identity.get('uid') != 1000 or identity.get('argv') != expected
            or saved.get('argv') != expected or saved.get('uid') != 1000):
        errors.append('parent identity/argv not independently observed or changed')
    return errors


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='B2.3 campaign runner với packet/guard capacity-one')
    commands = parser.add_subparsers(dest='role', required=True)
    prepare = commands.add_parser('prepare')
    for key in ('repo','commit','install','build-binding','run-id'):
        prepare.add_argument('--'+key, required=True)
    prepare.add_argument('--junit', action='append', required=True)
    for role in ('launch','parent'):
        command = commands.add_parser(role)
        command.add_argument('--packet', required=True); command.add_argument('--packet-sha256', required=True)
    for role in ('worker','final'):
        commands.add_parser(role).add_argument('--descriptor', required=True)
    args = parser.parse_args(argv)
    if args.role == 'prepare': return prepare_packet(args)
    if args.role == 'launch': return launch_packet(args)
    if args.role == 'parent': return asyncio.run(run_parent(args.packet, args.packet_sha256))
    if args.role == 'worker': return asyncio.run(training_child(args.descriptor))
    return final_child(args.descriptor)


if __name__ == '__main__':
    raise SystemExit(main())
