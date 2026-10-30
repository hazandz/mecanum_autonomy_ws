#include <array>
#include <atomic>
#include <chrono>
#include <deque>
#include <cmath>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <random>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

#include <gz/math/Quaternion.hh>
#include <gz/msgs/odometry.pb.h>
#include <gz/msgs/Utility.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/World.hh>
#include <gz/sim/components/ContactSensor.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <mecanum_nav_rl_interfaces/msg/final_issued_command_receipt.hpp>
#include <mecanum_nav_rl_interfaces/msg/local_training_safety_input.hpp>
#include <mecanum_nav_rl_interfaces/msg/simulation_contact_state.hpp>

#include "mecanum_sim_backend/backend_system.hpp"
#include "mecanum_sim_backend/contact_coverage.hpp"
#include "mecanum_sim_backend/receipt_gate.hpp"

namespace mecanum_sim_backend
{
namespace
{
using Receipt = mecanum_nav_rl_interfaces::msg::FinalIssuedCommandReceipt;
using SafetyInput = mecanum_nav_rl_interfaces::msg::LocalTrainingSafetyInput;
using BackendState = mecanum_nav_rl_interfaces::msg::SimulationContactState;
using SteadyClock = std::chrono::steady_clock;

std::int64_t NowSteadyNs()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      SteadyClock::now().time_since_epoch()).count();
}
std::int64_t TimeNs(const gz::sim::UpdateInfo &info)
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
}
std::uint64_t BootNonce()
{
  std::random_device random;
  auto value = (static_cast<std::uint64_t>(random()) << 32U) ^ random() ^
      static_cast<std::uint64_t>(NowSteadyNs());
  return value == 0 ? 1 : value;
}
bool Finite(const gz::math::Pose3d &pose)
{
  return std::isfinite(pose.Pos().X()) && std::isfinite(pose.Pos().Y()) &&
         std::isfinite(pose.Pos().Z()) && std::isfinite(pose.Rot().X()) &&
         std::isfinite(pose.Rot().Y()) && std::isfinite(pose.Rot().Z()) &&
         std::isfinite(pose.Rot().W());
}
std::uint64_t ParseU64(const std::shared_ptr<const sdf::Element> &sdf,
                       const std::string &name)
{
  return sdf->Get<std::uint64_t>(name, 0).first;
}
}  // namespace

