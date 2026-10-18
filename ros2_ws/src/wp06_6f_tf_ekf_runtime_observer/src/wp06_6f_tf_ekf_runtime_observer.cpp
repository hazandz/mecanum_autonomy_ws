#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <optional>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
#include <unistd.h>

#include <nlohmann/json.hpp>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rosgraph_msgs/msg/clock.hpp>
#include <tf2_msgs/msg/tf_message.hpp>

namespace wp06_6f_observer
{
using Json = nlohmann::json;
constexpr const char * kSchema = "wp06_6f_cpp_runtime_observer/v2";
constexpr const char * kExpectedEkfNodeName = "ekf_filter_node";
constexpr std::int64_t kNsPerSecond = 1000000000LL;
constexpr double kTolerance = 1e-9;

std::string now_iso8601();

std::optional<std::string> canonical_gid(const uint8_t * data, std::size_t size)
{
  if (data == nullptr || size == 0) {
    return std::nullopt;
  }
  bool nonzero = false;
  std::ostringstream stream;
  stream << std::hex << std::setfill('0');
  for (std::size_t index = 0; index < size; ++index) {
    nonzero = nonzero || data[index] != 0;
    stream << std::setw(2) << static_cast<unsigned int>(data[index]);
  }
  if (!nonzero) {
    return std::nullopt;
  }
  return stream.str();
}

bool is_dynamic_odom_edge(const std::string & parent, const std::string & child)
{
  return parent == "odom" && child == "base_link";
}

bool is_map_odom_edge(const std::string & parent, const std::string & child)
{
  return parent == "map" && child == "odom";
}

bool strictly_increasing_nonzero(const std::vector<std::int64_t> & values)
{
  return values.size() >= 5 && values.front() > 0 &&
         std::adjacent_find(values.begin(), values.end(), std::greater_equal<std::int64_t>()) == values.end();
}

struct EndpointRecord
{
  std::string gid;
  std::string node_name;
  std::string node_namespace;
  std::string topic_type;
};

struct EndpointMapping
{
  bool unique{false};
  bool expected_owner{false};
  std::size_t match_count{0};
  std::optional<EndpointRecord> endpoint;
};

EndpointMapping map_gid_to_endpoint(
  const std::string & gid, const std::vector<EndpointRecord> & endpoints,
  const std::string & expected_node_name)
{
  EndpointMapping result;
  for (const auto & endpoint : endpoints) {
    if (endpoint.gid == gid) {
      ++result.match_count;
      result.endpoint = endpoint;
    }
  }
  result.unique = result.match_count == 1;
  result.expected_owner = result.unique && result.endpoint->node_name == expected_node_name &&
    result.endpoint->node_namespace == "/" && result.endpoint->topic_type == "tf2_msgs/msg/TFMessage";
  return result;
}

struct TeardownRecord
{
  int leader_returncode{0};
  std::vector<int> live_member_pids;
  std::vector<int> zombie_member_pids;
  std::string outcome;
};

bool teardown_pass(const TeardownRecord & record)
{
  return record.leader_returncode == 0 && record.live_member_pids.empty() &&
         record.zombie_member_pids.empty() && record.outcome == "STOPPED";
}

rclcpp::QoS dynamic_tf_qos()
{
  auto qos = rclcpp::QoS(rclcpp::KeepLast(100));
  qos.best_effort();
  qos.durability_volatile();
  return qos;
}

rclcpp::QoS static_tf_qos()
{
  auto qos = rclcpp::QoS(rclcpp::KeepLast(1));
  qos.reliable();
  qos.transient_local();
  return qos;
}

Json qos_json(const rclcpp::QoS & qos)
{
  const auto & profile = qos.get_rmw_qos_profile();
  const char * history = profile.history == RMW_QOS_POLICY_HISTORY_KEEP_LAST ? "KEEP_LAST" : "UNKNOWN";
  const char * reliability = profile.reliability == RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT ?
    "BEST_EFFORT" : profile.reliability == RMW_QOS_POLICY_RELIABILITY_RELIABLE ? "RELIABLE" : "UNKNOWN";
  const char * durability = profile.durability == RMW_QOS_POLICY_DURABILITY_VOLATILE ?
    "VOLATILE" : profile.durability == RMW_QOS_POLICY_DURABILITY_TRANSIENT_LOCAL ? "TRANSIENT_LOCAL" : "UNKNOWN";
  return Json{{"depth", profile.depth}, {"durability", durability}, {"history", history},
    {"reliability", reliability}};
}

std::int64_t stamp_ns(const builtin_interfaces::msg::Time & stamp)
{
  return static_cast<std::int64_t>(stamp.sec) * kNsPerSecond + stamp.nanosec;
}

Json stamp_json(const builtin_interfaces::msg::Time & stamp)
{
  return Json{{"nanosec", stamp.nanosec}, {"sec", stamp.sec}};
}

bool valid_nonzero_stamp(const builtin_interfaces::msg::Time & stamp)
{
  return stamp.sec >= 0 && stamp.nanosec < 1000000000U && stamp_ns(stamp) > 0;
}

bool finite_pose_twist(const nav_msgs::msg::Odometry & message)
{
  const auto & p = message.pose.pose.position;
  const auto & q = message.pose.pose.orientation;
  const auto & v = message.twist.twist.linear;
  const auto & w = message.twist.twist.angular;
  const std::array<double, 13> values{
    p.x, p.y, p.z, q.x, q.y, q.z, q.w,
    v.x, v.y, v.z, w.x, w.y, w.z};
  return std::all_of(values.begin(), values.end(), [](double value) {return std::isfinite(value);}) &&
         std::all_of(message.pose.covariance.begin(), message.pose.covariance.end(),
           [](double value) {return std::isfinite(value);}) &&
         std::all_of(message.twist.covariance.begin(), message.twist.covariance.end(),
           [](double value) {return std::isfinite(value);});
}

bool exact_static_transform(const geometry_msgs::msg::TransformStamped & transform)
{
  const auto & t = transform.transform.translation;
  const auto & q = transform.transform.rotation;
  return std::abs(t.x + 0.031765) <= kTolerance && std::abs(t.y) <= kTolerance &&
         std::abs(t.z - 0.140) <= kTolerance && std::abs(q.x) <= kTolerance &&
         std::abs(q.y) <= kTolerance && std::abs(q.z) <= kTolerance &&
         std::abs(q.w - 1.0) <= kTolerance;
}

std::vector<std::int64_t> valid_sample_times(const Json & samples)
{
  std::vector<std::int64_t> result;
  for (const auto & sample : samples) {
    if (sample.value("valid", false)) {
      result.push_back(sample.value("stamp_ns", std::int64_t{0}));
    }
  }
  return result;
}

class Observer final : public rclcpp::Node
{
public:
  explicit Observer(std::string expected_ekf_node_name)
  : Node("wp06_6f_cpp_runtime_observer"), expected_ekf_node_name_(std::move(expected_ekf_node_name))
  {
    clock_sub_ = create_subscription<rosgraph_msgs::msg::Clock>(
      "/clock", rclcpp::QoS(100),
      [this](const rosgraph_msgs::msg::Clock & message, const rclcpp::MessageInfo &) {
        const auto & stamp = message.clock;
        const auto ns = stamp_ns(stamp);
        if (!valid_nonzero_stamp(stamp)) {
          ++clock_zero_count_;
          return;
        }
        clock_samples_.push_back(Json{{"stamp", stamp_json(stamp)}, {"stamp_ns", ns}, {"valid", true}});
      });

    odom_sub_ = create_subscription<nav_msgs::msg::Odometry>(
      "/odometry/filtered", rclcpp::QoS(100),
      [this](const nav_msgs::msg::Odometry & message, const rclcpp::MessageInfo &) {
        const auto & stamp = message.header.stamp;
        std::vector<std::string> reasons;
        if (!valid_nonzero_stamp(stamp)) {reasons.emplace_back("ODOMETRY_TIMESTAMP_ZERO_OR_INVALID");}
        if (message.header.frame_id != "odom" || message.child_frame_id != "base_link") {
          reasons.emplace_back("ODOMETRY_FRAME_CONTRACT_MISMATCH");
        }
        if (!finite_pose_twist(message)) {reasons.emplace_back("ODOMETRY_NONFINITE_POSE_TWIST_OR_COVARIANCE");}
        Json reason_json = reasons;
        odom_samples_.push_back(Json{
          {"message", odometry_json(message)}, {"rejection_reasons", reason_json},
          {"stamp", stamp_json(stamp)}, {"stamp_ns", stamp_ns(stamp)}, {"valid", reasons.empty()}});
      });

    tf_sub_ = create_subscription<tf2_msgs::msg::TFMessage>(
      "/tf", dynamic_tf_qos(),
      [this](const tf2_msgs::msg::TFMessage & message, const rclcpp::MessageInfo & info) {
        const auto & rmw_info = info.get_rmw_message_info();
        const auto gid = canonical_gid(rmw_info.publisher_gid.data, RMW_GID_STORAGE_SIZE);
        for (const auto & transform : message.transforms) {
          const auto & parent = transform.header.frame_id;
          const auto & child = transform.child_frame_id;
          if (is_map_odom_edge(parent, child)) {
            map_to_odom_seen_ = true;
            forbidden_edges_.push_back(Json{{"child", child}, {"parent", parent}, {"topic", "/tf"}});
          }
          if (!is_dynamic_odom_edge(parent, child)) {continue;}
          if (!gid) {
            errors_.push_back("TF_EDGE_PUBLISHER_GID_UNMAPPABLE");
            continue;
          }
          const auto & t = transform.transform.translation;
          const auto & q = transform.transform.rotation;
          const auto & stamp = transform.header.stamp;
          dynamic_tf_.push_back(Json{
            {"child", child}, {"parent", parent}, {"publisher_gid", *gid},
            {"rotation_xyzw", Json::array({q.x, q.y, q.z, q.w})},
            {"stamp", stamp_json(stamp)}, {"stamp_ns", stamp_ns(stamp)},
            {"translation", Json::array({t.x, t.y, t.z})},
            {"valid", valid_nonzero_stamp(stamp)}});
        }
      });

    auto static_qos = static_tf_qos();
    tf_static_sub_ = create_subscription<tf2_msgs::msg::TFMessage>(
      "/tf_static", static_qos,
      [this](const tf2_msgs::msg::TFMessage & message, const rclcpp::MessageInfo & info) {
        const auto & rmw_info = info.get_rmw_message_info();
        const auto gid = canonical_gid(rmw_info.publisher_gid.data, RMW_GID_STORAGE_SIZE);
        for (const auto & transform : message.transforms) {
          const auto & parent = transform.header.frame_id;
          const auto & child = transform.child_frame_id;
          if (is_map_odom_edge(parent, child)) {
            map_to_odom_seen_ = true;
            forbidden_edges_.push_back(Json{{"child", child}, {"parent", parent}, {"topic", "/tf_static"}});
          }
          if (parent != "base_link" || child != "lidar_frame") {continue;}
          const auto & t = transform.transform.translation;
          const auto & q = transform.transform.rotation;
          static_tf_.push_back(Json{
            {"child", child}, {"parent", parent}, {"publisher_gid", gid ? Json(*gid) : Json(nullptr)},
            {"rotation_xyzw", Json::array({q.x, q.y, q.z, q.w})},
            {"stamp", stamp_json(transform.header.stamp)},
            {"translation", Json::array({t.x, t.y, t.z})},
            {"valid", exact_static_transform(transform)}});
        }
      });
  }

