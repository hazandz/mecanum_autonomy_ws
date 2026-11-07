from pathlib import Path
import json,sys,subprocess,time,hashlib
r=Path(Path('/tmp/b22-query-cache-current-root').read_text().strip());label=sys.argv[1];p=json.loads((r/(label+'-packet.json')).read_text());assert not (r/p['run_id']).exists();record=r/(label+'-launch.json');assert not record.exists()
if label.startswith('gui'):
 previous=json.loads((r/'contact-001-outer-cleanup.json').read_text());assert not previous['remaining_cgroup_exists'] and not previous['scan_errors']
for path,sha in json.loads(Path(p['profile']).read_text())['files'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha
start=time.monotonic_ns()
with record.open('x') as stream:json.dump({'phase':'launch_requested_once','at_ns':start,'packet_sha256':hashlib.sha256((r/(label+'-packet.json')).read_bytes()).hexdigest(),'command':p['launch_command'],'authority':p['authority']},stream,indent=2)
out=subprocess.run(p['launch_command'],capture_output=True,text=True,timeout=10)
(r/(label+'-launch-result.json')).write_text(json.dumps({'started_ns':start,'finished_ns':time.monotonic_ns(),'stdout':out.stdout,'stderr':out.stderr,'exit':out.returncode},indent=2));print(out.returncode,out.stderr);assert out.returncode==0
out=subprocess.run(p['unit_properties_command'],capture_output=True,text=True,timeout=5);(r/(label+'-initial.json')).write_text(json.dumps({'stdout':out.stdout,'stderr':out.stderr,'exit':out.returncode,'collected_ns':time.monotonic_ns()},indent=2));print(out.stdout);assert out.returncode==0
