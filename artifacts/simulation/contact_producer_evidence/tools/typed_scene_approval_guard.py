#!/usr/bin/env python3
"""Atomic approval-bound capacity-one guard for S3.3.31; no runtime APIs."""
from __future__ import annotations
import hashlib, json, os, shutil, tempfile
from pathlib import Path
from typing import Any

AUTHORIZED="authorized_not_consumed"; CONSUMED="consumed"
def canonical(value: dict[str, Any]) -> bytes: return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))+"\n").encode()
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path: Path):
    try:
        value=json.loads(path.read_text(encoding="utf-8"))
        return (isinstance(value,dict), value if isinstance(value,dict) else None, "ready" if isinstance(value,dict) else "malformed guard")
    except (OSError,json.JSONDecodeError) as exc: return False,None,f"malformed guard: {type(exc).__name__}"
def validate(record: dict[str,Any], context:dict[str,Any], authorized:bool):
    for key in ("schema","approval_id","packet_path","packet_sha256","helper_sha256","world","world_sha256","literals","capacity"):
        if record.get(key)!=context.get(key): return False,f"guard mismatch: {key}"
    if record.get("state") not in (AUTHORIZED,CONSUMED): return False,"malformed guard: state"
    if authorized and record.get("state")!=AUTHORIZED: return False,"approval already consumed"
    return True,"ready"
def atomic_replace(path:Path,value:dict[str,Any]):
    temporary=path.with_name("."+path.name+".tmp."+str(os.getpid()))
    try:
        with temporary.open("xb") as f: f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
        os.replace(temporary,path); return True,"ready"
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False,f"atomic-write failure: {type(exc).__name__}"
def initialize(path:Path,context:dict[str,Any],created_at:str):
    path.parent.mkdir(parents=True,exist_ok=True)
    record=dict(context); record.update({"state":AUTHORIZED,"created_at_utc":created_at,"run_id":None,"consumed_at_utc":None,"final_status":None})
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,"wb") as f: f.write(canonical(record)); f.flush(); os.fsync(f.fileno())
        return True,"ready"
    except FileExistsError:
        ok,old,reason=load(path); return validate(old,context,False) if ok and old else (False,reason)
    except OSError as exc: return False,f"atomic-write failure: {type(exc).__name__}"
def acquire(path:Path,context:dict[str,Any]):
    ok,record,reason=load(path)
    if not ok or record is None: return False,reason,None
    ok,reason=validate(record,context,True)
    if not ok:return False,reason,None
    lock=path.with_name(path.name+".lock")
    try: lock.mkdir()
    except OSError as exc:return False,f"lock failure: {type(exc).__name__}",None
    ok,record,reason=load(path)
    if not ok or record is None or not validate(record,context,True)[0]:
        shutil.rmtree(lock,ignore_errors=True); return False,reason if not ok else validate(record,context,True)[1],None
    return True,"ready",lock
def consume(path:Path,lock:Path,context:dict[str,Any],run_id:str,status:str,when:str):
    if not lock.is_dir() or not run_id or not status:return False,"consumption precondition failed"
    ok,record,reason=load(path)
    if not ok or record is None:return False,reason
    ok,reason=validate(record,context,True)
    if not ok:return False,reason
    record.update({"state":CONSUMED,"run_id":run_id,"final_status":status,"consumed_at_utc":when})
    ok,reason=atomic_replace(path,record)
    if ok: lock.rmdir()
    return ok,reason
def offline_self_test():
    context={"schema":"s3_d3_typed_scene_guard/v1","approval_id":"S3.3.31_TYPED_SCENE_OBSERVER_RUN","packet_path":"docs/x.md","packet_sha256":"a"*64,"helper_sha256":"b"*64,"world":"world_demo","world_sha256":"c"*64,"literals":{"capacity":1},"capacity":1}
    with tempfile.TemporaryDirectory() as raw:
        root=Path(raw); old=root/'old.json'; old_bytes=b'{"old":true}\n'; old.write_bytes(old_bytes); guard=root/'g.json'
        results={}; ok,why=initialize(guard,context,"2026-09-27T00:00:00Z"); results['initialize']=ok
        results['old_unchanged']=old.read_bytes()==old_bytes
        ok,why,lock=acquire(guard,context); results['acquire_once']=ok
        results['consume']=bool(ok and lock and consume(guard,lock,context,"run","INVALID","2026-09-27T00:00:01Z")[0])
        results['second_acquire_rejected']=not acquire(guard,context)[0]
        mismatch=dict(context); mismatch['packet_sha256']='d'*64; results['packet_mismatch_rejected']=not initialize(guard,mismatch,"x")[0]
        mismatch=dict(context); mismatch['helper_sha256']='d'*64; results['helper_mismatch_rejected']=not initialize(guard,mismatch,"x")[0]
        mismatch=dict(context); mismatch['world_sha256']='d'*64; results['world_mismatch_rejected']=not initialize(guard,mismatch,"x")[0]
        mismatch=dict(context); mismatch['literals']={'capacity':2}; results['literal_mismatch_rejected']=not initialize(guard,mismatch,"x")[0]
        bad=root/'bad.json'; bad.write_text('bad'); results['malformed_rejected']=not acquire(bad,context)[0]
        locked=root/'locked.json'; initialize(locked,context,"x"); locked.with_name(locked.name+'.lock').mkdir(); results['lock_rejected']=not acquire(locked,context)[0]
        parent=root/'parent'; parent.write_text('x'); results['atomic_failure_rejected']=not atomic_replace(parent/'child',{"x":1})[0]
        passed=all(results.values()); return passed,results
if __name__=='__main__':
    ok,result=offline_self_test(); print(json.dumps({"passed":ok,"results":result},sort_keys=True)); raise SystemExit(0 if ok else 1)