class BackendSystem final : public gz::sim::System,
                            public gz::sim::ISystemConfigure,
                            public gz::sim::ISystemPreUpdate,
                            public gz::sim::ISystemPostUpdate
{
public:
  ~BackendSystem() override
  {
    if (executor_) executor_->cancel();
    if (executor_thread_.joinable()) executor_thread_.join();
    if (context_ && context_->is_valid()) context_->shutdown("backend shutdown");
  }

  void Configure(const gz::sim::Entity &entity,
                 const std::shared_ptr<const sdf::Element> &sdf,
                 gz::sim::EntityComponentManager &ecm,
                 gz::sim::EventManager &) override
  {
    world_entity_ = entity;
    world_name_ = sdf->Get<std::string>("world_name", "b2_training_arena").first;
    session_id_ = sdf->Get<std::string>("session_id", "").first;
    config_hash_ = sdf->Get<std::string>("config_hash", "").first;
    asset_manifest_hash_ = sdf->Get<std::string>("asset_manifest_sha256", "").first;
    const auto final_instance = ParseU64(sdf, "final_publisher_instance_id");
    const auto safe_instance = ParseU64(sdf, "safe_stop_source_instance_id");
    policy_instance_id_ = ParseU64(sdf, "policy_source_instance_id");
    model_name_ = sdf->Get<std::string>("robot_entity", "mecanum_b2").first;
    base_link_name_ = sdf->Get<std::string>("base_link", "base_link").first;
    world_ = gz::sim::World(entity);
    model_entity_ = world_.ModelByName(ecm, model_name_);
    if (model_entity_ == gz::sim::kNullEntity)
    {
      SetFault(BackendState::FAULT_CONTEXT, "robot_model_missing");
      return;
    }
    model_ = gz::sim::Model(model_entity_);
    const auto link_entity = model_.LinkByName(ecm, base_link_name_);
    if (link_entity == gz::sim::kNullEntity)
    {
      SetFault(BackendState::FAULT_CONTEXT, "base_link_missing");
      return;
    }
    base_link_ = gz::sim::Link(link_entity);
    base_link_.EnableVelocityChecks(ecm);

    GateBinding binding;
    binding.session_id = session_id_;
    binding.config_hash = config_hash_;
    binding.final_publisher_instance_id = final_instance;
    binding.safe_stop_source_instance_id = safe_instance;
    binding.policy_source_instance_id = policy_instance_id_;
    binding.next_safe_stop_sequence = ParseU64(sdf, "first_safe_stop_sequence");
    binding.barrier_stamp_ns = 0;
    gate_ = std::make_unique<ReceiptGate>(std::move(binding));

    std::uint32_t tracked_count = 0;
    auto plugin_sdf = sdf->Clone();
    if (plugin_sdf->HasElement("tracked_collision"))
    {
      auto item = plugin_sdf->GetElement("tracked_collision");
      while (item)
      {
        const auto name = item->Get<std::string>();
        const auto matches = gz::sim::entitiesFromScopedName(name, ecm);
        if (matches.size() != 1)
          SetFault(BackendState::FAULT_CONTACT_COVERAGE, "collision_manifest_resolution_not_unique");
        collision_bits_[name] = (tracked_count < 64) ? (std::uint64_t{1} << tracked_count) : 0;
        ++tracked_count;
        item = item->GetNextElement("tracked_collision");
      }
    }
    contact_coverage_ = std::make_unique<ContactCoverage>(tracked_count);
    backend_instance_id_ = BootNonce();
    if (tracked_count == 0 || tracked_count > 64 || asset_manifest_hash_.size() != 64)
      SetFault(BackendState::FAULT_CONTACT_COVERAGE, "invalid_asset_contact_manifest");
    if (sdf->HasElement("contact_probe_collision"))
      probe_collision_name_ = sdf->Get<std::string>("contact_probe_collision");

    // Each sensor name is bound by the same installed asset manifest. An
    // absent or stale ContactSensorData component is a health fault.
    for (const auto &[collision, bit] : collision_bits_)
    {
      const auto separator = collision.rfind("::");
      const auto collision_leaf = separator == std::string::npos ? collision : collision.substr(separator + 2);
      auto sensor_scoped = collision.substr(0, separator + 2) + collision_leaf + "_contact_sensor";
      const auto sensors = gz::sim::entitiesFromScopedName(sensor_scoped, ecm);
      if (sensors.size() != 1)
      {
        SetFault(BackendState::FAULT_CONTACT_COVERAGE, "contact_sensor_manifest_resolution_failed");
      }
      else sensor_bits_[*sensors.begin()] = bit;
    }

    try
    {
      context_ = std::make_shared<rclcpp::Context>();
      context_->init(0, nullptr);
      rclcpp::NodeOptions options; options.context(context_);
      node_ = std::make_shared<rclcpp::Node>("mecanum_sim_backend", options);
      const auto receipt_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
      const auto twist_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().durability_volatile();
      const auto input_qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
      const auto state_qos = rclcpp::QoS(rclcpp::KeepLast(50)).reliable().durability_volatile();
      receipt_sub_ = node_->create_subscription<Receipt>(
          "/mecanum/final_issued_command_receipt", receipt_qos,
          [this](Receipt::ConstSharedPtr msg) { OnReceipt(*msg); });
      twist_sub_ = node_->create_subscription<geometry_msgs::msg::Twist>(
          "/cmd_vel", twist_qos,
          [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
            std::lock_guard<std::mutex> lock(callback_mutex_);
            captured_twist_ = *msg; captured_twist_received_steady_ns_ = NowSteadyNs();
          });
      safety_sub_ = node_->create_subscription<SafetyInput>(
          "/mecanum/local_training/safety_input", input_qos,
          [this](SafetyInput::ConstSharedPtr msg) { OnSafetyInput(*msg); });
      state_pub_ = node_->create_publisher<BackendState>(
          "/mecanum/local_training/backend_state", state_qos);
      rclcpp::ExecutorOptions executor_options;
      executor_options.context = context_;
      executor_ = std::make_shared<rclcpp::executors::SingleThreadedExecutor>(
          executor_options);
      executor_->add_node(node_);
      executor_thread_ = std::thread([this] { executor_->spin(); });
      gt_publisher_ = gt_pub_.Advertise<gz::msgs::Odometry>("/b2/ground_truth/odom");
    }
    catch (const std::exception &error)
    {
      SetFault(BackendState::FAULT_CONTEXT, std::string("ros_transport_init_failed:") + error.what());
    }
    last_sim_ns_ = 0;
    last_sim_advance_steady_ns_ = NowSteadyNs();
    configured_ = gate_ && node_ && base_link_.Valid(ecm) && fault_flags_ == 0;
  }

  void PreUpdate(const gz::sim::UpdateInfo &info,
                 gz::sim::EntityComponentManager &ecm) override
  {
    ProcessCallbackInputs();
    const auto pending_faults = callback_fault_flags_.exchange(0);
    if (pending_faults != 0) SetFault(pending_faults, "ros_callback_queue_or_context_fault");
    if (!configured_ || info.paused) { local_zero_override_ = true; return; }
    const auto now_steady = NowSteadyNs();
    const auto now_sim = TimeNs(info);
    if (now_sim < last_sim_ns_)
    {
      gate_->Invalidate("simulation_clock_rollback");
      SetFault(BackendState::FAULT_CLOCK, "simulation_clock_rollback");
    }
    if (now_sim > last_sim_ns_)
    {
      last_sim_ns_ = now_sim;
      last_sim_advance_steady_ns_ = now_steady;
    }
    const auto stalled_ns = now_steady - last_sim_advance_steady_ns_;
    if (stalled_ns > 1'000'000'000)
      SetFault(BackendState::FAULT_CLOCK, "simulation_clock_stall_infrastructure_abort");
    else if (stalled_ns > 200'000'000)
      fault_flags_ |= BackendState::FAULT_CLOCK;

    GateResult decision;
    {
      std::lock_guard<std::mutex> lock(callback_mutex_);
      decision = gate_->ConsumeNext(now_sim, now_steady);
    }
    if (decision.disposition == GateDisposition::Faulted)
      SetFault(BackendState::FAULT_COMMAND_SEQUENCE, decision.reason);
    if (decision.disposition == GateDisposition::Applied ||
        decision.disposition == GateDisposition::Anchored)
    {
      selected_receipt_ = decision.accepted;
      selected_steady_ns_ = now_steady;
    }

    if (gate_->WatchdogExpired(now_steady))
    {
      fault_flags_ |= BackendState::FAULT_COMMAND_STALE;
      gate_->Invalidate("actuator_watchdog_expired");
      local_zero_override_ = true;
      ApplyEmergencyZero(ecm);
      return;
    }
    if (policy_open_ && (safety_receive_steady_ns_ == 0 || now_steady < safety_receive_steady_ns_ ||
        now_steady - safety_receive_steady_ns_ > 250'000'000))
    {
      fault_flags_ |= BackendState::FAULT_COMMAND_STALE;
      gate_->Invalidate("safety_input_steady_age_exceeded");
      local_zero_override_ = true;
      ApplyEmergencyZero(ecm);
      return;
    }
    const bool selected_safe_stop = decision.accepted && decision.accepted->source == Receipt::SOURCE_SAFE_STOP;
    if (fault_flags_ != 0 || (!policy_open_ && !selected_safe_stop) || contact_decision_.contact_active ||
        !contact_decision_.healthy || !measurement_healthy_)
    {
      local_zero_override_ = true;
      ApplyEmergencyZero(ecm);
      return;
    }
    if (decision.accepted)
    {
      std::string reason;
      const auto pose = base_link_.WorldPose(ecm);
      const auto world_linear = base_link_.WorldLinearVelocity(ecm);
      const auto world_angular = base_link_.WorldAngularVelocity(ecm);
      if (!pose || !world_linear || !world_angular || !Finite(*pose))
      {
        measurement_healthy_ = false;
        fault_flags_ |= BackendState::FAULT_ACTUATOR;
        local_zero_override_ = true;
        ApplyEmergencyZero(ecm);
        return;
      }
      const auto &q = pose->Rot();
      MeasuredWorldTwist3D measurement{{world_linear->X(), world_linear->Y(), world_linear->Z()},
                                       {world_angular->X(), world_angular->Y(), world_angular->Z()}};
      const auto &twist = decision.accepted->twist;
      const auto command = ComposeBodyPlanarCommand(
          measurement, {q.X(), q.Y(), q.Z(), q.W()},
          twist[0], twist[1], twist[5], reason);
      if (!command)
      {
        fault_flags_ |= BackendState::FAULT_ACTUATOR;
        local_zero_override_ = true;
        ApplyEmergencyZero(ecm);
        return;
      }
      base_link_.SetLinearVelocity(ecm, {command->linear[0], command->linear[1], command->linear[2]});
      base_link_.SetAngularVelocity(ecm, {command->angular[0], command->angular[1], command->angular[2]});
      pending_applied_receipt_ = decision.accepted;
      local_zero_override_ = false;
    }
  }

  void PostUpdate(const gz::sim::UpdateInfo &info,
                  const gz::sim::EntityComponentManager &ecm) override
  {
    ++status_sequence_;
    physics_iteration_ = info.iterations;
    const auto sim_ns = TimeNs(info);
    const auto pose = base_link_.WorldPose(ecm);
    const auto world_linear = base_link_.WorldLinearVelocity(ecm);
    const auto world_angular = base_link_.WorldAngularVelocity(ecm);
    measurement_healthy_ = pose && world_linear && world_angular && Finite(*pose) &&
      std::isfinite(world_linear->X()) && std::isfinite(world_linear->Y()) && std::isfinite(world_linear->Z()) &&
      std::isfinite(world_angular->X()) && std::isfinite(world_angular->Y()) && std::isfinite(world_angular->Z());
    if (measurement_healthy_)
    {
      const auto &q = pose->Rot();
      const auto body_linear = RotateWorldToBody({world_linear->X(), world_linear->Y(), world_linear->Z()},
                                                  {q.X(), q.Y(), q.Z(), q.W()});
      const auto body_angular = RotateWorldToBody({world_angular->X(), world_angular->Y(), world_angular->Z()},
                                                   {q.X(), q.Y(), q.Z(), q.W()});
      PublishGroundTruth(*pose, body_linear, body_angular, sim_ns);
    }
    else SetFault(BackendState::FAULT_CONTEXT, "ground_truth_measurement_missing_or_non_finite");

    auto sample = BuildContactSample(info, ecm);
    contact_decision_ = contact_coverage_->Observe(sample);
    if (!contact_decision_.healthy && !info.paused &&
        contact_decision_.reason != "contact_capability_unverified")
      fault_flags_ |= contact_decision_.fault_flags ? contact_decision_.fault_flags : BackendState::FAULT_CONTACT_COVERAGE;
    if (state_pub_) PublishBackendState(info, sim_ns);
  }

private:
  void OnReceipt(const Receipt &msg)
  {
    ReceiptFacts facts;
    facts.session_id = session_id_; facts.config_hash = config_hash_;
    facts.key = {msg.final_publisher_instance_id, msg.final_publish_sequence};
    facts.episode_generation = msg.episode_generation; facts.reset_epoch = msg.reset_epoch;
    facts.runtime_generation = msg.runtime_generation; facts.step_index = msg.step_index;
    facts.transition_id = msg.transition_id; facts.source = msg.source; facts.sequence = msg.sequence;
    facts.source_instance_id = msg.source_instance_id;
    facts.stamp_ns = static_cast<std::int64_t>(msg.header.stamp.sec) * 1'000'000'000LL + msg.header.stamp.nanosec;
    facts.frame_id = msg.header.frame_id;
    facts.twist = {msg.final_command.linear.x, msg.final_command.linear.y,
                   msg.final_command.linear.z, msg.final_command.angular.x,
                   msg.final_command.angular.y, msg.final_command.angular.z};
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (!gate_->Enqueue(std::move(facts), NowSteadyNs()))
      callback_fault_flags_.fetch_or(BackendState::FAULT_QUEUE);
  }

  void OnSafetyInput(const SafetyInput &msg)
  {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (safety_queue_.size() >= ReceiptGate::kQueueCapacity)
    { callback_fault_flags_.fetch_or(BackendState::FAULT_QUEUE); return; }
    safety_queue_.push_back({msg, NowSteadyNs()});
  }

  void ProcessCallbackInputs()
  {
    std::deque<std::pair<SafetyInput, std::int64_t>> pending;
    {
      std::lock_guard<std::mutex> lock(callback_mutex_);
      pending.swap(safety_queue_);
    }
    for (const auto &[msg, received_ns] : pending)
    {
      if (msg.session_id != session_id_ || msg.config_hash != config_hash_ ||
          msg.schema_version != SafetyInput::SCHEMA_VERSION || msg.ingress_instance_id == 0)
      { SetFault(BackendState::FAULT_CONTEXT, "safety_input_identity_invalid"); continue; }
      safety_input_ = msg;
      safety_receive_steady_ns_ = received_ns;
    if (msg.admission_state == SafetyInput::ADMISSION_POLICY_OPEN &&
        msg.odometry_status == SafetyInput::ODOM_VALID &&
        msg.measured_twist.size() == 3 && msg.observation0_cutoff.sec >= 0 &&
        msg.observation0_final_publisher_instance_id != 0 &&
        msg.observation0_final_publish_sequence != 0 && last_accepted_key_ &&
        last_accepted_key_->publisher_instance_id == msg.observation0_final_publisher_instance_id &&
        last_accepted_key_->publish_sequence == msg.observation0_final_publish_sequence &&
        !local_zero_override_ && contact_decision_.healthy && !contact_decision_.contact_active &&
        fault_flags_ == 0)
    {
      policy_open_ = true;
      // B2.1's public safety input deliberately has no POLICY issuance key.
      // B2.3 must bind the exact pending-step identity through its trusted port.
    }
    else if (msg.admission_state != SafetyInput::ADMISSION_POLICY_OPEN)
      policy_open_ = false;
    }
  }

  void ApplyEmergencyZero(gz::sim::EntityComponentManager &ecm)
  {
    base_link_.SetLinearVelocity(ecm, {0, 0, 0});
    base_link_.SetAngularVelocity(ecm, {0, 0, 0});
    pending_applied_receipt_.reset();
    local_zero_override_ = true;
  }

  ContactSample BuildContactSample(const gz::sim::UpdateInfo &info,
                                   const gz::sim::EntityComponentManager &ecm)
  {
    ContactSample out; out.physics_iteration = info.iterations;
    out.sim_stamp_ns = TimeNs(info); out.required_mask = collision_bits_.empty() ? 0 :
      ((collision_bits_.size() == 64) ? ~std::uint64_t{0} : ((std::uint64_t{1} << collision_bits_.size()) - 1));
    out.paused = info.paused;
    for (const auto &[sensor, bit] : sensor_bits_)
    {
      const auto *component = ecm.Component<gz::sim::components::ContactSensorData>(sensor);
      if (!component) continue;
      const auto &contacts = component->Data();
      const auto *stamp = contacts.has_header() && contacts.header().has_stamp() ?
        &contacts.header().stamp() : nullptr;
      if (stamp && static_cast<std::int64_t>(stamp->sec()) * 1'000'000'000LL + stamp->nsec() == out.sim_stamp_ns)
      {
        out.observed_mask |= bit;
        out.component_present = true;
      }
      for (int i = 0; i < contacts.contact_size(); ++i)
      {
        const auto &contact = contacts.contact(i);
        const auto name1 = contact.collision1().name(); const auto name2 = contact.collision2().name();
        const bool has_probe = name1 == probe_collision_name_ || name2 == probe_collision_name_;
        if (has_probe) contact_capability_verified_ = true;
        bool tracked_pair = collision_bits_.find(name1) != collision_bits_.end() ||
          collision_bits_.find(name2) != collision_bits_.end();
        if (!tracked_pair) continue;
        const bool floor = name1.find("ground_plane") != std::string::npos || name2.find("ground_plane") != std::string::npos;
        const bool wheel = name1.find("Wheel_") != std::string::npos || name2.find("Wheel_") != std::string::npos;
        if (floor && wheel)
        {
          out.wheel_floor_pair = true;
          out.wheel_floor_aggregated = true;
          if (contact.normal_size() == 0 || contact.depth_size() == 0 ||
              contact.normal_size() != contact.depth_size())
          {
            out.wheel_floor_unclassifiable = true;
            continue;
          }
          for (int j = 0; j < contact.normal_size(); ++j)
          {
            const auto &normal = contact.normal(j);
            const double nx = normal.x(), ny = normal.y(), nz = normal.z();
            const double depth = contact.depth(j);
            const double norm = std::sqrt(nx * nx + ny * ny + nz * nz);
            if (!std::isfinite(nx) || !std::isfinite(ny) || !std::isfinite(nz) ||
                !std::isfinite(depth) || norm <= 0.0 || depth < 0.0)
            {
              out.wheel_floor_unclassifiable = true;
              continue;
            }
            constexpr double cos15 = 0.9659258262890683;
            if (std::abs(nz) / norm < cos15 || depth > 0.005)
              out.wheel_floor_contact = true;
          }
        }
        else out.has_robot_external_contact = true;
      }
    }
    out.capability_valid = contact_capability_verified_;
    return out;
  }

  void PublishGroundTruth(const gz::math::Pose3d &pose,
                          const std::array<double,3> &linear,
                          const std::array<double,3> &angular,
                          std::int64_t stamp_ns)
  {
    gz::msgs::Odometry msg;
    auto *frame = msg.mutable_header()->add_data();
    frame->set_key("frame_id"); frame->add_value("world");
    auto *child_frame = msg.mutable_header()->add_data();
    child_frame->set_key("child_frame_id"); child_frame->add_value("base_link");
    auto *p = msg.mutable_pose(); auto *pos = p->mutable_position();
    pos->set_x(pose.Pos().X()); pos->set_y(pose.Pos().Y()); pos->set_z(pose.Pos().Z());
    auto *q = p->mutable_orientation(); q->set_x(pose.Rot().X()); q->set_y(pose.Rot().Y());
    q->set_z(pose.Rot().Z()); q->set_w(pose.Rot().W());
    auto *t = msg.mutable_twist(); auto *l=t->mutable_linear();
    l->set_x(linear[0]); l->set_y(linear[1]); l->set_z(linear[2]);
    auto *a=t->mutable_angular(); a->set_x(angular[0]); a->set_y(angular[1]); a->set_z(angular[2]);
    auto *stamp=msg.mutable_header()->mutable_stamp();
    stamp->set_sec(stamp_ns / 1'000'000'000LL); stamp->set_nsec(stamp_ns % 1'000'000'000LL);
    gt_publisher_.Publish(msg);
  }

  void PublishBackendState(const gz::sim::UpdateInfo &info, std::int64_t stamp_ns)
  {
    BackendState msg;
    msg.header.stamp.sec = static_cast<std::int32_t>(stamp_ns / 1'000'000'000LL);
    msg.header.stamp.nanosec = static_cast<std::uint32_t>(stamp_ns % 1'000'000'000LL);
    msg.header.frame_id = world_name_; msg.schema_version = BackendState::SCHEMA_VERSION;
    msg.session_id = session_id_; msg.config_hash = config_hash_;
    msg.backend_instance_id = backend_instance_id_; msg.status_sequence = status_sequence_;
    msg.episode_generation = safety_input_.episode_generation;
    msg.reset_epoch = safety_input_.reset_epoch; msg.runtime_generation = safety_input_.runtime_generation;
    msg.physics_iteration = info.iterations;
    msg.required_collision_mask = contact_decision_.coverage_complete ? contact_decision_.observed_mask :
      (collision_bits_.size() == 64 ? ~std::uint64_t{0} : ((std::uint64_t{1} << collision_bits_.size()) - 1));
    msg.observed_collision_mask = contact_decision_.observed_mask;
    msg.coverage_complete = contact_decision_.coverage_complete;
    msg.contact_source_healthy = contact_decision_.healthy;
    msg.contact_active = contact_decision_.contact_active;
    msg.paused = info.paused; msg.actuator_inhibited = !policy_open_ || local_zero_override_ || fault_flags_ != 0;
    msg.local_zero_override = local_zero_override_; msg.fault_flags = fault_flags_;
    if (!local_zero_override_ && pending_applied_receipt_)
    {
      msg.applied_receipt_valid = true;
      msg.applied_final_publisher_instance_id = pending_applied_receipt_->key.publisher_instance_id;
      msg.applied_final_publish_sequence = pending_applied_receipt_->key.publish_sequence;
      msg.applied_physics_iteration = info.iterations;
      msg.applied_sim_stamp.sec = static_cast<std::int32_t>(stamp_ns / 1'000'000'000LL);
      msg.applied_sim_stamp.nanosec = static_cast<std::uint32_t>(stamp_ns % 1'000'000'000LL);
    }
    else
    {
      msg.applied_receipt_valid = false;
      msg.applied_final_publisher_instance_id = 0; msg.applied_final_publish_sequence = 0;
      msg.applied_physics_iteration = 0; msg.applied_sim_stamp.sec = 0; msg.applied_sim_stamp.nanosec = 0;
    }
    state_pub_->publish(msg);
    if (pending_applied_receipt_)
      last_accepted_key_ = pending_applied_receipt_->key;
    pending_applied_receipt_.reset();
  }

  void SetFault(std::uint32_t flag, std::string reason)
  {
    fault_flags_ |= flag; fault_reason_ = std::move(reason); policy_open_ = false;
  }

  gz::sim::Entity world_entity_{gz::sim::kNullEntity};
  gz::sim::Entity model_entity_{gz::sim::kNullEntity};
  gz::sim::World world_{gz::sim::kNullEntity};
  gz::sim::Model model_{gz::sim::kNullEntity};
  gz::sim::Link base_link_{gz::sim::kNullEntity};
  std::string world_name_, model_name_, base_link_name_, session_id_, config_hash_, asset_manifest_hash_;
  std::string probe_collision_name_, fault_reason_;
  std::unique_ptr<ReceiptGate> gate_;
  std::unique_ptr<ContactCoverage> contact_coverage_;
  std::unordered_map<std::string,std::uint64_t> collision_bits_;
  std::unordered_map<gz::sim::Entity,std::uint64_t> sensor_bits_;
  std::shared_ptr<rclcpp::Context> context_;
  rclcpp::Node::SharedPtr node_;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  std::thread executor_thread_;
  rclcpp::Subscription<Receipt>::SharedPtr receipt_sub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr twist_sub_;
  rclcpp::Subscription<SafetyInput>::SharedPtr safety_sub_;
  rclcpp::Publisher<BackendState>::SharedPtr state_pub_;
  gz::transport::Node gt_pub_;
  gz::transport::Node::Publisher gt_publisher_;
  std::mutex callback_mutex_;
  std::deque<std::pair<SafetyInput, std::int64_t>> safety_queue_;
  std::atomic<std::uint32_t> callback_fault_flags_{};
  SafetyInput safety_input_;
  geometry_msgs::msg::Twist captured_twist_;
  std::int64_t captured_twist_received_steady_ns_{};
  std::int64_t safety_receive_steady_ns_{};
  std::uint64_t policy_instance_id_{}, backend_instance_id_{1}, status_sequence_{}, physics_iteration_{};
  std::uint32_t fault_flags_{};
  std::int64_t last_sim_ns_{}, last_sim_advance_steady_ns_{}, selected_steady_ns_{};
  bool configured_{}, policy_open_{}, local_zero_override_{true}, measurement_healthy_{};
  bool contact_capability_verified_{};
  std::optional<ReceiptFacts> selected_receipt_, pending_applied_receipt_;
  std::optional<ReceiptKey> last_accepted_key_;
  ContactDecision contact_decision_;
};
}  // namespace mecanum_sim_backend

GZ_ADD_PLUGIN(mecanum_sim_backend::BackendSystem, gz::sim::System,
              gz::sim::ISystemConfigure, gz::sim::ISystemPreUpdate,
              gz::sim::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(mecanum_sim_backend::BackendSystem,
                    "mecanum_sim_backend::BackendSystem")
