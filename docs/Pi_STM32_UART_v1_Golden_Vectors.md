# Pi–STM32 UART v1 Golden Vectors

**Status:** `PROPOSED_FOR_APPROVAL`

## 1. Scope, authority, and non-goals

This is a derived test specification for the Pi bridge and STM32 UART codecs.
It does not replace
[`Pi_STM32_Interface_Contract.md`](Pi_STM32_Interface_Contract.md); that
contract remains authoritative for protocol behavior. The authoritative system
documents remain `MECANUM_NAV_DRL_Architecture.docx` and
`MECANUM_NAV_DRL_Project_Tree.txt`.

The vectors provide deterministic payload, raw-frame, CRC, and wire-frame
bytes so both codecs can produce and decode the same UART v1 stream. They do
not authorize motor enable, physical UART operation, PWM, PID, encoder
hardware, E-stop, or HIL. `approval.yaml` is `DRAFT`, its motor permission is
false, and every implementation must remain fail-closed.

All hexadecimal bytes in this document are lowercase and separated by one
space. A multi-byte field uses little-endian order.

## 2. Locked protocol inputs used by every vector

| Item | Value |
| --- | --- |
| `protocol_version` | `0x0001` |
| Raw header | `uint16_le protocol_version`, `uint8 message_type`, `uint8 payload_length_bytes` |
| Raw frame | `header + payload + crc16_le` |
| Wire frame | `COBS(raw_frame) + trailing 00` |
| COBS delimiter | `00` |
| CRC | CRC-16/CCITT-FALSE: poly `0x1021`, init `0xffff`, refin false, refout false, xorout `0x0000` |
| Byte order | little-endian |
| `COMMAND` | `0x01` |
| `TELEMETRY` | `0x02` |
| `CONFIG` | `0x03` |
| `CONFIG_ACCEPTED` | `0x01` |
| `CONFIG_REJECTED` | `0x02` |
| `REJECT_NONE` | `0x00` |
| `REJECT_HASH_MISMATCH` | `0x01` |
| `REJECT_LOCAL_CONFIG_INVALID` | `0x02` |

CRC self-check: the ASCII bytes for `123456789` MUST produce CRC
`0x29b1`.

### Frame and buffer limits

| Frame | Payload | Raw frame | Maximum wire frame |
| --- | --- | --- | --- |
| COMMAND | 20 bytes | 26 bytes | 28 bytes |
| TELEMETRY | 65 bytes | 71 bytes | 73 bytes |
| CONFIG_REQUEST | 40 bytes | 46 bytes | 48 bytes |
| CONFIG_STATUS | 50 bytes | 56 bytes | 58 bytes |

Raw-frame storage MUST be at least 96 bytes. The receive COBS buffer, including
delimiter capacity, MUST be at least 98 bytes. A frame exceeding these limits
must be rejected safely without truncation or watchdog refresh.

### Test-only hardware hash

Every CONFIG vector uses this test-only 32-byte value:

```text
00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f
10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f
```

It is not the digest of the real hardware manifest and MUST NOT be used for
motor enable. A hash-mismatch vector assumes STM32's local generated hash is
different from this test fixture while CONFIG_STATUS correctly echoes the
Pi-sent bytes.

## 3. Valid vectors

### V1 COMMAND valid positive and negative twist

Purpose: verify float32 little-endian encoding and a valid periodic COMMAND.

| Field | Value |
| --- | --- |
| `command_sequence` | `0x10203040` |
| `reset_epoch` | `0x11223344` |
| `vx_mps` | `1.25` |
| `vy_mps` | `-0.5` |
| `wz_radps` | `0.75` |

```text
payload hex (20 bytes)
40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 01 14 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f 30 6e

crc value
0x6e30

wire frame COBS hex (28 bytes)
02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 30 6e 00
```

Expected decoded fields equal the table above. Given an accepted CONFIG session
with epoch `0x11223344` and a previously lower sequence, STM32 accepts the
COMMAND, updates `last_accepted_command_sequence` to `0x10203040`, and refreshes
the watchdog. It sends no response frame.

### V2 CONFIG_REQUEST valid

