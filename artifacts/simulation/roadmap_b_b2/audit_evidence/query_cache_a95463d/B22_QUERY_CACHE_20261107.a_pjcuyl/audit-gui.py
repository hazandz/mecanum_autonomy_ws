from pathlib import Path
import json,hashlib,sys,importlib.util
r=Path(Path('/tmp/b22-query-cache-current-root').read_text().strip());d=r/'B22_GUI_QUERY_CACHE_VERIFY_001'
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
completion=json.loads((d/'completion.json').read_text());cleanup=json.loads((d/'cleanup.json').read_text());binding=json.loads((d/'bindings.json').read_text());consumed=json.loads((d/'consumed.json').read_text());terminal=json.loads((d/'completion-acceptance.json').read_text());outer=json.loads((r/'gui-001-outer-cleanup.json').read_text());batch=json.loads((d/'cleanup-batch.json').read_text());rows=[json.loads(l) for l in (d/'observation.jsonl').read_text().splitlines()]
assert completion['failures']==[] and completion['cleanup_clean'] and terminal['timing_verdict']=='PASS'
assert h(d/'observation.jsonl')==completion['stream_sha256'];assert cleanup['publication']['acknowledged'] and cleanup['publication']['batch_id']==batch['batch_id'];assert cleanup['process_residue']==cleanup['task_residue']=='NONE';assert not outer['remaining_cgroup_exists'] and not outer['scan_errors']
assert all(e['run_id']==d.name and e['session_id']==completion['outcomes']['observation']['backend_identity'][0] for e in rows)
status=[e['facts'] for e in rows if e['event']=='backend_status_sample'];clock=[e['facts'] for e in rows if e['event']=='clock_sample']
assert all(s['paused'] and s['actuator_inhibited'] and not s['applied_receipt_valid'] and s['fault_flags']==0 for s in status)
assert all(s['clock_sec']==s['clock_nanosec']==0 for s in clock)
status_times=[s['receive_steady_ns'] for s in status];clock_times=[s['receive_steady_ns'] for s in clock];gap=lambda times:max(b-a for a,b in zip(times,times[1:]));assert gap(status_times)<=1_000_000_000 and gap(clock_times)<=1_000_000_000
assert completion['outcomes']['observation']['observed_seconds']>=60
request=json.loads((d/'review-request.json').read_text());review=json.loads((d/'codex-review.json').read_text());assert review['request_sha256']==h(d/'review-request.json') and review['screenshot_sha256']==h(d/'gui.png') and review['at_ns']<=request['deadline_ns'] and review['source']=='codex_image_review' and review['verdict']=='PASS'
platform=json.loads((d/'capture-platform.json').read_text());assert platform['platform']=='xcb' and 'IsViewable' in platform['xwininfo']['stdout'];assert platform['window_identity']==request['window']['gui_process_identity']
# Reader sẵn có chỉ được gọi sau khi reap/group absence đã xác minh.
facts=cleanup['observer_facts'];join=facts['join_evidence'];assert join['server_process_joined'] and join['server_group_absent'] and join['observer_process_joined'] and join['observer_process_group_absent'] and join['observer_end_written'] and join['observer_writer_closed']
ctx=facts['clock_context'];cert=facts['clock_domain_certificate'];assert cert['provenance']==ctx['provenance']==binding['clock']['provenance'];assert cert['binary_sha256']==h(r/'install/lib/libmecanum_heartbeat_trace_writer.so');assert all(x['python_before_ns']<=x['native_ns']<=x['python_after_ns'] for x in cert['samples'])
path=r/'runtime-snapshot/artifacts/simulation/roadmap_b_b2/heartbeat_diagnostics/heartbeat_trace_reader.py';spec=importlib.util.spec_from_file_location('b22_exact_trace_reader',path);reader=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reader;spec.loader.exec_module(reader)
session,config,backend,world=completion['outcomes']['observation']['backend_identity'];traces={}
for item in facts['files']:
 path=Path(item['path']);st=path.stat();assert (st.st_dev,st.st_ino,st.st_size)==(item['device'],item['inode'],item['size'])
 expected={'collection':session,'session':session,'backend':backend,'config':config,'world':world,'clock':ctx['clock'],'role':item['role'],'provenance':ctx['provenance']}
 result=reader.read_after_join(path,expected=expected,requested_window=(next(e['steady_time_ns'] for e in rows if e['event']=='codex_review_validated'),status_times[-1]),clock_verified=True)
 assert result.structure_valid and result.coverage_complete,(item['role'],result.issues)
 kinds={}
 for record in result.records:
  if record[1]==2 and record[4]:kinds[record[4][0]]=kinds.get(record[4][0],0)+1
 traces[item['role']]={'sha256':h(path),'records':len(result.records),'structure_valid':result.structure_valid,'file_window_coverage':result.coverage_complete,'issues':result.issues,'event_counts':kinds,'begin_ns':result.records[0][2],'end_ns':result.records[-1][2]}
result={'run_id':d.name,'source_commit':terminal['source_commit'],'observation':completion['outcomes']['observation'],'evaluator_max_gap_ns':gap(status_times),'clock_max_gap_ns':gap(clock_times),'terminal':terminal,'consume_to_exit_s':(terminal['process_exit_ns_upper_bound']-consumed['at_ns'])/1e9,'cleanup_ack':cleanup['publication'],'process_residue':cleanup['process_residue'],'task_residue':cleanup['task_residue'],'outer_cgroup_absent':not outer['remaining_cgroup_exists'],'screenshot_sha256':h(d/'gui.png'),'review_sha256':h(d/'codex-review.json'),'traces':traces,'clock_domain_certificate_sha256':h(d/'cleanup.json'),'trace_requested_window':'review accepted through last validated status; startup callbacks before observer BEGIN are excluded','clock_error_bound':'NOT_CLAIMED','historical_RUN008_cause':'UNKNOWN'}
(r/'gui-final-raw-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
