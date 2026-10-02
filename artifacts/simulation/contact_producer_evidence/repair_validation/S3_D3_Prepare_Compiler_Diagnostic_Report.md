# S3 D3 Prepare Compiler Diagnostic Report

## Scope and result

`COMPILE_REPRODUCTION_FAIL`

This offline-only diagnostic reproduced the prerequisite subprocess sequence in `RuntimeDependencyFactory.compile_helper()` without running the helper binary, Gazebo, ROS, a launch process, a service request, or any guard operation.

## Guard read-only check

S3.3.54 was read only and remained:

| Field | Observed value |
| --- | --- |
| `state` | `authorized_not_consumed` |
| `capacity` | `1` |
| `run_id` | `null` |
| `final_status` | `null` |
| `consumed_at_utc` | `null` |

## Reproduced command sequence

Helper source SHA-256: `ff6cc497ce845e136469f8cc026c8d6076c129da39f53591072d3b62e6241424`.

| Tool | Version | Exit code |
| --- | --- | --- |
| `/usr/bin/pkg-config` | `1.8.1` | `0` for `--version` |
| `/usr/bin/g++` | `g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` | `0` for `--version` |

The first prerequisite command used by `compile_helper()` was reproduced exactly:

```text
/usr/bin/pkg-config --cflags --libs gz-transport13 gz-msgs10
```

It returned exit code `1`; stdout was empty and stderr was:

```text
Package gz-transport13 was not found in the pkg-config search path.
Perhaps you should add the directory containing `gz-transport13.pc`
to the PKG_CONFIG_PATH environment variable
Package 'gz-transport13', required by 'virtual:world', not found
Package 'gz-msgs10', required by 'virtual:world', not found
```

The independent OpenSSL prerequisite command was also captured:

```text
/usr/bin/pkg-config --cflags --libs openssl
```

It returned exit code `0`, stdout `-lssl -lcrypto `, and empty stderr.

No `g++` argv was formed or invoked because the required Gazebo pkg-config prerequisite failed. The intended compiler argv would only be assembled after both pkg-config calls returned zero.

## Logic assessment

`prepare()` creates a temporary directory, calls `compile_helper()`, and cleans the temporary directory when that call raises. `execute_guarded()` invokes `prepare()` before trusted-context build and guard acquisition. Therefore this prerequisite failure is a concrete offline explanation for `INVALID_PREPARE` when the supervisor inherits the same pkg-config environment. It does not establish that the prior supervisor invocation reached that exact branch, because the supervisor does not persist a pre-acquisition terminal diagnostic.

## Temporary-output handling

The reproduction used `/tmp/s3-d3-prepare-compile-7ctbrpls`; no binary was produced, and the directory was removed after capture.

## Non-claims

This report does not alter the guard, packet, source, launch, world, or runtime configuration. It does not run or prove Gazebo, ROS, spawning, Scene service availability, hierarchy identity, collision, ContactLatch, reward, training, or hardware behavior.

## Smallest next fix candidate

`REQUIRES_EXPLICIT_APPROVAL`: make the future supervisor establish and validate the version-matched Gazebo pkg-config environment before `prepare()`, while preserving fail-closed behavior and without using log parsing or a retry. No such change was made here.
