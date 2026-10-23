#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <system_error>
#include <stdexcept>
#include <string>
#include <vector>
#include <unistd.h>

#include "mecanum_nav_rl_interfaces/msg/final_issued_command_receipt.hpp"
#include "mecanum_nav_rl_interfaces/msg/safety_lifecycle_state.hpp"
#include "mecanum_nav_rl_interfaces/msg/safety_state.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "nlohmann/json.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rosgraph_msgs/msg/clock.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "tf2_msgs/msg/tf_message.hpp"

namespace step07_observer {
using Json = nlohmann::json;

rclcpp::QoS dynamic_tf_qos() {
  return rclcpp::QoS(rclcpp::KeepLast(100)).best_effort().durability_volatile();
}
rclcpp::QoS static_tf_qos() {
  return rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
}
rclcpp::QoS lifecycle_state_qos() {
  return rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
}
rclcpp::QoS receipt_qos() {
  return rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
}
bool is_dynamic_edge(const std::string &parent, const std::string &child) {
  return parent == "odom" && child == "base_link";
}
bool is_static_edge(const std::string &parent, const std::string &child) {
  return parent == "base_link" && child == "lidar_frame";
}
bool lifecycle_receipt_identity_matches(uint64_t episode_a, uint32_t reset_a, uint32_t runtime_a,
                                        uint64_t episode_b, uint32_t reset_b, uint32_t runtime_b) {
  return episode_a == episode_b && reset_a == reset_b && runtime_a == runtime_b;
}

bool lifecycle_receipts_match(const Json &lifecycle, const Json &receipts) {
  if (receipts.empty()) return false;
  for (const auto &receipt : receipts) {
    const bool matched = std::any_of(lifecycle.begin(), lifecycle.end(), [&](const Json &state) {
      return state.value("primary_state", -1) == 2 && state.value("barrier_state", -1) == 1 &&
        state.value("motion_permitted", false) && lifecycle_receipt_identity_matches(
          state.value("episode_generation", uint64_t{0}), state.value("reset_epoch", uint32_t{0}),
          state.value("runtime_generation", uint32_t{0}), receipt.value("episode_generation", uint64_t{0}),
          receipt.value("reset_epoch", uint32_t{0}), receipt.value("runtime_generation", uint32_t{0}));
    });
    if (!matched) return false;
  }
  return true;
}

bool static_transform_matches(const Json &row) {
  if (row.value("parent", "") != "base_link" || row.value("child", "") != "lidar_frame" ||
      !row.contains("translation") || !row.contains("rotation") ||
      !row["translation"].is_array() || row["translation"].size() != 3 ||
      !row["rotation"].is_array() || row["rotation"].size() != 4) return false;
  const auto &t = row["translation"];
  const auto &q = row["rotation"];
  return std::abs(t[0].get<double>() + 0.031765) <= 1e-6 &&
      std::abs(t[1].get<double>()) <= 1e-6 && std::abs(t[2].get<double>() - 0.140) <= 1e-6 &&
      std::abs(q[0].get<double>()) <= 1e-6 && std::abs(q[1].get<double>()) <= 1e-6 &&
      std::abs(q[2].get<double>()) <= 1e-6 && std::abs(q[3].get<double>() - 1.0) <= 1e-6;
}

std::string canonical_gid(const uint8_t *data, size_t size) {
  std::ostringstream output;
  output << std::hex << std::setfill('0');
  for (size_t i = 0; i < size; ++i) output << std::setw(2) << static_cast<unsigned>(data[i]);
  return output.str();
}

Json endpoint_json(const rclcpp::TopicEndpointInfo &endpoint) {
  const auto &gid = endpoint.endpoint_gid();
  return Json{{"gid", canonical_gid(gid.data(), gid.size())},
              {"node_name", endpoint.node_name()},
              {"node_namespace", endpoint.node_namespace()},
              {"topic_type", endpoint.topic_type()},
              {"endpoint_type", endpoint.endpoint_type() == rclcpp::EndpointType::Publisher ? "PUBLISHER" : "SUBSCRIPTION"},
              {"reliability", static_cast<int>(endpoint.qos_profile().reliability())},
              {"durability", static_cast<int>(endpoint.qos_profile().durability())},
              {"history", static_cast<int>(endpoint.qos_profile().history())},
              {"depth", endpoint.qos_profile().depth()}};
}

bool strictly_increasing_nonzero(const Json &rows) {
  int64_t previous = 0;
  for (const auto &row : rows) {
    const int64_t stamp = static_cast<int64_t>(row.at("stamp_sec").get<int64_t>()) * 1000000000LL + row.at("stamp_nanosec").get<int64_t>();
    if (stamp <= previous) return false;
    previous = stamp;
  }
  return rows.size() >= 5;
}

std::vector<Json> endpoint_rows(const rclcpp::Node &node, const std::string &topic, bool publishers) {
  std::vector<Json> rows;
  if (publishers) {
    for (const auto &endpoint : node.get_publishers_info_by_topic(topic)) rows.push_back(endpoint_json(endpoint));
  } else {
    for (const auto &endpoint : node.get_subscriptions_info_by_topic(topic)) rows.push_back(endpoint_json(endpoint));
  }
  const auto discovered = std::chrono::steady_clock::now().time_since_epoch();
  const auto discovered_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(discovered).count();
  for (auto &row : rows) {
    row["topic_name"] = topic;
    row["discovery_monotonic_ns"] = discovered_ns;
  }
  return rows;
}

bool write_json_atomic(const std::string &path, const Json &document) {
  if (path.empty()) return false;
  const std::filesystem::path target(path);
  const auto temporary = target.string() + ".tmp." + std::to_string(::getpid());
  {
    std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
    output << document.dump(-1, ' ', false, Json::error_handler_t::strict);
    output.flush();
    if (!output) return false;
  }
  std::error_code error;
  std::filesystem::rename(temporary, target, error);
  if (error) {
    std::filesystem::remove(temporary);
    return false;
  }
  return true;
}

bool exact_owner_for_gid(const Json &rows, const std::string &gid, const std::string &name) {
  size_t matches = 0;
  bool owner = false;
  for (const auto &row : rows) {
    if (row.at("gid") == gid) {
      ++matches;
      owner = row.at("node_name") == name && row.at("node_namespace") == "/" && row.at("topic_type") == "tf2_msgs/msg/TFMessage";
    }
  }
  return matches == 1 && owner;
}

bool unique_topic_owner(const Json &rows, const std::string &name, const std::string &type) {
  return rows.is_array() && rows.size() == 1 && rows.front().value("node_name", "") == name &&
      rows.front().value("node_namespace", "") == "/" && rows.front().value("topic_type", "") == type;
}

enum class EndpointPolicyStatus { Match, Unobservable, Mismatch };

EndpointPolicyStatus endpoint_policy_status(const Json &row, int reliability,
                                            int durability, int depth) {
  if (row.value("reliability", -1) != reliability ||
      row.value("durability", -1) != durability) return EndpointPolicyStatus::Mismatch;
  if (row.value("history", -1) == RMW_QOS_POLICY_HISTORY_KEEP_LAST &&
      row.value("depth", -1) == depth) return EndpointPolicyStatus::Match;
  if (row.value("history", -1) == RMW_QOS_POLICY_HISTORY_UNKNOWN &&
      row.value("depth", -1) == 0) return EndpointPolicyStatus::Unobservable;
  return EndpointPolicyStatus::Mismatch;
}

bool lifecycle_publisher_contract(const Json &rows) {
  if (!rows.is_array() || rows.size() != 1) return false;
  const auto &row = rows.front();
  return row.value("node_name", "") == "safety_lifecycle" && row.value("node_namespace", "") == "/" &&
      row.value("topic_type", "") == "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState" &&
      row.value("endpoint_type", "") == "PUBLISHER" &&
      endpoint_policy_status(row, RMW_QOS_POLICY_RELIABILITY_RELIABLE,
        RMW_QOS_POLICY_DURABILITY_VOLATILE, 10) == EndpointPolicyStatus::Match;
}

bool receipt_publisher_contract(const Json &rows) {
  if (!rows.is_array() || rows.size() != 1) return false;
  const auto &row = rows.front();
  return row.value("node_name", "") == "final_twist_publisher" && row.value("node_namespace", "") == "/" &&
      row.value("topic_type", "") == "mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt" &&
      row.value("endpoint_type", "") == "PUBLISHER" &&
      endpoint_policy_status(row, RMW_QOS_POLICY_RELIABILITY_RELIABLE,
        RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL, 1) == EndpointPolicyStatus::Match;
}

bool lifecycle_observer_subscriptions_contract(const Json &rows) {
  if (!rows.is_array()) return false;
  const auto exact_subscription = [](const Json &row, const std::string &node) {
    return row.value("node_name", "") == node && row.value("node_namespace", "") == "/" &&
      row.value("topic_type", "") == "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState" &&
      row.value("endpoint_type", "") == "SUBSCRIPTION" &&
      endpoint_policy_status(row, RMW_QOS_POLICY_RELIABILITY_RELIABLE,
        RMW_QOS_POLICY_DURABILITY_VOLATILE, 10) == EndpointPolicyStatus::Match;
  };
  const std::vector<std::string> expected = {"safety_supervisor", "final_twist_publisher",
      "step07_nav2_baseline_runtime_observer", "step07_gate_b_observer"};
  return rows.size() == expected.size() && std::all_of(expected.begin(), expected.end(), [&](const std::string &node) {
    return std::count_if(rows.begin(), rows.end(), [&](const Json &row) { return exact_subscription(row, node); }) == 1;
  });
}

size_t endpoint_count_for_gid(const Json &rows, const std::string &gid) {
  return static_cast<size_t>(std::count_if(rows.begin(), rows.end(), [&](const Json &row) { return row.value("gid", "") == gid; }));
}

Json empty_collection_document() {
  return Json{{"clock", Json::array()}, {"scan", Json::array()},
              {"wheel_odometry_raw", Json::array()}, {"imu_data", Json::array()},
              {"filtered_odometry", Json::array()}, {"tf", Json::array()},
              {"tf_static", Json::array()}, {"map_to_odom", Json::array()},
              {"world_to_map", Json::array()}};
}

class Observer final : public rclcpp::Node {
 public:
  Observer() : Node("step07_nav2_baseline_runtime_observer") {
    output_path_ = declare_parameter<std::string>("output_path", "");
    ready_path_ = declare_parameter<std::string>("ready_path", "");
    config_hash_ = declare_parameter<std::string>("config_hash", "");
    duration_sec_ = declare_parameter<int>("duration_sec", 30);
    runner_controlled_shutdown_ = declare_parameter<bool>("runner_controlled_shutdown", false);
    if (output_path_.empty() || ready_path_.empty() || config_hash_.size() != 64 || duration_sec_ < 1 || duration_sec_ > 1800) {
      throw std::invalid_argument("OBSERVER_ARGUMENT_INVALID");
    }
    doc_ = empty_collection_document();
    doc_["schema_version"] = "1.0";
    doc_["config_hash"] = config_hash_;
    doc_["errors"] = Json::array();
    doc_["lifecycle"] = Json::array();
    doc_["receipt"] = Json::array();
    doc_["safety_state"] = Json::array();
    doc_["gate_b_vectors"] = Json::array();
    doc_["map_to_odom"] = Json::array();
    doc_["map_to_odom_gids"] = Json::array();
    doc_["world_to_map"] = Json::array();
    doc_["forbidden_boundary"] = Json::object();
    doc_["graph"] = Json::object();
    doc_["cmd_vel_ownership"] = Json{{"publisher_endpoints", Json::array()},
                                       {"all_endpoints", Json::array()}};
    doc_["qos"] = Json{
      {"/tf", {{"history", "KEEP_LAST"}, {"depth", 100}, {"reliability", "BEST_EFFORT"}, {"durability", "VOLATILE"}}},
      {"/tf_static", {{"history", "KEEP_LAST"}, {"depth", 1}, {"reliability", "RELIABLE"}, {"durability", "TRANSIENT_LOCAL"}}},
      {"/mecanum/safety_lifecycle_state", {{"history", "KEEP_LAST"}, {"depth", 10}, {"reliability", "RELIABLE"}, {"durability", "VOLATILE"}}},
      {"/mecanum/final_issued_command", {{"history", "KEEP_LAST"}, {"depth", 1}, {"reliability", "RELIABLE"}, {"durability", "TRANSIENT_LOCAL"}}}};
    auto sensor_qos = rclcpp::SensorDataQoS();
    auto static_qos = static_tf_qos();
    auto lifecycle_qos = lifecycle_state_qos();
    auto receipt_subscription_qos = receipt_qos();
    clock_sub_ = create_subscription<rosgraph_msgs::msg::Clock>("/clock", sensor_qos,
      [this](rosgraph_msgs::msg::Clock::ConstSharedPtr msg) { doc_["clock"].push_back({{"sec", msg->clock.sec}, {"nanosec", msg->clock.nanosec}}); });
    scan_sub_ = create_subscription<sensor_msgs::msg::LaserScan>("/scan", sensor_qos,
      [this](sensor_msgs::msg::LaserScan::ConstSharedPtr msg) { Json ranges = Json::array(); for (float value : msg->ranges) ranges.push_back(std::isfinite(value) ? Json(value) : (value > 0 ? Json("POSITIVE_INFINITY") : Json("INVALID_NONFINITE"))); doc_["scan"].push_back({{"frame_id", msg->header.frame_id}, {"stamp_sec", msg->header.stamp.sec}, {"stamp_nanosec", msg->header.stamp.nanosec}, {"angle_min", msg->angle_min}, {"angle_increment", msg->angle_increment}, {"range_min", msg->range_min}, {"range_max", msg->range_max}, {"range_count", msg->ranges.size()}, {"ranges", ranges}, {"ranges_valid", std::all_of(msg->ranges.begin(), msg->ranges.end(), [](float x) { return std::isfinite(x) || x == std::numeric_limits<float>::infinity(); })}}); });
    wheel_sub_ = create_subscription<nav_msgs::msg::Odometry>("/wheel/odometry_raw", sensor_qos,
      [this](nav_msgs::msg::Odometry::ConstSharedPtr msg) { const auto &v = msg->twist.twist; doc_["wheel_odometry_raw"].push_back({{"frame_id", msg->header.frame_id}, {"child_frame_id", msg->child_frame_id}, {"stamp_sec", msg->header.stamp.sec}, {"stamp_nanosec", msg->header.stamp.nanosec}, {"twist", {v.linear.x, v.linear.y, v.linear.z, v.angular.x, v.angular.y, v.angular.z}}, {"twist_finite", std::isfinite(v.linear.x) && std::isfinite(v.linear.y) && std::isfinite(v.angular.z)}}); });
    imu_sub_ = create_subscription<sensor_msgs::msg::Imu>("/imu/data", sensor_qos,
      [this](sensor_msgs::msg::Imu::ConstSharedPtr msg) { const auto &q = msg->orientation; const auto &w = msg->angular_velocity; const auto &a = msg->linear_acceleration; const double norm = q.x*q.x + q.y*q.y + q.z*q.z + q.w*q.w; doc_["imu_data"].push_back({{"frame_id", msg->header.frame_id}, {"stamp_sec", msg->header.stamp.sec}, {"stamp_nanosec", msg->header.stamp.nanosec}, {"orientation", {q.x, q.y, q.z, q.w}}, {"angular_velocity", {w.x, w.y, w.z}}, {"linear_acceleration", {a.x, a.y, a.z}}, {"quaternion_finite", std::isfinite(q.x) && std::isfinite(q.y) && std::isfinite(q.z) && std::isfinite(q.w)}, {"quaternion_norm", norm}}); });
    filtered_sub_ = create_subscription<nav_msgs::msg::Odometry>("/odometry/filtered", sensor_qos,
      [this](nav_msgs::msg::Odometry::ConstSharedPtr msg) { const auto finite_array = [](const auto &values) { return std::all_of(values.begin(), values.end(), [](double value) { return std::isfinite(value); }); }; const auto &p = msg->pose.pose.position; const auto &q = msg->pose.pose.orientation; const auto &tw = msg->twist.twist; const bool pose_finite = std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z) && std::isfinite(q.x) && std::isfinite(q.y) && std::isfinite(q.z) && std::isfinite(q.w); const bool twist_finite = std::isfinite(tw.linear.x) && std::isfinite(tw.linear.y) && std::isfinite(tw.angular.z); doc_["filtered_odometry"].push_back({{"frame_id", msg->header.frame_id}, {"child_frame_id", msg->child_frame_id}, {"stamp_sec", msg->header.stamp.sec}, {"stamp_nanosec", msg->header.stamp.nanosec}, {"pose", {p.x, p.y, p.z, q.x, q.y, q.z, q.w}}, {"twist", {tw.linear.x, tw.linear.y, tw.linear.z, tw.angular.x, tw.angular.y, tw.angular.z}}, {"pose_covariance", msg->pose.covariance}, {"twist_covariance", msg->twist.covariance}, {"pose_finite", pose_finite}, {"twist_finite", twist_finite}, {"pose_covariance_finite", finite_array(msg->pose.covariance)}, {"twist_covariance_finite", finite_array(msg->twist.covariance)}, {"pose_covariance_count", msg->pose.covariance.size()}, {"twist_covariance_count", msg->twist.covariance.size()}}); });
    tf_sub_ = create_subscription<tf2_msgs::msg::TFMessage>("/tf", dynamic_tf_qos(),
      [this](tf2_msgs::msg::TFMessage::ConstSharedPtr msg, const rclcpp::MessageInfo &info) { collect_tf(msg, info, false); });
    tf_static_sub_ = create_subscription<tf2_msgs::msg::TFMessage>("/tf_static", static_qos,
      [this](tf2_msgs::msg::TFMessage::ConstSharedPtr msg, const rclcpp::MessageInfo &info) { collect_tf(msg, info, true); });
    lifecycle_sub_ = create_subscription<mecanum_nav_rl_interfaces::msg::SafetyLifecycleState>("/mecanum/safety_lifecycle_state", lifecycle_qos,
      [this](mecanum_nav_rl_interfaces::msg::SafetyLifecycleState::ConstSharedPtr msg) { doc_["lifecycle"].push_back({{"episode_generation", msg->episode_generation}, {"reset_epoch", msg->reset_epoch}, {"runtime_generation", msg->runtime_generation}, {"primary_state", msg->primary_state}, {"barrier_state", msg->barrier_state}, {"motion_permitted", msg->motion_permitted}, {"reason", msg->reason}}); });
    receipt_sub_ = create_subscription<mecanum_nav_rl_interfaces::msg::FinalIssuedCommandReceipt>("/mecanum/final_issued_command", receipt_subscription_qos,
      [this](mecanum_nav_rl_interfaces::msg::FinalIssuedCommandReceipt::ConstSharedPtr msg) { doc_["receipt"].push_back({{"stamp_sec", msg->header.stamp.sec}, {"stamp_nanosec", msg->header.stamp.nanosec}, {"episode_generation", msg->episode_generation}, {"reset_epoch", msg->reset_epoch}, {"runtime_generation", msg->runtime_generation}, {"sequence", msg->final_publish_sequence}, {"source", msg->source}, {"vx", msg->final_command.linear.x}, {"vy", msg->final_command.linear.y}, {"wz", msg->final_command.angular.z}}); });
    safety_state_sub_ = create_subscription<mecanum_nav_rl_interfaces::msg::SafetyState>(
      "/mecanum/safety_state", lifecycle_qos,
      [this](mecanum_nav_rl_interfaces::msg::SafetyState::ConstSharedPtr msg) {
        const auto twist = [](const geometry_msgs::msg::Twist &value) {
          return Json{{"vx", value.linear.x}, {"vy", value.linear.y}, {"wz", value.angular.z}};
        };
        doc_["safety_state"].push_back({
          {"stamp_sec", msg->header.stamp.sec}, {"stamp_nanosec", msg->header.stamp.nanosec},
          {"state", msg->state}, {"active_command_source", msg->active_command_source},
          {"command_valid", msg->command_valid}, {"motion_permitted", msg->motion_permitted},
          {"intervention_reasons", msg->intervention_reasons}, {"raw_command", twist(msg->raw_command)},
          {"limited_command", twist(msg->limited_command)}, {"final_command", twist(msg->final_command)},
          {"scan_fresh", msg->scan_fresh}, {"odom_fresh", msg->odom_fresh},
          {"tf_valid", msg->tf_valid}, {"localization_valid", msg->localization_valid},
          {"navigation_state_fresh", msg->navigation_state_fresh}, {"path_valid", msg->path_valid},
          {"scan_age_ms", msg->scan_age_ms}, {"odom_age_ms", msg->odom_age_ms},
          {"command_age_ms", msg->command_age_ms}, {"navigation_state_age_ms", msg->navigation_state_age_ms}});
      });
    started_ = std::chrono::steady_clock::now();
    const bool context_valid = context_is_valid();
    const bool subscriptions_created = clock_sub_ && scan_sub_ && wheel_sub_ && imu_sub_ &&
      filtered_sub_ && tf_sub_ && tf_static_sub_ && lifecycle_sub_ && receipt_sub_ && safety_state_sub_;
    ready_document_ = Json{{"schema_version", "1.0"}, {"collector", "step07_nav2_baseline_runtime_observer"},
      {"config_hash", config_hash_}, {"pid", static_cast<int64_t>(::getpid())},
      {"process_alive", true},
      {"ros_context_valid", context_valid},
      {"subscriptions_created", subscriptions_created ? Json::array({"/clock", "/scan",
        "/wheel/odometry_raw", "/imu/data", "/odometry/filtered", "/tf", "/tf_static",
        "/mecanum/safety_lifecycle_state", "/mecanum/final_issued_command", "/mecanum/safety_state"}) : Json::array()},
      {"state", context_valid && subscriptions_created ? "READY" : "NOT_READY"}};
    if (!context_valid || !subscriptions_created) {
      ready_document_["failure_literal"] = "OBSERVER_READINESS_HANDSHAKE_FAILED";
    }
    if (!context_valid || !subscriptions_created || !write_json_atomic(ready_path_, ready_document_)) {
      doc_["errors"].push_back("OBSERVER_READINESS_HANDSHAKE_FAILED");
      failed_closed_ = true;
    }
    if (!runner_controlled_shutdown_) {
      timer_ = create_wall_timer(std::chrono::seconds(duration_sec_), [this]() { finish(); });
    }
  }

