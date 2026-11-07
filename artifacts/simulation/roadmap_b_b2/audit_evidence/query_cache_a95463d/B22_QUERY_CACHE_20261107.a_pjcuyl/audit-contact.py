from pathlib import Path
import json,hashlib,re,sys
r=Path(Path('/tmp/b22-query-cache-current-root').read_text().strip());d=r/'B22_CONTACT_QUERY_CACHE_VERIFY_001'
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=json.loads((d/'contact-proof.json').read_text());b=json.loads((d/'bindings.json').read_text());c=json.loads((d/'cleanup.json').read_text());completion=json.loads((d/'completion.json').read_text());terminal=json.loads((d/'completion-acceptance.json').read_text());batch=json.loads((d/'cleanup-batch.json').read_text());outer=json.loads((r/'contact-001-outer-cleanup.json').read_text());events=[json.loads(l) for l in (d/'observation.jsonl').read_text().splitlines()]
assert h(d/'observation.jsonl')==completion['stream_sha256'];assert c['publication']['batch_id']==batch['batch_id'] and c['publication']['acknowledged']
assert c['process_residue']==c['task_residue']=='NONE' and not c['cleanup_errors'];assert terminal['timing_verdict']=='PASS';assert not outer['remaining_cgroup_exists'] and not outer['scan_errors']
assert p['result']==3 and p['reason_code']==0 and p['binding_revision']==p['applied_binding_revision']==0
assert p['proof_session_id']==b['session_id'] and p['proof_backend_instance_id']==p['backend_instance_id']==completion['outcomes']['backend_instance_id']
assert p['proof_config_hash']==b['config_hash'] and p['proof_asset_manifest_sha256']==b['asset_manifest_sha256']
facts=[e['facts'] for e in events if e['event']=='owned_process_output']+ [dict(pairs) for event,pairs in batch['events'] if event=='owned_process_output']
texts=[re.sub(r'\x1b\[[0-9;]*m','',f.get('text','')) for f in facts]
samples=[];raw={};removal=[]
for t in texts:
 if 'B22_CONTACT_SAMPLE session=' in t:
  fields=dict(re.findall(r'(\w+)=([^ ]+)',t));samples.append(fields)
 if 'B22_CONTACT_RAW session=' in t:
  fields=dict(re.findall(r'(\w+)=([^ ]+)',t.split(' data=',1)[0]));raw[int(fields['iteration'])]={'fields':fields,'text':t}
 if 'B22_CONTACT_REMOVAL session=' in t:removal.append(dict(re.findall(r'(\w+)=([^ ]+)',t)))
assert len(removal)==1 and removal[0]['absent']==removal[0]['verified']=='1'
for s in samples+removal:assert s['session']==b['session_id'] and int(s['backend'])==p['backend_instance_id']
for phase,start,end in [('contact',p['contact_first_iteration'],p['contact_last_iteration']),('empty',p['empty_first_iteration'],p['empty_last_iteration'])]:
 selected=[s for s in samples if start<=int(s['iteration'])<=end];assert len(selected)>=3
 assert int(selected[-1]['stamp_ns'])-int(selected[0]['stamp_ns'])>=20_000_000
 for s in selected:
  assert s['component']==s['coverage']=='1';i=int(s['iteration']);assert i in raw and raw[i]['fields']['truncated']=='0'
  if phase=='contact':assert s['floor_pair']==s['normal_depth_valid']=='1' and 'normal {' in raw[i]['text'] and 'depth:' in raw[i]['text']
  else:assert s['floor_pair']=='0' and s['separated']=='1' and raw[i]['fields']['raw_bytes']=='0'
assert not any('residue_possible' in t or 'B22_CONTACT_FAILED iteration=' in t for t in texts)
requests=[e for e in events if e['event']=='contact_request'];assert any(e['facts']['kind']=='START' for e in requests) and any(e['facts']['kind']=='QUERY' for e in requests)
for e in requests:
 q=e['facts']['request']
 if 'operation' in q:
  for k in ('final_publisher_instance_id','safe_stop_publisher_instance_id','policy_publisher_instance_id','episode_generation','reset_epoch','runtime_generation','step_id'):
   if k in q:assert q[k]==0
final=[e for e in events if e['event']=='contact_final'][0]['facts'];assert all(s['inhibited'] and s['fault_flags']==0 for s in final['statuses'])
result={'run_id':d.name,'source_commit':terminal['source_commit'],'proof':p,'raw_samples':samples,'removal':removal,'cleanup_ack':c['publication'],'residue':outer,'terminal':terminal,'stream_sha256':h(d/'observation.jsonl'),'batch_sha256':h(d/'cleanup-batch.json'),'proof_sha256':h(d/'contact-proof.json'),'raw_lines_count':len(raw),'scope':'same inhibited fixture-only session; no B2.3 motion eligibility'}
(r/'contact-final-raw-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({'contact':p['contact_sample_count'],'empty':p['covered_empty_sample_count'],'removed_iteration':removal[0]['iteration'],'proof_sha256':result['proof_sha256']}))