Purpose: verify the 40-byte request and raw 32-byte hash transport.

| Field | Value |
| --- | --- |
| `config_sequence` | `0x01020304` |
| `reset_epoch` | `0x11223344` |
| `hardware_config_hash` | test-only bytes `00` through `1f` |

```text
payload hex (40 bytes)
04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f

raw frame hex (46 bytes)
01 00 03 28 04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 7b e7

crc value
0xe77b

wire frame COBS hex (48 bytes)
02 01 0b 03 28 04 03 02 01 44 33 22 11 22 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 7b e7 00
```

Expected decoded fields equal the table above. If local configuration is valid
and has the same hash, STM32 accepts this epoch, clears accepted command state,
requests motor disable, enters `CONFIG_ACCEPTED_MOTOR_DISABLED`, and sends one
CONFIG_STATUS. This request alone never enables motor output.

### V3 CONFIG_STATUS accepted

Purpose: verify the 50-byte accepted status and `mcu_boot_id` echo binding.

| Field | Value |
| --- | --- |
| `config_sequence` | `0x01020304` |
| `reset_epoch` | `0x11223344` |
| `hardware_config_hash` | test-only bytes `00` through `1f` |
| `mcu_boot_id` | `0x0102030405060708` |
| `config_status` | `CONFIG_ACCEPTED = 0x01` |
| `reject_reason` | `REJECT_NONE = 0x00` |

```text
payload hex (50 bytes)
04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 01 00

raw frame hex (56 bytes)
01 00 03 32 04 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 01 00 a7 93

crc value
0x93a7

wire frame COBS hex (58 bytes)
02 01 0b 03 32 04 03 02 01 44 33 22 11 29 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 01 03 a7 93 00
```

Expected decoded fields equal the table above. Pi treats the handshake as
successful only if this is the status for its transmitted request and its most
recent valid TELEMETRY has the same `mcu_boot_id`.

### V4 CONFIG_STATUS rejected hash mismatch

Purpose: verify a valid status frame reporting hash mismatch, rather than a
codec drop.

| Field | Value |
| --- | --- |
| `config_sequence` | `0x01020305` |
| `reset_epoch` | `0x11223344` |
| `hardware_config_hash` | echoed test-only bytes `00` through `1f` |
| `mcu_boot_id` | `0x0102030405060708` |
| `config_status` | `CONFIG_REJECTED = 0x02` |
| `reject_reason` | `REJECT_HASH_MISMATCH = 0x01` |

```text
payload hex (50 bytes)
05 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 01

raw frame hex (56 bytes)
01 00 03 32 05 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 01 a3 c4

crc value
0xc4a3

wire frame COBS hex (58 bytes)
02 01 0b 03 32 05 03 02 01 44 33 22 11 2c 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 01 a3 c4 00
```

Expected decoded fields equal the table above. Pi does not establish a control
session and sends no COMMAND. STM32 retains its prior accepted session state.

### V5 CONFIG_STATUS rejected local configuration invalid

Purpose: verify a valid status frame reporting invalid local generated
configuration.

| Field | Value |
| --- | --- |
| `config_sequence` | `0x01020306` |
| `reset_epoch` | `0x11223344` |
| `hardware_config_hash` | echoed test-only bytes `00` through `1f` |
| `mcu_boot_id` | `0x0102030405060708` |
| `config_status` | `CONFIG_REJECTED = 0x02` |
| `reject_reason` | `REJECT_LOCAL_CONFIG_INVALID = 0x02` |

```text
payload hex (50 bytes)
06 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 02

raw frame hex (56 bytes)
01 00 03 32 06 03 02 01 44 33 22 11 00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 02 5a c2

crc value
0xc25a

wire frame COBS hex (58 bytes)
02 01 0b 03 32 06 03 02 01 44 33 22 11 2c 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 17 18 19 1a 1b 1c 1d 1e 1f 08 07 06 05 04 03 02 01 02 02 5a c2 00
```

Expected decoded fields equal the table above. Pi does not establish a control
session. Motor output remains disabled.

### V6 TELEMETRY valid mixed-sign cumulative ticks