  bool context_is_valid() {
    const auto context = get_node_base_interface()->get_context();
    return context && context->is_valid();
  }

  bool finished() const { return finished_; }
  int exit_code() const {
    // QoS and runtime acceptance are verdict data for the runner/validator.
    // Only actual collection/readiness/artifact failures affect process status.
    return failed_closed_ ? 2 : 0;
  }

  void collect_tf(tf2_msgs::msg::TFMessage::ConstSharedPtr msg, const rclcpp::MessageInfo &info, bool is_static) {
    const auto &rmw_info = info.get_rmw_message_info();
    const auto gid = canonical_gid(rmw_info.publisher_gid.data, RMW_GID_STORAGE_SIZE);
    for (const auto &transform : msg->transforms) {
      const auto parent = transform.header.frame_id;
      const auto child = transform.child_frame_id;
      if (!is_static && is_dynamic_edge(parent, child)) {
        const auto &t = transform.transform.translation; const auto &q = transform.transform.rotation;
        doc_["tf"].push_back({{"parent", parent}, {"child", child}, {"stamp_sec", transform.header.stamp.sec}, {"stamp_nanosec", transform.header.stamp.nanosec}, {"translation", {t.x, t.y, t.z}}, {"rotation", {q.x, q.y, q.z, q.w}}, {"publisher_gid", gid}});
        dynamic_gids_.insert(gid);
      } else if (is_static && is_static_edge(parent, child)) {
        doc_["tf_static"].push_back({{"parent", parent}, {"child", child}, {"stamp_sec", transform.header.stamp.sec}, {"stamp_nanosec", transform.header.stamp.nanosec}, {"publisher_gid", gid}, {"translation", {transform.transform.translation.x, transform.transform.translation.y, transform.transform.translation.z}}, {"rotation", {transform.transform.rotation.x, transform.transform.rotation.y, transform.transform.rotation.z, transform.transform.rotation.w}}});
        static_gids_.insert(gid);
      }
      if (!is_static && parent == "map" && child == "odom") {
        doc_["map_to_odom"].push_back({{"parent", parent}, {"child", child}, {"stamp_sec", transform.header.stamp.sec}, {"stamp_nanosec", transform.header.stamp.nanosec}, {"publisher_gid", gid}});
        map_to_odom_gids_.insert(gid);
      }
      if (parent == "world" && child == "map") doc_["world_to_map"].push_back({{"parent", parent}, {"child", child}, {"publisher_gid", gid}});
    }
  }

