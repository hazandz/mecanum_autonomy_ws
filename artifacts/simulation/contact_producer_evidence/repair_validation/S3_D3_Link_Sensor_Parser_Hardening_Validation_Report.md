# S3 D3 Link/Sensor Parser Hardening Validation Report

## Scope

This was an offline-only tooling repair. It did not launch Gazebo, ROS, `gz`, a bridge, a collector, a command/service/action path, or hardware. It created no approval packet, guard, authorization record, or diagnostic run. No robot Xacro, SDF, launch file, consumed packet, guard, or raw diagnostic artifact was edited.

## Defect repaired

The former shared `parse_named_output()` treated arbitrary successful stdout as evidence by testing whether an expected literal occurred as a substring, and treated the words `No` or `not` as parseable negative text. That could mistake near matches, warnings, logs, and error prose for link/sensor identity evidence.

The supervisor now has distinct `parse_link_output()` and `parse_sensor_output()` paths. Both require string stdout and stderr, exit code zero, no timeout, and no shutdown-incomplete flag before considering a record structurally usable. They use exact expected identities in retained metadata only; they do not coerce bytes with `str(...)`, use substring matching, fuzzy matching, scoped-name guesses, or negative keywords.

## Local grammar feasibility audit

The installed, version-matched wrapper at [`cmdmodel8.rb`](/opt/ros/jazzy/opt/gz_sim_vendor/lib/ruby/gz/cmdmodel8.rb) documents only selector invocation:

```text
gz model -m <model> -l <link>
gz model -m <model> -l <link> -s <sensor>
```

It states that `-l` selects a link and `-s` selects a sensor, then dispatches both to the compiled `cmdModelInfo` entry point. The installed local documentation/source inspected for this repair contains no stdout grammar or example response for either selector. It therefore provides no evidence for an exact positive link/sensor grammar or an exact negative "sensor absent" grammar.

Consequently the current parser records:

```text
NO_LOCAL_LINK_SENSOR_OUTPUT_GRAMMAR_CONFIRMED
```

for both selectors and returns `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY`. It cannot produce `SENSOR_ABSENT_AFTER_SPAWN` from any arbitrary query text. A future evidence-backed grammar is required before a positive identity or an absence result can be classified.

## Files changed

| File | Change |
| --- | --- |
| [`run_spawned_contactsensor_diagnostic.py`](../tools/run_spawned_contactsensor_diagnostic.py) | Replaced the shared substring/keyword parser with separate exact-identity link and sensor fail-closed parsers; added an in-memory offline self-test mode. |
| [`s3_d3_link_sensor_parser_self_test.json`](s3_d3_link_sensor_parser_self_test.json) | Recorded output of the offline parser self-test. |
| [`s3_d3_link_sensor_parser_self_test.exit_code`](s3_d3_link_sensor_parser_self_test.exit_code) | Recorded exit code `0`. |

## Offline fixture results

No fixture claims a positive identity or confirmed absence because no local grammar supports either claim. The self-test evaluated each of the following twelve in-memory records through both the link and sensor parsers, plus one source-level anti-substring/coercion guard: `25/25` assertions passed.

| Fixture | Required result | Result |
| --- | --- | --- |
| Exact link/sensor literal in otherwise unverified text | Incomplete; literal alone is not grammar | PASS |
| `base_link_extra` / `s3_d3_base_contact_sensor_backup` | Reject/incomplete | PASS |
| Warning text containing expected literal | Reject/incomplete | PASS |
| Empty stdout | Incomplete | PASS |
| Unstructured or malformed text | Incomplete | PASS |
| Nonzero exit | Incomplete before parsing | PASS |
| Timeout | Incomplete before parsing | PASS |
| Bytes/non-string stdout or stderr | Incomplete; no coercion | PASS |
| Negative result | No fixture created; no local negative grammar exists | PASS — omitted intentionally |
| Source anti-pattern guard | No shared substring parser or bytes coercion in named parsers | PASS |

## Validation commands

```text
python3 -m py_compile artifacts/simulation/contact_producer_evidence/tools/run_spawned_contactsensor_diagnostic.py
python3 artifacts/simulation/contact_producer_evidence/tools/run_spawned_contactsensor_diagnostic.py --offline-link-sensor-parser-self-test
```

Both commands exited `0`. The saved self-test result is valid JSON. Markdown, whitespace, and scoped diff checks were also run. No live command was invoked by either validation.

## Retained evidence and next gate

The consumed S3.3.20 artifact and approval authority remain untouched. In particular, this repair does not reinterpret its `DIAGNOSTIC_INCOMPLETE_SENSOR_QUERY` result and does not create or revive execution authority.

## Conclusion

**BLOCKED_BY_UNVERIFIED_LINK_SENSOR_CLI_OUTPUT**

The diagnostic tool is now safe against ambiguous textual inference, but it cannot classify a sensor as present or absent until a locally evidenced, version-matched `gz model` link/sensor output grammar is available. Any future runtime work requires a new user approval packet after that evidence or diagnostic interface design is established.
