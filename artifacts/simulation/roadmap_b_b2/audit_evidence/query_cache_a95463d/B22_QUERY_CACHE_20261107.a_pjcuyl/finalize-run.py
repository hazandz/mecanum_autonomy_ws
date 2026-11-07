import pathlib,json,subprocess,time,hashlib,sys,os
r=pathlib.Path(pathlib.Path('/tmp/b22-query-cache-current-root').read_text().strip());label=sys.argv[1];p=json.loads((r/(label+'-packet.json')).read_text());initial=json.loads((r/(label+'-initial.json')).read_text())['stdout']
props=lambda s:dict(l.split('=',1) for l in s.splitlines() if '=' in l)
a=props(initial);start=time.monotonic_ns();out=subprocess.run(p['unit_properties_command'],capture_output=True,text=True,timeout=5);assert out.returncode==0
b=props(out.stdout);assert b['InvocationID']==a['InvocationID'];assert b['ExecMainPID']==a['MainPID'];assert b['SubState']=='exited' and b['ExecMainStatus']=='0'
e={'initial_unit':initial,'terminal_unit':out.stdout,'collected_start_ns':start,'collected_end_ns':time.monotonic_ns()};ep=r/(label+'-terminal.json');ep.write_text(json.dumps(e,indent=2))
argv=p['worker_argv'][:3]+['--validate-terminal',str(r/p['run_id']),str(ep),str(r/(label+'-packet.json')),hashlib.sha256((r/(label+'-packet.json')).read_bytes()).hexdigest()]
out=subprocess.run(argv,capture_output=True,text=True,timeout=10);(r/(label+'-terminal-validation.json')).write_text(json.dumps({'command':argv,'stdout':out.stdout,'stderr':out.stderr,'exit':out.returncode},indent=2));print(out.stdout,out.stderr);assert out.returncode==0
# Đọc lại ngay trước stop; không tác động invocation khác.
cur=subprocess.run(p['unit_properties_command'],capture_output=True,text=True,timeout=5);c=props(cur.stdout);assert cur.returncode==0 and c['InvocationID']==a['InvocationID'] and c['ExecMainPID']==a['MainPID']
out=subprocess.run(['systemctl','--user','stop',p['unit']],capture_output=True,text=True,timeout=7)
cg=pathlib.Path('/sys/fs/cgroup'+a['ControlGroup']);errors=[];members={}
if cg.exists():
 def err(e):errors.append(str(e))
 for directory,dirs,files in os.walk(cg,onerror=err):
  if 'cgroup.procs' in files:
   q=pathlib.Path(directory)/'cgroup.procs'
   try:members[str(q)]=q.read_text().split()
   except OSError as ex:errors.append(str(ex))
res={'checked_ns':time.monotonic_ns(),'pinned_invocation':a['InvocationID'],'pinned_cgroup':str(cg),'guarded_stop_exit':out.returncode,'stdout':out.stdout,'stderr':out.stderr,'remaining_cgroup_exists':cg.exists(),'members':members,'scan_errors':errors,'unit_raw':cur.stdout}
(r/(label+'-outer-cleanup.json')).write_text(json.dumps(res,indent=2));print(json.dumps(res));assert out.returncode==0 and not errors and not any(members.values())