Purpose: verify all telemetry fields, FL/FR/RL/RR order, int64 sign encoding,
and a permitted combined fault bitmap.

| Field | Value |
| --- | --- |
| `telemetry_sequence` | `0x0a0b0c0d` |
| `mcu_boot_id` | `0x0102030405060708` |
| `reset_epoch` | `0x11223344` |
| `mcu_monotonic_time_us` | `0x0001020304050607` |
| `ticks_fl` | `123456789` |
| `ticks_fr` | `-42` |
| `ticks_rl` | `9876543210` |
| `ticks_rr` | `-9876543210` |
| `last_accepted_command_sequence` | `0x10203040` |
| `mcu_fault_bits` | `2050 = FAULT_ESTOP_ACTIVE (2) | FAULT_MOTOR_DRIVER (2048)` |
| `estop_aux_active` | `1` |

```text
payload hex (65 bytes)
0d 0c 0b 0a 08 07 06 05 04 03 02 01 44 33 22 11 07 06 05 04 03 02 01 00 15 cd 5b 07 00 00 00 00 d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 00 00 00 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 00 00 01

raw frame hex (71 bytes)
01 00 02 41 0d 0c 0b 0a 08 07 06 05 04 03 02 01 44 33 22 11 07 06 05 04 03 02 01 00 15 cd 5b 07 00 00 00 00 d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 00 00 00 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 00 00 01 dd 12

crc value
0x12dd

wire frame COBS hex (73 bytes)
02 01 1a 02 41 0d 0c 0b 0a 08 07 06 05 04 03 02 01 44 33 22 11 07 06 05 04 03 02 01 05 15 cd 5b 07 01 01 01 0e d6 ff ff ff ff ff ff ff ea 16 b0 4c 02 01 01 0f 16 e9 4f b3 fd ff ff ff 40 30 20 10 02 08 01 04 01 dd 12 00
```

Expected decoded fields equal the table above. Pi bridge validates the sequence,
boot ID, epoch, and monotonic time before calculating deltas. The acknowledgement
field proves only accepted UART COMMAND receipt, never applied PWM or achieved
motion.

## 4. Invalid vectors

All codec/frame failures below are safe drops: no watchdog refresh and no
CONFIG_STATUS response. Semantic COMMAND failures are decoded frames that must
be rejected without updating `last_accepted_command_sequence`, without watchdog
refresh, and without a response frame.

### I1 CRC wrong

```text
payload hex (20 bytes)
40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes; stored CRC is intentionally wrong)
01 00 01 14 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f 31 6e

stored CRC value
0x6e31

wire frame COBS hex (28 bytes)
02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 31 6e 00
```

The receiver decodes COBS but computes `0x6e30`, not stored `0x6e31`; it drops
the frame safely.

### I2 COBS malformed

```text
wire frame COBS hex (2 bytes)
02 00
```

COBS code `02` requires one following data byte, but none exists before the
delimiter. There is no payload, raw frame, or CRC to decode. The receiver drops
it safely.

### I3 Payload length mismatch

```text
payload hex (20 physical bytes; header claims 19)
40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 01 13 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f b0 67

crc value
0x67b0

wire frame COBS hex (28 bytes)
02 01 0b 01 13 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f b0 67 00
```

COBS and CRC are valid, but the header length is not COMMAND's exact 20-byte
length. This is a frame/codec drop, not a semantic command rejection.

### I4 Unsupported protocol version

```text
payload hex (20 bytes)
40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
02 00 01 14 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f 35 37

crc value
0x3735

wire frame COBS hex (28 bytes)
02 02 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 35 37 00
```

The decoded `protocol_version` is `0x0002`, so the receiver drops it safely.

### I5 Unknown message type

```text
payload hex (20 bytes)
40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 7f 14 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f d3 4e

crc value
0x4ed3

wire frame COBS hex (28 bytes)
02 01 0b 7f 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f d3 4e 00
```

The decoded `message_type` is `0x7f`, which is not COMMAND, TELEMETRY, or
CONFIG. The receiver drops it safely.

### I6 COMMAND NaN

Precondition: CONFIG is accepted for epoch `0x11223344`; last accepted command
sequence is `0x10203040`.

