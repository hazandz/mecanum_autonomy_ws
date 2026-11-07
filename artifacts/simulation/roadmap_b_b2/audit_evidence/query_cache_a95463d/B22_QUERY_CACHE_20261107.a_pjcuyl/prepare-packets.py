from pathlib import Path
import importlib.util,json,hashlib,sys,subprocess,uuid,shlex,argparse
r=Path(Path('/tmp/b22-query-cache-current-root').read_text().strip());snap=r/'runtime-snapshot';prefix=r/'install';commit=(r/'candidate-commit.txt').read_text().strip();runner=snap/'artifacts/simulation/roadmap_b_b2/gui_verification/tools/observation_runner.py';h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('b22_qcache_runner',runner);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==commit
assert not json.loads(Path('/home/hazan/mecanum_runtime_evidence/B22_CONTACT_ONLY_20261107.vyuE1i/gui-final-003-outer-cleanup.json').read_text())['remaining_cgroup_exists']
authority='Owner authorized B2.2 cached QUERY corrective: Codex packet review, fresh capacity-one contact and GUI confirmation; no B2.3 or hardware'
engine=Path('/opt/ros/jazzy/opt/gz_physics_vendor/lib/gz-physics-7/engine-plugins/libgz-physics7-dartsim-plugin.so.7.6.0')
for label,run,mode in [('contact-001','B22_CONTACT_QUERY_CACHE_VERIFY_001','contact_probe_only'),('gui-001','B22_GUI_QUERY_CACHE_VERIFY_001','gui')]:
 assert not (r/run).exists()
 wrapper=r/('execute-'+label+'.sh');pp=r/(label+'-profile.json');packetp=r/(label+'-packet.json');assert not pp.exists() and not wrapper.exists()
 unit='b22-qcache-'+label+'-'+uuid.uuid4().hex[:10]+'.service'
 profile={'schema':'b22_gui_profile/v2','mode':mode,'run_id':run,'source_commit':commit,'authority':authority,'unit':unit,'parent_argv':['/bin/bash',str(wrapper)],'install':str(prefix),'evidence':str(r),'python':str(Path(sys.executable).resolve()),'files':{str(p):h(p) for p in sorted(m.profile_inputs(prefix))},'capacity':1,'contract':{'active_s':240,'cleanup_s':60,'total_s':300,'observation_s':60,'review_s':60,'inhibited':True,'no_POLICY':True,'reviewer':'CODEX','owner_visual_review':'NOT_PERFORMED'}}
 if mode=='contact_probe_only':profile.update(engine_file=str(engine),physics_engine_sha256=h(engine));profile['contract'].update(probe_deadline_s=5,cleanup_reserve_s=1,no_actuator_gate=True)
 pp.write_text(json.dumps(profile,indent=2)+'\n')
 args=argparse.Namespace(evidence=str(r),run_id=run,install=str(prefix),source_commit=commit,authority=authority,profile=str(pp),profile_sha256=h(pp));m.verify_profile(args);argv=m.worker_command(args)
 wrapper.write_text('#!/bin/bash\nset -e\nexec 9>/home/hazan/.local/state/ros2_nav2_drl/b22-simulation-runtime.lock\nflock -n 9\nsource /opt/ros/jazzy/setup.bash\nsource '+shlex.quote(str(prefix/'setup.bash'))+'\nset +e\n'+shlex.join(argv)+'\nB22_PY_EXIT=$?\nprintf "%s\\n" "$B22_PY_EXIT" >'+str(r/(label+'-python.exit'))+'\nB22_WRITE_EXIT=$?\nprintf "%s\\n" "$B22_WRITE_EXIT" >'+str(r/(label+'-writer.exit'))+'\nif [ "$B22_PY_EXIT" -ne 0 ]; then exit "$B22_PY_EXIT"; fi\nexit "$B22_WRITE_EXIT"\n')
 subprocess.run(['bash','-n',str(wrapper)],check=True)
 launch=['systemd-run','--user','--unit='+unit]+['--property='+v for v in ('Type=exec','RemainAfterExit=yes','Restart=no','RuntimeMaxSec=300s','TimeoutStartSec=3s','TimeoutStopSec=5s','KillMode=control-group','SendSIGKILL=yes','MemoryMax=5G','StandardOutput=append:'+str(r/(label+'.stdout')),'StandardError=append:'+str(r/(label+'.stderr')))]+profile['parent_argv']
 props=['systemctl','--user','show',unit,'-p','Id,LoadState,ActiveState,SubState,InvocationID,ControlGroup,MainPID,ExecMainPID,ExecMainCode,ExecMainStatus,ExecMainExitTimestampMonotonic,Result,ExecStart,Type,RemainAfterExit,Restart,RuntimeMaxUSec,TimeoutStopUSec,KillMode,SendSIGKILL,MemoryMax']
 collision=subprocess.run(['systemctl','--user','show',unit,'-p','LoadState'],capture_output=True,text=True,timeout=5);assert 'LoadState=not-found' in collision.stdout
 packet={'source_commit':commit,'run_id':run,'unit':unit,'source_runner_sha256':h(runner),'profile':str(pp),'profile_sha256':h(pp),'parent_argv':profile['parent_argv'],'worker_argv':argv,'wrapper_sha256':h(wrapper),'launch_command':launch,'unit_properties_command':props,'authority':authority,'capacity':1,'install':str(prefix),'mode':mode}
 packetp.write_text(json.dumps(packet,indent=2)+'\n');print(label,'files',len(profile['files']),'packet',h(packetp),'unit',unit)
