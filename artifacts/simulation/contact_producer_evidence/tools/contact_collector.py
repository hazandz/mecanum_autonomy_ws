#!/usr/bin/env python3
"""Passive-only raw Contacts collector. It creates subscriptions only."""
from __future__ import annotations
import argparse, base64, hashlib, json, signal, sys, time
from collections import Counter
from pathlib import Path
from typing import Any
import rclpy
from rclpy.node import Node
from rclpy.serialization import serialize_message
from ros_gz_interfaces.msg import Contacts
from rosgraph_msgs.msg import Clock
from rosidl_runtime_py.convert import message_to_ordereddict

RAW_TOPIC="/s3_d3/contact/raw"
CLOCK_TOPIC="/clock"
RAW_TYPE="ros_gz_interfaces/msg/Contacts"
CLOCK_TYPE="rosgraph_msgs/msg/Clock"
NAME="s3_d3_passive_contact_collector"

def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)+"\n", encoding="utf-8")

def pubinfo(node: Node, topic: str) -> list[dict[str, str]]:
    return sorted([{"node_name":x.node_name,"node_namespace":x.node_namespace,"topic_type":x.topic_type} for x in node.get_publishers_info_by_topic(topic)], key=lambda x:(x["node_namespace"],x["node_name"],x["topic_type"]))

def graph(node: Node) -> dict[str, Any]:
    return {"captured_steady_ns":time.monotonic_ns(),"collector_node":NAME,"topics":{n:sorted(t) for n,t in node.get_topic_names_and_types()},"raw_topic_publishers":pubinfo(node,RAW_TOPIC),"clock_topic_publishers":pubinfo(node,CLOCK_TOPIC),"cmd_vel_publishers":pubinfo(node,"/cmd_vel")}

def stamp_ns(stamp: Any) -> int | None:
    sec=getattr(stamp,"sec",None); nano=getattr(stamp,"nanosec",None)
    if isinstance(sec,int) and not isinstance(sec,bool) and isinstance(nano,int) and not isinstance(nano,bool): return sec*1_000_000_000+nano
    return None

def ready(snapshot: dict[str, Any]) -> tuple[bool, str]:
    if snapshot["topics"].get(RAW_TOPIC,[]) != [RAW_TYPE]: return False, "raw topic type mismatch"
    if snapshot["topics"].get(CLOCK_TOPIC,[]) != [CLOCK_TYPE]: return False, "clock topic type mismatch"
    if len(snapshot["raw_topic_publishers"]) != 1: return False, "expected exactly one raw Contacts publisher"
    if any(x["node_name"]==NAME for x in snapshot["cmd_vel_publishers"]): return False, "collector appears as /cmd_vel publisher"
    return True, "ready"

class Collector(Node):
    def __init__(self, run: Path) -> None:
        super().__init__(NAME); self.contacts=0; self.clocks=0; self.hashes=Counter(); self.cardinality=[]
        self.raw=(run/"raw_contacts.jsonl").open("w",encoding="utf-8"); self.clock=(run/"clock_trace.jsonl").open("w",encoding="utf-8")
        self.create_subscription(Contacts,RAW_TOPIC,self.on_contact,100)
        self.create_subscription(Clock,CLOCK_TOPIC,self.on_clock,100)
    def on_contact(self,msg: Contacts) -> None:
        cdr=serialize_message(msg); digest=hashlib.sha256(cdr).hexdigest(); count=len(msg.contacts); self.hashes[digest]+=1; self.cardinality.append(count)
        value={"stream":"contacts","receive_index":self.contacts,"received_steady_ns":time.monotonic_ns(),"aggregate_header_stamp_ns":stamp_ns(msg.header.stamp),"contact_count":count,"payload_sha256":digest,"payload_cdr_base64":base64.b64encode(cdr).decode("ascii"),"payload":message_to_ordereddict(msg)}
        self.raw.write(json.dumps(value,ensure_ascii=True,sort_keys=True)+"\n"); self.raw.flush(); self.contacts+=1
    def on_clock(self,msg: Clock) -> None:
        self.clock.write(json.dumps({"stream":"clock","receive_index":self.clocks,"received_steady_ns":time.monotonic_ns(),"clock_ns":stamp_ns(msg.clock)},ensure_ascii=True,sort_keys=True)+"\n"); self.clock.flush(); self.clocks+=1
    def close(self) -> None: self.raw.close(); self.clock.close()

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--run-dir",required=True); ap.add_argument("--preflight-seconds",type=float,default=90.0); ap.add_argument("--capture-seconds",type=float,default=30.0); args=ap.parse_args()
    run=Path(args.run_dir); run.mkdir(parents=True,exist_ok=True); rclpy.init(); node=Collector(run); interrupted=False
    def stop(_s: int,_f: Any) -> None:
        nonlocal interrupted; interrupted=True
    signal.signal(signal.SIGINT,stop)
    try:
        dump(run/"graph_pre_initial.json",graph(node)); snap=graph(node); good=False; reason="preflight timeout"; end=time.monotonic()+args.preflight_seconds
        while time.monotonic()<end and not interrupted:
            rclpy.spin_once(node,timeout_sec=0.2); snap=graph(node); good,reason=ready(snap)
            if good: dump(run/"graph_pre.json",snap); break
        dump(run/"collector_preflight.json",{"ready":good,"reason":reason,"captured_steady_ns":time.monotonic_ns()})
        if not good:
            dump(run/"collector_summary.json",{"status":"INVALID","reason":reason,"contacts_payloads":node.contacts,"clock_messages":node.clocks}); return 2
        allow=snap["cmd_vel_publishers"]; end=time.monotonic()+args.capture_seconds
        while time.monotonic()<end and not interrupted: rclpy.spin_once(node,timeout_sec=0.2)
        post=graph(node); dump(run/"graph_post.json",post); good,reason=ready(post)
        if post["cmd_vel_publishers"] != allow: good=False; reason="frozen /cmd_vel publisher allowlist changed"
        summary={"status":"VALID" if good and not interrupted else "INVALID","reason":"capture complete" if good and not interrupted else ("interrupted" if interrupted else reason),"contacts_payloads":node.contacts,"clock_messages":node.clocks,"aggregate_empty_payloads":sum(n==0 for n in node.cardinality),"max_contacts_per_payload":max(node.cardinality,default=0),"duplicate_payload_hashes":{k:v for k,v in node.hashes.items() if v>1},"frozen_cmd_vel_allowlist":allow,"collector_created_publishers":[],"collector_created_service_clients":[],"collector_created_action_clients":[]}
        dump(run/"collector_summary.json",summary); return 0 if summary["status"]=="VALID" else 3
    finally:
        node.close(); node.destroy_node(); rclpy.shutdown()
if __name__=="__main__": sys.exit(main())