  Json finish(bool window_complete)
  {
    Json endpoint_snapshot = Json::array();
    std::vector<EndpointRecord> endpoints;
    try {
      for (const auto & endpoint : get_publishers_info_by_topic("/tf")) {
        const auto canonical = canonical_gid(endpoint.endpoint_gid().data(), endpoint.endpoint_gid().size());
        if (!canonical) {
          errors_.push_back("GRAPH_ENDPOINT_GID_UNAVAILABLE");
          continue;
        }
        EndpointRecord row{*canonical, endpoint.node_name(), endpoint.node_namespace(), endpoint.topic_type()};
        endpoints.push_back(row);
        endpoint_snapshot.push_back(Json{
          {"gid", row.gid}, {"node_name", row.node_name}, {"node_namespace", row.node_namespace},
          {"topic_type", row.topic_type}});
      }
    } catch (const std::exception & error) {
      errors_.push_back(std::string("GRAPH_ENDPOINT_SNAPSHOT_FAILED:") + error.what());
    }

    std::set<std::string> edge_gids;
    for (const auto & edge : dynamic_tf_) {edge_gids.insert(edge.at("publisher_gid").get<std::string>());}
    Json gid_mapping = Json::array();
    bool gid_unmappable = false;
    bool gid_missing_on_edge = std::find(errors_.begin(), errors_.end(), "TF_EDGE_PUBLISHER_GID_UNMAPPABLE") != errors_.end();
    bool owner_is_ekf = !edge_gids.empty();
    for (const auto & gid : edge_gids) {
      auto mapping = map_gid_to_endpoint(gid, endpoints, expected_ekf_node_name_);
      gid_mapping.push_back(Json{
        {"expected_node_name", expected_ekf_node_name_}, {"gid", gid},
        {"match_count", mapping.match_count}, {"mapped_endpoint", mapping.endpoint ? Json{
          {"node_name", mapping.endpoint->node_name}, {"node_namespace", mapping.endpoint->node_namespace},
          {"topic_type", mapping.endpoint->topic_type}} : Json(nullptr)},
        {"unique", mapping.unique}, {"expected_owner", mapping.expected_owner}});
      gid_unmappable = gid_unmappable || !mapping.unique;
      owner_is_ekf = owner_is_ekf && mapping.expected_owner;
    }

    const auto clock_times = valid_sample_times(clock_samples_);
    const auto odom_times = valid_sample_times(odom_samples_);
    std::vector<std::int64_t> tf_times;
    for (const auto & edge : dynamic_tf_) {
      if (edge.value("valid", false)) {tf_times.push_back(edge.value("stamp_ns", std::int64_t{0}));}
    }
    bool odom_monotonic = strictly_increasing_nonzero(odom_times);
    bool clock_monotonic = strictly_increasing_nonzero(clock_times);
    bool tf_monotonic = strictly_increasing_nonzero(tf_times);
    bool clock_pass = clock_samples_.size() >= 5 && clock_monotonic;
    bool odom_pass = odom_samples_.size() >= 5 && odom_monotonic &&
      std::all_of(odom_samples_.begin(), odom_samples_.end(), [](const Json & sample) {return sample.value("valid", false);});
    const auto valid_tf_count = static_cast<std::size_t>(std::count_if(
      dynamic_tf_.begin(), dynamic_tf_.end(), [](const Json & edge) {return edge.value("valid", false);}));
    bool tf_pass = valid_tf_count >= 5 && tf_monotonic && edge_gids.size() == 1 && owner_is_ekf;
    bool static_pass = static_tf_.size() == 1 && static_tf_.front().value("valid", false);
    bool map_absent = !map_to_odom_seen_ && window_complete;
    bool no_errors = errors_.empty();

    Json acceptance{
      {"clock_minimum_five_nonzero_strictly_increasing", clock_pass},
      {"dynamic_odom_to_base_link_minimum_five_strictly_increasing_single_gid_owned_by_ekf", tf_pass},
      {"dynamic_tf_subscription_qos_contract", qos_json(dynamic_tf_qos()) ==
        Json{{"depth", 100}, {"durability", "VOLATILE"}, {"history", "KEEP_LAST"}, {"reliability", "BEST_EFFORT"}}},
      {"filtered_odometry_minimum_five_contract_and_monotonicity", odom_pass},
      {"map_to_odom_absent_during_full_window", map_absent},
      {"observer_errors_absent", no_errors},
      {"static_base_link_to_lidar_frame_exact", static_pass}};
    Json reasons = Json::object();
    if (!clock_pass) {reasons["/clock"] = clock_samples_.size() < 5 ? "CLOCK_TIMEOUT_MINIMUM_FIVE_SAMPLES" : "CLOCK_TIMESTAMP_NOT_STRICTLY_INCREASING";}
    if (!odom_pass) {reasons["/odometry/filtered"] = odom_samples_.size() < 5 ? "FILTERED_ODOMETRY_TIMEOUT_MINIMUM_FIVE_SAMPLES" : "FILTERED_ODOMETRY_CONTRACT_OR_MONOTONICITY_FAILED";}
    if (!tf_pass) {
      if (gid_unmappable || gid_missing_on_edge) {reasons["/tf:odom->base_link"] = "TF_EDGE_PUBLISHER_GID_UNMAPPABLE";}
      else if (edge_gids.size() == 1 && !owner_is_ekf) {reasons["/tf:odom->base_link"] = "TF_EDGE_PUBLISHER_NOT_EKF";}
      else if (!tf_monotonic) {reasons["/tf:odom->base_link"] = "TF_DYNAMIC_TIMESTAMP_NOT_STRICTLY_INCREASING";}
      else {reasons["/tf:odom->base_link"] = "TF_DYNAMIC_TIMEOUT_MINIMUM_FIVE_EDGES_OR_GIDS";}
    }
    if (!static_pass) {reasons["/tf_static:base_link->lidar_frame"] = "TF_STATIC_EDGE_MISSING_OR_TRANSFORM_MISMATCH";}
    if (map_to_odom_seen_) {reasons["map->odom"] = "MAP_TO_ODOM_EDGE_OBSERVED";}
    else if (!window_complete) {reasons["map->odom"] = "TF_OBSERVATION_WINDOW_INCOMPLETE";}
    if (!no_errors) {reasons["observer_errors"] = "RUNTIME_OBSERVER_CALLBACK_OR_API_ERROR";}
    const bool all_pass = std::all_of(acceptance.begin(), acceptance.end(), [](const auto & row) {return row.template get<bool>();});
    std::string outcome = all_pass ? "PASS" : "FAIL_NO_RETRY";
    if (gid_unmappable || gid_missing_on_edge) {outcome = "TF_EDGE_PUBLISHER_GID_UNMAPPABLE";}

    return Json{
      {"acceptance", acceptance}, {"duration_seconds", duration_seconds_},
      {"endpoint_mapping", gid_mapping}, {"expected_ekf_node_name", expected_ekf_node_name_},
      {"failure_reason_literals", reasons}, {"graph_endpoint_snapshot", endpoint_snapshot},
      {"observed_forbidden_edges", forbidden_edges_},
      {"map_to_odom_seen", map_to_odom_seen_}, {"observer_errors", errors_},
      {"qos_used", Json{{"/tf", qos_json(dynamic_tf_qos())}, {"/tf_static", qos_json(static_tf_qos())}}},
      {"schema", kSchema}, {"started_at", started_at_}, {"finished_at", now()},
      {"terminal_outcome", outcome}, {"topics", Json{
        {"/clock", Json{{"samples", clock_samples_}, {"type", "rosgraph_msgs/msg/Clock"}, {"zero_samples_ignored", clock_zero_count_}}},
        {"/odometry/filtered", Json{{"samples", odom_samples_}, {"type", "nav_msgs/msg/Odometry"}}},
        {"/tf", Json{{"transforms", dynamic_tf_}, {"type", "tf2_msgs/msg/TFMessage"}, {"window_complete", window_complete}}},
        {"/tf_static", Json{{"transforms", static_tf_}, {"type", "tf2_msgs/msg/TFMessage"}, {"window_complete", window_complete}}}}},
      {"window_complete", window_complete}};
  }

