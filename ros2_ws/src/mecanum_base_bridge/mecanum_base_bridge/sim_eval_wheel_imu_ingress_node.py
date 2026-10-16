"""ROS ingress node for the bounded sim_eval wheel and IMU interfaces."""

import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Imu, JointState

from mecanum_base_bridge.sim_eval_imu_normalizer import (
    ANGULAR_VELOCITY_COVARIANCE,
    IMU_FRAME_ID,
    LINEAR_ACCELERATION_COVARIANCE,
    ORIENTATION_COVARIANCE,
    ImuNormalizer,
)
from mecanum_base_bridge.sim_eval_wheel_odometry_emulator import WheelOdometryEmulator


def _stamp_ns(stamp):
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def _qos(reliability):
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=10,
        reliability=reliability,
        durability=DurabilityPolicy.VOLATILE,
    )


def _diagonal_covariance(values):
    result = [0.0] * 36
    for index, value in enumerate(values):
        result[index * 6 + index] = value
    return result


class SimEvalWheelImuIngressNode(Node):
    """Convert only the two authorized staging inputs to canonical outputs."""

    def __init__(self):
        super().__init__("sim_eval_wheel_imu_ingress")
        if not self.has_parameter("use_sim_time"):
            self.declare_parameter("use_sim_time", True)
        self._wheel = WheelOdometryEmulator()
        self._imu = ImuNormalizer()
        input_qos = _qos(ReliabilityPolicy.BEST_EFFORT)
        output_qos = _qos(ReliabilityPolicy.RELIABLE)
        self._wheel_publisher = self.create_publisher(Odometry, "/wheel/odometry_raw", output_qos)
        self._imu_publisher = self.create_publisher(Imu, "/imu/data", output_qos)
        self._wheel_subscription = self.create_subscription(
            JointState, "/sim_eval/wheel_joint_states", self._on_joint_state, input_qos
        )
        self._imu_subscription = self.create_subscription(Imu, "/sim_eval/imu_raw", self._on_imu, input_qos)

    def _on_joint_state(self, message):
        sample = self._wheel.process(message.name, message.velocity, _stamp_ns(message.header.stamp))
        if sample is None:
            return
        output = Odometry()
        output.header.stamp = message.header.stamp
        output.header.frame_id = "odom"
        output.child_frame_id = "base_link"
        output.pose.pose.position.x = sample.x
        output.pose.pose.position.y = sample.y
        output.pose.pose.position.z = 0.0
        output.pose.pose.orientation.z = math.sin(sample.yaw / 2.0)
        output.pose.pose.orientation.w = math.cos(sample.yaw / 2.0)
        output.twist.twist.linear.x = sample.linear_x
        output.twist.twist.linear.y = sample.linear_y
        output.twist.twist.linear.z = 0.0
        output.twist.twist.angular.z = sample.angular_z
        output.pose.covariance = list(sample.pose_covariance)
        output.twist.covariance = list(sample.twist_covariance)
        self._wheel_publisher.publish(output)

    def _on_imu(self, message):
        q = message.orientation
        angular = message.angular_velocity
        acceleration = message.linear_acceleration
        sample = self._imu.process(
            _stamp_ns(message.header.stamp),
            message.header.frame_id,
            (q.x, q.y, q.z, q.w),
            (angular.x, angular.y, angular.z),
            (acceleration.x, acceleration.y, acceleration.z),
        )
        if sample is None:
            return
        output = Imu()
        output.header.stamp = message.header.stamp
        output.header.frame_id = IMU_FRAME_ID
        output.orientation.x, output.orientation.y, output.orientation.z, output.orientation.w = sample.orientation_xyzw
        output.angular_velocity.x, output.angular_velocity.y, output.angular_velocity.z = sample.angular_velocity_xyz
        output.linear_acceleration.x, output.linear_acceleration.y, output.linear_acceleration.z = sample.linear_acceleration_xyz
        output.orientation_covariance = list(ORIENTATION_COVARIANCE)
        output.angular_velocity_covariance = list(ANGULAR_VELOCITY_COVARIANCE)
        output.linear_acceleration_covariance = list(LINEAR_ACCELERATION_COVARIANCE)
        self._imu_publisher.publish(output)


def main(args=None):
    rclpy.init(args=args)
    node = SimEvalWheelImuIngressNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
