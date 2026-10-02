#!/usr/bin/env python3
"""Offline-only summary for lossless S3 D3 raw Contacts traces."""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

def rows(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--run-dir",required=True); args=ap.parse_args()
    run=Path(args.run_dir); contacts=rows(run/"raw_contacts.jsonl"); clocks=rows(run/"clock_trace.jsonl")
    hashes=Counter(x["payload_sha256"] for x in contacts)
    pairs=[]
    for row in contacts:
        for contact in row.get("payload",{}).get("contacts",[]):
            pairs.append({"collision1":contact.get("collision1",{}),"collision2":contact.get("collision2",{})})
    out={"contacts_payloads":len(contacts),"clock_messages":len(clocks),"header_stamp_present_payloads":sum(x.get("aggregate_header_stamp_ns") is not None for x in contacts),"empty_aggregate_payloads":sum(x.get("contact_count",0)==0 for x in contacts),"max_contacts_per_payload":max((x.get("contact_count",0) for x in contacts),default=0),"duplicate_payload_hashes":{k:v for k,v in hashes.items() if v>1},"observed_contact_pairs":pairs}
    (run/"analysis_summary.json").write_text(json.dumps(out,ensure_ascii=True,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