  void set_window(double seconds, std::string started)
  {
    duration_seconds_ = seconds;
    started_at_ = std::move(started);
  }

private:
  static std::string now()
  {
    const auto value = std::chrono::system_clock::now().time_since_epoch();
    return std::to_string(std::chrono::duration_cast<std::chrono::nanoseconds>(value).count());
  }

  template<typename VectorLike>
  static Json vector3_json(const VectorLike & value)
  {
    return Json{{"x", value.x}, {"y", value.y}, {"z", value.z}};
  }

  static Json quaternion_json(const geometry_msgs::msg::Quaternion & value)
  {
    return Json{{"w", value.w}, {"x", value.x}, {"y", value.y}, {"z", value.z}};
  }

  static Json odometry_json(const nav_msgs::msg::Odometry & value)
  {
    return Json{
      {"child_frame_id", value.child_frame_id},
      {"header", Json{{"frame_id", value.header.frame_id}, {"stamp", stamp_json(value.header.stamp)}}},
      {"pose", Json{{"covariance", value.pose.covariance}, {"pose", Json{
        {"orientation", quaternion_json(value.pose.pose.orientation)},
        {"position", vector3_json(value.pose.pose.position)}}}}},
      {"twist", Json{{"covariance", value.twist.covariance}, {"twist", Json{
        {"angular", vector3_json(value.twist.twist.angular)},
        {"linear", vector3_json(value.twist.twist.linear)}}}}}};
  }

