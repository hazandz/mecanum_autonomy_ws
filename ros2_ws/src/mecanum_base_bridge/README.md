# mecanum_base_bridge

The development package remains at version `0.3.0`; the U2 transport changes
below are unreleased. Release versioning will be reconciled during U7. The
package contains three distinct pieces:

- The UART v1 codec (`uart_v1_codec.py`) encodes and validates byte frames
  against the contract and golden vectors.
- The existing `sim_eval` source provides offline-only wheel/IMU ingress
  components and its launch entry point; this does not imply hardware or
  production runtime eligibility.
- `SerialTransport` is the U2 offline implementation of bounded raw-byte
  serial I/O. It owns one explicitly supplied port and does not implement
  protocol framing, session validation, ROS endpoints, or command state.

`SerialTransport(port, serial_factory=None, monotonic=time.monotonic)` does not
open a device during import or construction. `open()` applies 115200/8N1,
disables software and hardware flow control, uses nonblocking reads,
`write_timeout=0.020`, and requires exclusive access. A reconnect attempt made
before the one-second monotonic backoff expires returns `False`; after the
deadline the caller may call `open()` again.

Each `read()` returns at most 512 raw bytes (`b''` means no bytes available).
Each `write()` sends the exact caller-provided bytes in one call and accepts at
most `MAX_WIRE_FRAME_LENGTH`; short writes and serial errors close the handle
and are reported to the caller without replay.

Offline tests use only fake serial backends and a fake monotonic clock. They
provide no evidence of STM32 behavior or A1 handshake compliance. The U2
evidence level is `OFFLINE_ONLY`: production ROS/session behavior, HIL,
hardware validation, motor enable, and deployment have not been implemented
or authorized by this transport candidate. The physical port name and UART
wiring must be independently verified on the target machine before a future
separately authorized runtime activity.

The normative byte contract and expected vectors remain in
`docs/Pi_STM32_Interface_Contract.md` and
`docs/Pi_STM32_UART_v1_Golden_Vectors.md`. Passing codec or transport tests
does not establish the complete L2 design, runtime approval, HIL, motor safety,
or deployment readiness.
