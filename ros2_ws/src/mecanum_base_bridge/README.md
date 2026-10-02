# mecanum_base_bridge — Phase A codec-only

Status: PROPOSED_FOR_APPROVAL.

This package is a pure-Python implementation of the UART v1 byte codec and its
golden-vector unit tests. It accepts and returns bytes and packet dataclasses
only. It does not import rclpy, open a serial device, create a ROS node,
publish or subscribe to a topic, transmit UART bytes, or perform any motor,
kinematics, odometry, watchdog, or safety-runtime action.

The normative transport definition remains
docs/Pi_STM32_Interface_Contract.md. The golden vectors in
docs/Pi_STM32_UART_v1_Golden_Vectors.md are the independent expected-byte test
specification. Passing these tests is codec evidence only; it is not UART
runtime, HIL, motor-enable, or deployment approval.

The 96-byte raw-frame and 98-byte delimiter-inclusive COBS receive-buffer
limits are enforced without truncation or partial parsing.