  static std::string now_string()
  {
    const auto value = std::chrono::system_clock::now().time_since_epoch();
    return std::to_string(std::chrono::duration_cast<std::chrono::nanoseconds>(value).count());
  }

  std::string expected_ekf_node_name_;
  std::string started_at_;
  double duration_seconds_{0.0};
  std::size_t clock_zero_count_{0};
  bool map_to_odom_seen_{false};
  std::vector<std::string> errors_;
  Json forbidden_edges_{Json::array()};
  Json clock_samples_{Json::array()};
  Json odom_samples_{Json::array()};
  Json dynamic_tf_{Json::array()};
  Json static_tf_{Json::array()};
  rclcpp::Subscription<rosgraph_msgs::msg::Clock>::SharedPtr clock_sub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Subscription<tf2_msgs::msg::TFMessage>::SharedPtr tf_sub_;
  rclcpp::Subscription<tf2_msgs::msg::TFMessage>::SharedPtr tf_static_sub_;
};

bool atomic_write_json(const std::filesystem::path & output, const Json & value)
{
  const auto temporary = output.string() + ".tmp." + std::to_string(::getpid());
  {
    std::ofstream stream(temporary, std::ios::binary | std::ios::trunc);
    if (!stream) {return false;}
    stream << value.dump(-1, ' ', false, Json::error_handler_t::strict);
    stream.flush();
    if (!stream) {return false;}
  }
  std::error_code error;
  std::filesystem::rename(temporary, output, error);
  if (error) {
    std::filesystem::remove(temporary);
    return false;
  }
  return true;
}

int run(const std::filesystem::path & output, double duration_seconds, const std::string & expected_ekf_node_name)
{
  const auto started = std::chrono::steady_clock::now();
  const auto started_at = now_iso8601();
  Json result;
  bool window_complete = false;
  try {
    rclcpp::init(0, nullptr);
    auto node = std::make_shared<Observer>(expected_ekf_node_name);
    node->set_window(duration_seconds, started_at);
    rclcpp::executors::SingleThreadedExecutor executor;
    executor.add_node(node);
    const auto deadline = started + std::chrono::duration<double>(duration_seconds);
    while (std::chrono::steady_clock::now() < deadline && rclcpp::ok()) {
      executor.spin_some(std::chrono::milliseconds(20));
    }
    window_complete = rclcpp::ok() && std::chrono::steady_clock::now() >= deadline;
    result = node->finish(window_complete);
    executor.remove_node(node);
    node.reset();
    rclcpp::shutdown();
  } catch (const std::exception & error) {
    result = Json{{"observer_errors", Json::array({std::string("OBSERVER_RUNTIME_ERROR:") + error.what()})},
      {"schema", kSchema}, {"terminal_outcome", "FAIL_NO_RETRY"}, {"window_complete", false}};
    if (rclcpp::ok()) {rclcpp::shutdown();}
  }
  result["finished_at"] = now_iso8601();
  result["started_at"] = started_at;
  result["window_seconds_requested"] = duration_seconds;
  if (!atomic_write_json(output, result)) {
    std::cerr << "OBSERVER_ATOMIC_WRITE_FAILED\n";
    return 2;
  }
  return result.value("terminal_outcome", std::string("FAIL_NO_RETRY")) == "PASS" ? 0 : 1;
}

std::string now_iso8601()
{
  const auto time = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
  std::tm value{};
  gmtime_r(&time, &value);
  std::ostringstream stream;
  stream << std::put_time(&value, "%Y-%m-%dT%H:%M:%SZ");
  return stream.str();
}

}  // namespace wp06_6f_observer

#ifndef WP06_OBSERVER_TESTING
int main(int argc, char ** argv)
{
  std::filesystem::path output;
  double duration = 30.0;
  std::string expected_node = wp06_6f_observer::kExpectedEkfNodeName;
  for (int index = 1; index < argc; ++index) {
    const std::string argument(argv[index]);
    if (argument == "--output" && index + 1 < argc) {output = argv[++index];}
    else if (argument == "--duration-seconds" && index + 1 < argc) {duration = std::stod(argv[++index]);}
    else if (argument == "--expected-ekf-node-name" && index + 1 < argc) {expected_node = argv[++index];}
    else {std::cerr << "OBSERVER_ARGUMENT_INVALID\n"; return 2;}
  }
  if (output.empty() || duration <= 0.0 || expected_node.empty()) {
    std::cerr << "OBSERVER_ARGUMENT_INVALID\n";
    return 2;
  }
  return wp06_6f_observer::run(output, duration, expected_node);
}
#endif
