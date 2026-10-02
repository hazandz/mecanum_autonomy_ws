#!/usr/bin/env python3
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("run_ecs_contact_diagnostic.py")
spec = importlib.util.spec_from_file_location("ecs_supervisor", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
assert spec.loader is not None
spec.loader.exec_module(mod)

class FakeProcess:
    def __init__(self, ready=True, terminal="ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED", grace=True):
        self._ready, self._terminal, self._grace, self.sigints = ready, terminal, grace, 0
    def ready(self): return self._ready
    def terminal(self): return self._terminal
    def send_sigint_group(self): self.sigints += 1
    def wait_grace(self, timeout_ns): return self._grace

class FakeRunner:
    def __init__(self, render=True, manifest=True, collector_ready=True, receipt_mutator=None):
        self.render_ok, self.manifest_ok, self.collector_ready = render, manifest, collector_ready
        self.receipt_mutator, self.events, self.commands, self.processes = receipt_mutator, [], [], {}
    def render(self, command, plan):
        self.events.append("render"); self.commands.append(command); return self.render_ok
    def read_renderer_result(self, plan):
        self.events.append("render_result")
        receipt=mod.RendererResultReceipt("s3_d3_renderer_result/v1", plan.run_id, plan.template_installed.resolve(), plan.rendered_world.resolve(), plan.template_sha256, "a" * 64)
        return self.receipt_mutator(receipt) if self.receipt_mutator else receipt
    def write_manifest(self, plan, receipt):
        self.events.append("manifest"); return self.manifest_ok
    def start(self, role, command):
        self.events.append(role); self.commands.append(command)
        process=FakeProcess(ready=self.collector_ready if role == "collector" else True)
        self.processes[role]=process; return process

class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.create=Path('/opt/ros/jazzy/lib/ros_gz_sim/create')
        self.paths={}
        for name in ('template_source','template_installed','model_source','model_installed','plugin_source','plugin_binary','collector_source','collector_binary','renderer_executable','collector_executable','launch_executable','launch_file'):
            path=self.root/name; path.write_text(name); self.paths[name]=path
        self.paths['template_installed'].write_bytes(self.paths['template_source'].read_bytes())
        self.paths['model_installed'].write_bytes(self.paths['model_source'].read_bytes())
        self.hashes={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in self.paths.values()}
        self.hashes[self.create]='b'*64
    def tearDown(self): self.tmp.cleanup()
    def fake_hash(self,path): return self.hashes[path]
    def fake_regular(self,path): return path in self.hashes
    def plan(self):
        run_directory=self.root/'run-run_12345678'; rendered=run_directory/'native_sdf_contact_diagnostic.rendered.sdf'
        self.hashes[rendered]='a'*64
        h=lambda name:self.hashes[self.paths[name]]
        return mod.EcsDiagnosticRunPlan(
            workspace_root=self.root, run_id='run_12345678', template_source=self.paths['template_source'], template_installed=self.paths['template_installed'], template_sha256=h('template_source'),
            model_source=self.paths['model_source'], model_installed=self.paths['model_installed'], model_sha256=h('model_source'),
            plugin_source=self.paths['plugin_source'], plugin_source_sha256=h('plugin_source'), plugin_binary=self.paths['plugin_binary'], plugin_binary_sha256=h('plugin_binary'),
            collector_source=self.paths['collector_source'], collector_source_sha256=h('collector_source'), collector_binary=self.paths['collector_binary'], collector_binary_sha256=h('collector_binary'),
            renderer_executable=self.paths['renderer_executable'], renderer_sha256=h('renderer_executable'), collector_executable=self.paths['collector_executable'], collector_executable_sha256=h('collector_executable'),
            launch_executable=self.paths['launch_executable'], launch_executable_sha256=h('launch_executable'), launch_file=self.paths['launch_file'], launch_sha256=h('launch_file'),
            create_executable=self.create, create_sha256='b'*64,
            create_argv=('-world','world_demo','-file',str(self.paths['model_installed'].resolve()),'-name','ROBOT_URDF_final','-allow_renaming','false','-x','0','-y','0','-z','0.1','-Y','0'),
            run_directory=run_directory, rendered_world=rendered, renderer_result_receipt=run_directory/'renderer_result.json',
            world_name='world_demo', model_name='ROBOT_URDF_final', link_name='base_link', sensor_name='s3_d3_base_contact_sensor', receipt_topic='/s3_d3/receipt',
            system_wait_timeout_sim_time_ns=1, system_delivery_wait_timeout_steady_ns=2, collector_receipt_wait_timeout_steady_ns=3, collector_persist_timeout_steady_ns=4)
    def run_future(self, plan, runner): return mod.orchestrate_future(plan,runner,file_hash=self.fake_hash,is_regular=self.fake_regular)
    def test_exact_order_one_child_each_and_sigint_cleanup(self):
        runner=FakeRunner(); result=self.run_future(self.plan(),runner)
        self.assertEqual(result.events,('preflight','render','render_result','manifest','collector','launch','create','collector_terminal'))
        self.assertEqual(runner.events,['render','render_result','manifest','collector','launch','create'])
        self.assertEqual([command.shell for command in runner.commands],[False]*4); self.assertEqual([command.new_session for command in runner.commands],[True]*4)
        self.assertEqual([record.process_role for record in result.cleanup],['create','launch','collector']); self.assertTrue(all(record.supervisor_initiated_sigint_only for record in result.cleanup))
    def test_render_and_manifest_failures_start_zero_children(self):
        for runner, expected, events in ((FakeRunner(render=False),'INVALID_RENDER',['render']), (FakeRunner(manifest=False),'INVALID_MANIFEST',['render','render_result','manifest'])):
            result=self.run_future(self.plan(),runner); self.assertEqual(result.status,expected); self.assertEqual(runner.events,events)
    def test_collector_unready_blocks_launch_and_create(self):
        runner=FakeRunner(collector_ready=False); result=self.run_future(self.plan(),runner)
        self.assertEqual(result.status,'COLLECTOR_UNREADY'); self.assertEqual(runner.events,['render','render_result','manifest','collector']); self.assertEqual(runner.processes['collector'].sigints,1)
    def test_create_and_workspace_drift_rejected_before_render(self):
        plan=self.plan(); runner=FakeRunner(); bad=mod.EcsDiagnosticRunPlan(**{**plan.__dict__,'create_argv':('-topic','bad')})
        self.assertEqual(self.run_future(bad,runner).status,'INVALID_NATIVE_CREATE_CONTRACT'); self.assertEqual(runner.events,[])
        bad=mod.EcsDiagnosticRunPlan(**{**plan.__dict__,'run_directory':Path('/tmp/escape'),'rendered_world':Path('/tmp/escape/world.sdf'),'renderer_result_receipt':Path('/tmp/escape/renderer_result.json')})
        self.assertEqual(self.run_future(bad,FakeRunner()).status,'INVALID_WORKSPACE_PATH')
    def test_every_bound_artifact_hash_drift_rejected_before_render(self):
        for name in self.paths:
            with self.subTest(name=name):
                plan=self.plan(); original=self.hashes[self.paths[name]]; self.hashes[self.paths[name]]='f'*64
                runner=FakeRunner(); self.assertEqual(self.run_future(plan,runner).status,'INVALID_PREFLIGHT_BINDING'); self.assertEqual(runner.events,[]); self.hashes[self.paths[name]]=original
    def test_missing_malformed_or_mismatched_result_blocks_children(self):
        cases=(
            lambda receipt:None,
            lambda receipt:mod.RendererResultReceipt(receipt.schema_version,'wrong_run',receipt.template_path,receipt.rendered_world_path,receipt.base_world_template_sha256,receipt.rendered_world_sha256),
            lambda receipt:mod.RendererResultReceipt(receipt.schema_version,receipt.run_id,self.root/'wrong',receipt.rendered_world_path,receipt.base_world_template_sha256,receipt.rendered_world_sha256),
            lambda receipt:mod.RendererResultReceipt(receipt.schema_version,receipt.run_id,receipt.template_path,self.root/'wrong',receipt.base_world_template_sha256,receipt.rendered_world_sha256),
            lambda receipt:mod.RendererResultReceipt(receipt.schema_version,receipt.run_id,receipt.template_path,receipt.rendered_world_path,'b'*64,receipt.rendered_world_sha256),
            lambda receipt:mod.RendererResultReceipt(receipt.schema_version,receipt.run_id,receipt.template_path,receipt.rendered_world_path,receipt.base_world_template_sha256,'c'*64),
        )
        for mutate in cases:
            with self.subTest(mutate=mutate):
                runner=FakeRunner(receipt_mutator=mutate); result=self.run_future(self.plan(),runner)
                self.assertEqual(result.status,'INVALID_RENDER_RESULT_PROVENANCE'); self.assertEqual(runner.events,['render','render_result'])
    def test_renderer_command_binds_result_run_id_and_output(self):
        plan=self.plan(); command=mod.renderer_command(plan)
        self.assertEqual(command.argv[command.argv.index('--result')+1],str(plan.renderer_result_receipt)); self.assertIn(plan.run_id,command.argv); self.assertEqual(plan.run_directory.name,'run-'+plan.run_id)
    def test_result_json_parser_is_strict(self):
        path=self.root/'receipt.json'; path.write_text('broken'); self.assertIsNone(mod.parse_renderer_result_receipt(path))
        path.write_text('{"schema_version":"wrong"}'); self.assertIsNone(mod.parse_renderer_result_receipt(path))
    def test_execute_blocks_before_dependencies(self): self.assertEqual(mod.main(['--execute']),2)
    def test_source_has_no_runtime_bypass_or_force_kill(self):
        source=MODULE_PATH.read_text()
        for banned in ('subprocess','shell=True','.kill(','SIGTERM','SIGKILL','/cmd_vel','RequestRaw'): self.assertNotIn(banned,source)

if __name__ == '__main__': unittest.main()