  void finish() {
    if (finished_) return;
    finished_ = true;
    if (!context_is_valid()) {
      failed_closed_ = true;
      doc_["errors"].push_back("OBSERVER_CONTEXT_INVALID_BEFORE_FINISH");
      doc_["observer_lifecycle"] = Json{{"state", "FAIL_CLOSED"},
        {"failure_literal", "OBSERVER_CONTEXT_INVALID_BEFORE_FINISH"},
        {"ros_context_valid", false}, {"partial_artifact", output_path_}};
      write_json_atomic(output_path_, doc_);
      return;
    }
    doc_["observer_lifecycle"] = Json{{"state", "FINALIZING"}, {"ros_context_valid", true}};
    for (const auto *topic : {"/tf", "/tf_static", "/cmd_vel", "/clock", "/scan", "/wheel/odometry_raw", "/imu/data", "/odometry/filtered", "/map", "/odom", "/ground_truth/odom", "/mecanum/safety_lifecycle_state", "/mecanum/safety/lifecycle_state", "/mecanum/final_issued_command", "/mecanum/safety_state"}) {
      if (!context_is_valid()) {
        failed_closed_ = true;
        doc_["errors"].push_back("OBSERVER_CONTEXT_INVALID_DURING_ENDPOINT_SNAPSHOT");
        doc_["observer_lifecycle"] = Json{{"state", "FAIL_CLOSED"},
          {"failure_literal", "OBSERVER_CONTEXT_INVALID_DURING_ENDPOINT_SNAPSHOT"},
          {"ros_context_valid", false}, {"partial_artifact", output_path_}};
        write_json_atomic(output_path_, doc_);
        return;
      }
      Json pubs = endpoint_rows(*this, topic, true);
      Json subs = endpoint_rows(*this, topic, false);
      doc_["graph"][topic] = Json{{"publishers", pubs}, {"subscribers", subs}};
      if (std::string(topic) == "/cmd_vel") {
        doc_["cmd_vel_ownership"]["publisher_endpoints"] = pubs;
        doc_["cmd_vel_ownership"]["all_endpoints"] = Json{{"publishers", pubs}, {"subscribers", subs}};
      }
      if (std::string(topic) == "/odom" || std::string(topic) == "/ground_truth/odom" || std::string(topic) == "/map") {
        doc_["forbidden_boundary"][topic] = Json{{"publishers", pubs}, {"subscribers", subs}};
      }
    }
    doc_["dynamic_tf_gids"] = dynamic_gids_;
    doc_["static_tf_gids"] = static_gids_;
    doc_["map_to_odom_gids"] = map_to_odom_gids_;
    Json tf_publishers = doc_["graph"]["/tf"]["publishers"];
    Json static_publishers = doc_["graph"]["/tf_static"]["publishers"];
    bool dynamic_owner = dynamic_gids_.size() == 1 && exact_owner_for_gid(tf_publishers, *dynamic_gids_.begin(), "ekf_filter_node");
    bool static_owner = static_gids_.size() == 1 && exact_owner_for_gid(static_publishers, *static_gids_.begin(), "robot_state_publisher");
    bool map_to_odom_owner = map_to_odom_gids_.size() == 1 && exact_owner_for_gid(tf_publishers, *map_to_odom_gids_.begin(), "amcl");
    if (dynamic_gids_.size() != 1) doc_["errors"].push_back("TF_EDGE_PUBLISHER_GID_NOT_UNIQUE");
    else if (endpoint_count_for_gid(tf_publishers, *dynamic_gids_.begin()) == 0) doc_["errors"].push_back("TF_EDGE_PUBLISHER_GID_UNMAPPABLE");
    else if (endpoint_count_for_gid(tf_publishers, *dynamic_gids_.begin()) != 1) doc_["errors"].push_back("TF_EDGE_PUBLISHER_GID_NOT_UNIQUE");
    else if (!dynamic_owner) doc_["errors"].push_back("TF_EDGE_PUBLISHER_NOT_EKF");
    if (static_gids_.size() != 1) doc_["errors"].push_back("TF_STATIC_EDGE_PUBLISHER_GID_NOT_UNIQUE");
    else if (endpoint_count_for_gid(static_publishers, *static_gids_.begin()) == 0) doc_["errors"].push_back("TF_STATIC_EDGE_PUBLISHER_GID_UNMAPPABLE");
    else if (endpoint_count_for_gid(static_publishers, *static_gids_.begin()) != 1) doc_["errors"].push_back("TF_STATIC_EDGE_PUBLISHER_GID_NOT_UNIQUE");
    else if (!static_owner) doc_["errors"].push_back("TF_STATIC_EDGE_PUBLISHER_NOT_ROBOT_STATE_PUBLISHER");
    bool static_transform = doc_["tf_static"].size() == 1 && static_transform_matches(doc_["tf_static"].front());
    if (!static_transform) doc_["errors"].push_back("TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH");
    if (map_to_odom_gids_.size() != 1) doc_["errors"].push_back("TF_MAP_ODOM_PUBLISHER_GID_NOT_UNIQUE");
    else if (endpoint_count_for_gid(tf_publishers, *map_to_odom_gids_.begin()) == 0) doc_["errors"].push_back("TF_MAP_ODOM_PUBLISHER_GID_UNMAPPABLE");
    else if (endpoint_count_for_gid(tf_publishers, *map_to_odom_gids_.begin()) != 1) doc_["errors"].push_back("TF_MAP_ODOM_PUBLISHER_GID_NOT_UNIQUE");
    else if (!map_to_odom_owner) doc_["errors"].push_back("TF_MAP_ODOM_PUBLISHER_NOT_AMCL");
    bool clock_ok = doc_["clock"].size() >= 5;
    int64_t clock_previous = 0;
    for (const auto &row : doc_["clock"]) { int64_t stamp = static_cast<int64_t>(row.at("sec").get<int64_t>()) * 1000000000LL + row.at("nanosec").get<int64_t>(); if (stamp <= clock_previous) clock_ok = false; clock_previous = stamp; }
    bool odom_ok = strictly_increasing_nonzero(doc_["filtered_odometry"]);
    bool dynamic_ok = strictly_increasing_nonzero(doc_["tf"]) && dynamic_owner;
    const auto cmd_pubs = doc_["cmd_vel_ownership"]["publisher_endpoints"];
    const auto cmd_subs = doc_["graph"]["/cmd_vel"]["subscribers"];
    bool cmd_owner = cmd_pubs.size() == 1 && cmd_pubs.front().at("node_name") == "final_twist_publisher" &&
      cmd_pubs.front().at("node_namespace") == "/" && cmd_pubs.front().at("topic_type") == "geometry_msgs/msg/Twist";
    bool bridge_subscriber = std::any_of(cmd_subs.begin(), cmd_subs.end(), [](const Json &row) { return row.at("node_name") == "parameter_bridge" || row.at("node_name") == "sim_eval_cmd_vel_bridge"; });
    bool bridge_not_publisher = std::none_of(cmd_pubs.begin(), cmd_pubs.end(), [](const Json &row) { return row.at("node_name") == "parameter_bridge" || row.at("node_name") == "sim_eval_cmd_vel_bridge"; });
    bool boundary_clear = doc_["forbidden_boundary"]["/odom"]["publishers"].empty() && doc_["forbidden_boundary"]["/odom"]["subscribers"].empty() &&
      doc_["forbidden_boundary"]["/ground_truth/odom"]["publishers"].empty() && doc_["forbidden_boundary"]["/ground_truth/odom"]["subscribers"].empty() &&
      doc_["world_to_map"].empty();
    bool wheel_ok = !doc_["wheel_odometry_raw"].empty() && std::all_of(doc_["wheel_odometry_raw"].begin(), doc_["wheel_odometry_raw"].end(), [](const Json &row) { return row.at("frame_id") == "odom" && row.at("child_frame_id") == "base_link" && row.at("twist_finite").get<bool>(); });
    bool imu_ok = !doc_["imu_data"].empty() && std::all_of(doc_["imu_data"].begin(), doc_["imu_data"].end(), [](const Json &row) { const double norm = row.at("quaternion_norm").get<double>(); return row.at("frame_id") == "base_link" && row.at("quaternion_finite").get<bool>() && std::isfinite(norm) && std::abs(norm - 1.0) <= 1e-3; });
    bool scan_ok = !doc_["scan"].empty() && std::all_of(doc_["scan"].begin(), doc_["scan"].end(), [](const Json &row) { return row.at("frame_id") == "lidar_frame" && row.at("ranges_valid").get<bool>(); });
    bool lifecycle_ready = std::any_of(doc_["lifecycle"].begin(), doc_["lifecycle"].end(), [](const Json &row) { return row.at("primary_state") == 2 && row.at("barrier_state") == 1 && row.at("motion_permitted").get<bool>(); });
    bool receipt_observed = !doc_["receipt"].empty();
    bool lifecycle_receipt_identity = lifecycle_receipts_match(doc_["lifecycle"], doc_["receipt"]);
    const auto lifecycle_publishers = doc_["graph"]["/mecanum/safety_lifecycle_state"]["publishers"];
    const auto lifecycle_subscribers = doc_["graph"]["/mecanum/safety_lifecycle_state"]["subscribers"];
    const auto receipt_publishers = doc_["graph"]["/mecanum/final_issued_command"]["publishers"];
    auto qos_status_rows = Json::array();
    const auto add_qos_status = [&](const std::string &topic, const Json &rows,
                                    const std::string &expected_node, const std::string &type,
                                    const std::string &direction, int reliability,
                                    int durability, int depth) {
      if (!rows.is_array()) return;
      for (const auto &row : rows) {
        if (row.value("node_name", "") != expected_node ||
            row.value("endpoint_type", "") != direction) continue;
        const auto status = row.value("topic_type", "") == type ?
          endpoint_policy_status(row, reliability, durability, depth) : EndpointPolicyStatus::Mismatch;
        const char *label = status == EndpointPolicyStatus::Match ? "OBSERVED_MATCH" :
          status == EndpointPolicyStatus::Unobservable ? "UNOBSERVABLE" : "MISMATCH";
        qos_status_rows.push_back({{"topic", topic}, {"node_name", expected_node},
          {"endpoint_type", direction}, {"history_depth_status", label}});
      }
    };
    add_qos_status("/mecanum/safety_lifecycle_state", lifecycle_publishers, "safety_lifecycle",
      "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState", "PUBLISHER",
      RMW_QOS_POLICY_RELIABILITY_RELIABLE, RMW_QOS_POLICY_DURABILITY_VOLATILE, 10);
    for (const auto *name : {"safety_supervisor", "final_twist_publisher",
                             "step07_nav2_baseline_runtime_observer", "step07_gate_b_observer"}) {
      add_qos_status("/mecanum/safety_lifecycle_state", lifecycle_subscribers, name,
        "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState", "SUBSCRIPTION",
        RMW_QOS_POLICY_RELIABILITY_RELIABLE, RMW_QOS_POLICY_DURABILITY_VOLATILE, 10);
    }
    add_qos_status("/mecanum/final_issued_command", receipt_publishers, "final_twist_publisher",
      "mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt", "PUBLISHER",
      RMW_QOS_POLICY_RELIABILITY_RELIABLE, RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL, 1);
    doc_["qos_history_depth_observability"] = qos_status_rows;
    doc_["qos_endpoint_absence"] = Json::array();
    for (const auto *expected_node : {"safety_supervisor", "final_twist_publisher",
                                      "step07_nav2_baseline_runtime_observer", "step07_gate_b_observer"}) {
      const bool observed = std::any_of(lifecycle_subscribers.begin(), lifecycle_subscribers.end(),
        [&](const Json &row) { return row.value("node_name", "") == expected_node; });
      if (!observed) doc_["qos_endpoint_absence"].push_back({
        {"topic", "/mecanum/safety_lifecycle_state"}, {"node_name", expected_node},
        {"endpoint_type", "SUBSCRIPTION"}, {"status", "UNOBSERVABLE"},
        {"reason", "ENDPOINT_NOT_DISCOVERED_AT_FINAL_SNAPSHOT"},
        {"discovery_monotonic_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(
          std::chrono::steady_clock::now().time_since_epoch()).count()}});
    }
    const auto qos_verdict = [&](const std::string &topic) {
      bool unobservable = false;
      size_t observed = 0;
      const size_t expected = topic == "/mecanum/safety_lifecycle_state" ? 5 : 1;
      for (const auto &row : qos_status_rows) {
        if (row.value("topic", "") != topic) continue;
        ++observed;
        const auto status = row.value("history_depth_status", "");
        if (status == "MISMATCH") return std::string("FAIL");
        if (status == "UNOBSERVABLE") unobservable = true;
      }
      if (observed != expected) return std::string("FAIL");
      return unobservable ? std::string("UNOBSERVABLE") : std::string("PASS");
    };
    doc_["qos_verdict"] = Json{
      {"lifecycle_endpoint_qos_contract", qos_verdict("/mecanum/safety_lifecycle_state")},
      {"receipt_qos_contract", qos_verdict("/mecanum/final_issued_command")}};
    doc_["qos_verdict_details"] = Json::object();
    for (const auto &row : qos_status_rows) {
      const auto topic = row.value("topic", "");
      const auto node_name = row.value("node_name", "");
      const auto &endpoints = row.value("endpoint_type", "") == "PUBLISHER"
        ? (topic == "/mecanum/safety_lifecycle_state" ? lifecycle_publishers : receipt_publishers)
        : lifecycle_subscribers;
      const auto endpoint = std::find_if(endpoints.begin(), endpoints.end(), [&](const Json &candidate) {
        return candidate.value("node_name", "") == node_name &&
          candidate.value("endpoint_type", "") == row.value("endpoint_type", "");
      });
      if (endpoint == endpoints.end()) continue;
      std::string reason = "POLICY_MATCH";
      const auto expected_type = topic == "/mecanum/safety_lifecycle_state"
        ? "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState"
        : "mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt";
      if (endpoint->value("topic_type", "") != expected_type) reason = "TOPIC_TYPE_MISMATCH";
      else if (endpoint->value("reliability", -1) != RMW_QOS_POLICY_RELIABILITY_RELIABLE) reason = "RELIABILITY_MISMATCH";
      else if (endpoint->value("durability", -1) != (topic == "/mecanum/safety_lifecycle_state"
          ? RMW_QOS_POLICY_DURABILITY_VOLATILE : RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL)) reason = "DURABILITY_MISMATCH";
      else if (endpoint->value("history", -1) == RMW_QOS_POLICY_HISTORY_UNKNOWN && endpoint->value("depth", -1) == 0)
        reason = "RMW_HISTORY_DEPTH_METADATA_UNAVAILABLE";
      else if (endpoint->value("history", -1) != RMW_QOS_POLICY_HISTORY_KEEP_LAST ||
               endpoint->value("depth", -1) != (topic == "/mecanum/safety_lifecycle_state" ? 10 : 1))
        reason = "HISTORY_DEPTH_MISMATCH";
      doc_["qos_verdict_details"][topic].push_back({
        {"endpoint_name", node_name}, {"endpoint_type", row.value("endpoint_type", "")},
        {"topic_name", topic}, {"gid", endpoint->value("gid", "")},
        {"node_namespace", endpoint->value("node_namespace", "")},
        {"topic_type", endpoint->value("topic_type", "")},
        {"reliability", endpoint->value("reliability", -1)},
        {"durability", endpoint->value("durability", -1)},
        {"history", endpoint->value("history", -1)}, {"depth", endpoint->value("depth", -1)},
        {"discovery_monotonic_ns", endpoint->value("discovery_monotonic_ns", int64_t{0})},
        {"status", row.value("history_depth_status", "")}, {"reason", reason}});
    }
    doc_["acceptance"] = Json{
      {"clock_multisample", clock_ok}, {"filtered_odometry_multisample", odom_ok},
      {"tf_qos_contract", doc_["qos"]["/tf"]["reliability"] == "BEST_EFFORT" && doc_["qos"]["/tf"]["durability"] == "VOLATILE" && doc_["qos"]["/tf"]["history"] == "KEEP_LAST" && doc_["qos"]["/tf"]["depth"] == 100 && doc_["qos"]["/tf_static"]["reliability"] == "RELIABLE" && doc_["qos"]["/tf_static"]["durability"] == "TRANSIENT_LOCAL" && doc_["qos"]["/tf_static"]["history"] == "KEEP_LAST" && doc_["qos"]["/tf_static"]["depth"] == 1},
      {"dynamic_tf_single_gid_and_ekf_owner", dynamic_ok}, {"static_transform_and_rsp_owner", static_transform && static_owner},
      {"map_to_odom_single_amcl_owner", !doc_["map_to_odom"].empty() && map_to_odom_owner},
      {"world_to_map_absent", doc_["world_to_map"].empty()}, {"forbidden_boundary_clear", boundary_clear},
      {"scan_publisher_owner", unique_topic_owner(doc_["graph"]["/scan"]["publishers"], "sim_eval_scan_bridge", "sensor_msgs/msg/LaserScan")},
      {"wheel_publisher_owner", unique_topic_owner(doc_["graph"]["/wheel/odometry_raw"]["publishers"], "sim_eval_wheel_imu_ingress", "nav_msgs/msg/Odometry")},
      {"imu_publisher_owner", unique_topic_owner(doc_["graph"]["/imu/data"]["publishers"], "sim_eval_wheel_imu_ingress", "sensor_msgs/msg/Imu")},
      {"filtered_odometry_publisher_owner", unique_topic_owner(doc_["graph"]["/odometry/filtered"]["publishers"], "ekf_filter_node", "nav_msgs/msg/Odometry")},
      {"map_server_publisher_owner", unique_topic_owner(doc_["graph"]["/map"]["publishers"], "map_server", "nav_msgs/msg/OccupancyGrid")},
      {"lifecycle_endpoint_qos_contract", lifecycle_publisher_contract(doc_["graph"]["/mecanum/safety_lifecycle_state"]["publishers"]) &&
        lifecycle_observer_subscriptions_contract(doc_["graph"]["/mecanum/safety_lifecycle_state"]["subscribers"]) &&
        doc_["qos"]["/mecanum/safety_lifecycle_state"]["history"] == "KEEP_LAST" &&
        doc_["qos"]["/mecanum/safety_lifecycle_state"]["depth"] == 10 &&
        doc_["qos"]["/mecanum/safety_lifecycle_state"]["reliability"] == "RELIABLE" &&
        doc_["qos"]["/mecanum/safety_lifecycle_state"]["durability"] == "VOLATILE" &&
        doc_["graph"]["/mecanum/safety/lifecycle_state"]["publishers"].empty() &&
        doc_["graph"]["/mecanum/safety/lifecycle_state"]["subscribers"].empty()},
      {"receipt_qos_contract", receipt_publisher_contract(doc_["graph"]["/mecanum/final_issued_command"]["publishers"]) &&
        doc_["qos"]["/mecanum/final_issued_command"]["history"] == "KEEP_LAST" &&
        doc_["qos"]["/mecanum/final_issued_command"]["depth"] == 1 &&
        doc_["qos"]["/mecanum/final_issued_command"]["reliability"] == "RELIABLE" &&
        doc_["qos"]["/mecanum/final_issued_command"]["durability"] == "TRANSIENT_LOCAL"},
      {"obsolete_lifecycle_topic_absent", doc_["graph"]["/mecanum/safety/lifecycle_state"]["publishers"].empty() &&
        doc_["graph"]["/mecanum/safety/lifecycle_state"]["subscribers"].empty()},
      {"receipt_publisher_owner", unique_topic_owner(doc_["graph"]["/mecanum/final_issued_command"]["publishers"], "final_twist_publisher", "mecanum_nav_rl_interfaces/msg/FinalIssuedCommandReceipt")},
      {"cmd_vel_single_final_publisher", cmd_owner}, {"cmd_vel_bridge_subscriber_only", bridge_subscriber && bridge_not_publisher}, {"scan_valid_frame", scan_ok},
      {"wheel_ingress_valid", wheel_ok}, {"imu_ingress_valid", imu_ok},
      {"lifecycle_ready_observed", lifecycle_ready}, {"final_receipt_observed", receipt_observed},
      {"lifecycle_receipt_identity", lifecycle_receipt_identity}};
    for (const auto &[name, pass] : doc_["acceptance"].items()) if (!pass) {
      const std::string qos_topic = name == "lifecycle_endpoint_qos_contract" ?
        "/mecanum/safety_lifecycle_state" : "/mecanum/final_issued_command";
      const size_t expected_qos_endpoints = name == "lifecycle_endpoint_qos_contract" ? 5 : 1;
      const size_t topic_qos_count = static_cast<size_t>(std::count_if(
        qos_status_rows.begin(), qos_status_rows.end(), [&](const Json &row) {
          return row.value("topic", "") == qos_topic;
        }));
      const bool unknown_qos = (name == "lifecycle_endpoint_qos_contract" || name == "receipt_qos_contract") &&
        topic_qos_count == expected_qos_endpoints &&
        std::all_of(qos_status_rows.begin(), qos_status_rows.end(), [&](const Json &row) {
          return row.value("topic", "") != qos_topic ||
            row.value("history_depth_status", "") != "MISMATCH";
        }) && std::any_of(qos_status_rows.begin(), qos_status_rows.end(), [&](const Json &row) {
          return row.value("topic", "") == qos_topic &&
            row.value("history_depth_status", "") == "UNOBSERVABLE";
        });
      // UNOBSERVABLE is raw metadata, not a C++ verdict failure. The runner and
      // offline validator resolve it only from exact pinned source/install proof.
      if (!unknown_qos) doc_["errors"].push_back("ACCEPTANCE_FAILED:" + name);
    }
    doc_["observer_lifecycle"] = Json{{"state", "FINALIZED"}, {"ros_context_valid", true}};
    if (!write_json_atomic(output_path_, doc_)) {
      failed_closed_ = true;
      RCLCPP_ERROR(get_logger(), "OBSERVER_JSON_WRITE_FAILED");
    }
  }

 private:
  std::string output_path_, ready_path_, config_hash_;
  int duration_sec_{30};
  bool finished_{false};
  bool failed_closed_{false};
  bool runner_controlled_shutdown_{false};
  std::chrono::steady_clock::time_point started_;
  Json doc_ = Json::object();
  Json ready_document_ = Json::object();
  std::set<std::string> dynamic_gids_, static_gids_;
  std::set<std::string> map_to_odom_gids_;
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Subscription<rosgraph_msgs::msg::Clock>::SharedPtr clock_sub_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr wheel_sub_, filtered_sub_;
  rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
  rclcpp::Subscription<tf2_msgs::msg::TFMessage>::SharedPtr tf_sub_, tf_static_sub_;
  rclcpp::Subscription<mecanum_nav_rl_interfaces::msg::SafetyLifecycleState>::SharedPtr lifecycle_sub_;
  rclcpp::Subscription<mecanum_nav_rl_interfaces::msg::FinalIssuedCommandReceipt>::SharedPtr receipt_sub_;
  rclcpp::Subscription<mecanum_nav_rl_interfaces::msg::SafetyState>::SharedPtr safety_state_sub_;
};
}  // namespace step07_observer

#ifndef STEP07_OBSERVER_TEST
#include <csignal>
namespace { volatile std::sig_atomic_t step07_observer_stop_requested = 0;
void step07_observer_signal_handler(int) { step07_observer_stop_requested = 1; } }
int main(int argc, char **argv) {
  rclcpp::init(argc, argv, rclcpp::InitOptions(), rclcpp::SignalHandlerOptions::None);
  std::signal(SIGINT, step07_observer_signal_handler);
  std::signal(SIGTERM, step07_observer_signal_handler);
  try {
    auto node = std::make_shared<step07_observer::Observer>();
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    while (rclcpp::ok() && !node->finished() && !step07_observer_stop_requested) {
      executor.spin_some(std::chrono::milliseconds(50));
    }
    if (!node->finished()) node->finish();
    executor.remove_node(node);
    const int observer_exit_code = node->exit_code();
    if (rclcpp::ok()) rclcpp::shutdown();
    if (observer_exit_code != 0) return observer_exit_code;
  }
  catch (const std::exception &error) { RCLCPP_FATAL(rclcpp::get_logger("step07_observer"), "%s", error.what()); if (rclcpp::ok()) rclcpp::shutdown(); return 2; }
  return 0;
}
#endif