```text
payload hex (20 bytes; vx is float32 quiet NaN)
41 30 20 10 44 33 22 11 00 00 c0 7f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 01 14 41 30 20 10 44 33 22 11 00 00 c0 7f 00 00 00 bf 00 00 40 3f 4d 4f

crc value
0x4f4d

wire frame COBS hex (28 bytes)
02 01 0b 01 14 41 30 20 10 44 33 22 11 01 03 c0 7f 01 01 02 bf 01 05 40 3f 4d 4f 00
```

Codec decoding succeeds, but semantic validation rejects non-finite `vx_mps`.

### I7 COMMAND duplicate sequence

Precondition: CONFIG is accepted for epoch `0x11223344`; last accepted command
sequence is `0x10203040`.

```text
payload hex (20 bytes)
40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 01 14 40 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f 30 6e

crc value
0x6e30

wire frame COBS hex (28 bytes)
02 01 0b 01 14 40 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 30 6e 00
```

Semantic validation rejects the duplicate sequence.

### I8 COMMAND backward sequence

Precondition: CONFIG is accepted for epoch `0x11223344`; last accepted command
sequence is `0x10203040`.

```text
payload hex (20 bytes)
3f 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 01 14 3f 30 20 10 44 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f 08 5b

crc value
0x5b08

wire frame COBS hex (28 bytes)
02 01 0b 01 14 3f 30 20 10 44 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f 08 5b 00
```

Semantic validation rejects the backward sequence.

### I9 COMMAND wrong reset epoch

Precondition: CONFIG is accepted for epoch `0x11223344`; last accepted command
sequence is `0x10203040`.

```text
payload hex (20 bytes)
41 30 20 10 45 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f

raw frame hex (26 bytes)
01 00 01 14 41 30 20 10 45 33 22 11 00 00 a0 3f 00 00 00 bf 00 00 40 3f a7 f3

crc value
0xf3a7

wire frame COBS hex (28 bytes)
02 01 0b 01 14 41 30 20 10 45 33 22 11 01 03 a0 3f 01 01 02 bf 01 05 40 3f a7 f3 00
```

The decoded epoch is `0x11223345`, so semantic validation rejects it without
changing the accepted sequence or watchdog.

## 5. Expected receiver behavior summary

| Category | Cases | Expected behavior |
| --- | --- | --- |
| Frame/codec drop | I1 through I5 | Drop safely; no watchdog refresh; no CONFIG_STATUS response. |
| Semantic COMMAND reject | I6 through I9 | Reject after decode; no accepted-sequence update; no watchdog refresh; no response frame. |
| CONFIG hash mismatch | V4 behavior | Decoded valid CONFIG request returns CONFIG_REJECTED / REJECT_HASH_MISMATCH. |
| CONFIG local config invalid | V5 behavior | Decoded valid CONFIG request returns CONFIG_REJECTED / REJECT_LOCAL_CONFIG_INVALID. |

## 6. How to use these vectors

| Check | Expected result |
| --- | --- |
| Pi codec encode | Produces exactly the listed `wire frame COBS hex`. |
| STM32 codec encode | Produces exactly the same listed bytes. |
| Pi and STM32 decoder | Restores all listed valid fields with the stated numeric values. |
| Error tests | Produce the stated safe drop or semantic reject behavior. |
| Out of scope | No physical UART, PWM, PID, hardware encoder, E-stop, motor, or HIL validation is performed. |

## 7. Reference verification record

All hexadecimal values were generated by a temporary reference implementation
outside the repository. It implemented CRC-16/CCITT-FALSE and COBS, checked
the `123456789` CRC self-test, decoded every generated wire frame back to its
raw frame, verified valid-frame CRC values, and checked contract payload/raw/
wire sizes.

| Result | Value |
| --- | --- |
| Valid vectors verified | 6 |
| Invalid vectors verified | 9 |
| CRC self-check | `0x29b1` passed |
| Valid wire-frame COBS round-trip | passed |
| Contract payload/raw/wire-size checks | passed |

This verification is codec-only evidence. It is not approval, HIL evidence, or
permission to enable motors.
