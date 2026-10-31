#include <array>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <deque>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <memory>
#include <map>
#include <mutex>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <thread>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include <openssl/sha.h>
#include <openssl/evp.h>

#include <gz/math/Quaternion.hh>
#include <gz/msgs/odometry.pb.h>
#include <gz/msgs/Utility.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/World.hh>
#include <gz/sim/config.hh>
#include <gz/sim/components/Collision.hh>
#include <gz/sim/components/ContactSensor.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/sim/components/PhysicsEnginePlugin.hh>
#include <gz/sim/components/World.hh>
#include <gz/transport/Node.hh>

#include <ament_index_cpp/get_package_share_directory.hpp>
#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>
#include <mecanum_nav_rl_interfaces/msg/final_issued_command_receipt.hpp>
#include <mecanum_nav_rl_interfaces/msg/local_training_safety_input.hpp>
#include <mecanum_nav_rl_interfaces/msg/simulation_contact_state.hpp>
#include <mecanum_nav_rl_interfaces/srv/local_training_backend_control.hpp>
#include <ros_gz_interfaces/srv/delete_entity.hpp>
#include <ros_gz_interfaces/srv/set_entity_pose.hpp>
#include <ros_gz_interfaces/srv/spawn_entity.hpp>

#include "mecanum_sim_backend/backend_system.hpp"
#include "mecanum_sim_backend/contact_coverage.hpp"
#include "mecanum_sim_backend/receipt_gate.hpp"

namespace mecanum_sim_backend
{
namespace backend_detail
{
using SpawnEntity = ros_gz_interfaces::srv::SpawnEntity;
using SetEntityPose = ros_gz_interfaces::srv::SetEntityPose;
using DeleteEntity = ros_gz_interfaces::srv::DeleteEntity;

enum class ProbeServiceKind { Spawn, Lift, Remove };
enum class RuntimeResourceKind
{
  Context,
  Node,
  ReceiptSubscription,
  TwistSubscription,
  SafetySubscription,
  BackendStatePublisher,
  BackendControlService,
  ProbeSpawnClient,
  ProbePoseClient,
  ProbeDeleteClient,
  Executor,
  ExecutorNodeRegistration,
  ExecutorThread,
  GazeboTransportNode,
  GroundTruthPublisher,
};
constexpr std::array<RuntimeResourceKind, 15> kRuntimeResourceOrder{
  RuntimeResourceKind::Context,
  RuntimeResourceKind::Node,
  RuntimeResourceKind::ReceiptSubscription,
  RuntimeResourceKind::TwistSubscription,
  RuntimeResourceKind::SafetySubscription,
  RuntimeResourceKind::BackendStatePublisher,
  RuntimeResourceKind::BackendControlService,
  RuntimeResourceKind::ProbeSpawnClient,
  RuntimeResourceKind::ProbePoseClient,
  RuntimeResourceKind::ProbeDeleteClient,
  RuntimeResourceKind::Executor,
  RuntimeResourceKind::ExecutorNodeRegistration,
  RuntimeResourceKind::ExecutorThread,
  RuntimeResourceKind::GazeboTransportNode,
  RuntimeResourceKind::GroundTruthPublisher,
};
struct ProbeServiceResult
{
  std::uint64_t start_sequence{};
  ProbeServiceKind kind{};
  bool success{};
};
struct ProbeServiceTransport
{
  std::function<bool()> spawn_ready;
  std::function<bool()> pose_ready;
  std::function<bool()> remove_ready;
  std::function<void(const SpawnEntity::Request &, std::function<void(bool)>)>
      spawn;
  std::function<void(const SetEntityPose::Request &, std::function<void(bool)>)>
      set_pose;
  std::function<void(const DeleteEntity::Request &, std::function<void(bool)>)>
      remove;
};
}  // namespace backend_detail

namespace
{
using Receipt = mecanum_nav_rl_interfaces::msg::FinalIssuedCommandReceipt;
using SafetyInput = mecanum_nav_rl_interfaces::msg::LocalTrainingSafetyInput;
using BackendState = mecanum_nav_rl_interfaces::msg::SimulationContactState;
using BackendControl =
  mecanum_nav_rl_interfaces::srv::LocalTrainingBackendControl;
using ControlRequest = BackendControl::Request;
using ControlResponse = BackendControl::Response;
using SteadyClock = std::chrono::steady_clock;
using backend_detail::DeleteEntity;
using backend_detail::ProbeServiceKind;
using backend_detail::ProbeServiceResult;
using backend_detail::ProbeServiceTransport;
using backend_detail::SetEntityPose;
using backend_detail::SpawnEntity;

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
std::int64_t TimeNs(const builtin_interfaces::msg::Time &stamp)
{
  if (stamp.nanosec >= 1'000'000'000U) return -1;
  return static_cast<std::int64_t>(stamp.sec) * 1'000'000'000LL +
         stamp.nanosec;
}
bool LowerHex64(const std::string &value)
{
  return value.size() == 64 && std::all_of(
      value.begin(), value.end(), [](char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
      });
}
std::vector<std::uint8_t> SerializeControlRequest(
    const ControlRequest &request)
{
  std::vector<std::uint8_t> bytes;
  const auto append_integer = [&bytes](auto value) {
    using Value = decltype(value);
    using Unsigned = std::make_unsigned_t<Value>;
    const auto encoded = static_cast<Unsigned>(value);
    for (std::size_t index = 0; index < sizeof(Value); ++index)
    {
      const auto shift = 8U * (sizeof(Value) - index - 1U);
      bytes.push_back(static_cast<std::uint8_t>(encoded >> shift));
    }
  };
  const auto append_bool = [&bytes](bool value) {
    bytes.push_back(value ? 1U : 0U);
  };
  const auto append_string = [&bytes, &append_integer](const std::string &value) {
    append_integer(static_cast<std::uint64_t>(value.size()));
    bytes.insert(bytes.end(), value.begin(), value.end());
  };
  const auto append_time = [&append_integer](
      const builtin_interfaces::msg::Time &stamp) {
    append_integer(stamp.sec);
    append_integer(stamp.nanosec);
  };

  append_integer(request.schema_version);
  append_integer(request.operation);
  append_integer(request.probe_action);
  append_integer(request.coordinator_ingress_instance_id);
  append_integer(request.request_sequence);
  append_integer(request.expected_binding_revision);
  append_integer(request.expected_backend_instance_id);
  append_string(request.session_id);
  append_string(request.config_hash);
  append_string(request.asset_manifest_sha256);
  append_integer(request.episode_generation);
  append_integer(request.reset_epoch);
  append_integer(request.runtime_generation);
  append_integer(request.lifecycle_sequence);
  append_integer(request.primary_state);
  append_integer(request.barrier_state);
  append_time(request.lifecycle_header_stamp);
  append_string(request.lifecycle_frame_id);
  append_time(request.barrier_stamp);
  append_bool(request.motion_permitted);
  append_integer(request.final_publisher_instance_id);
  append_integer(request.policy_source_instance_id);
  append_integer(request.safe_stop_source_instance_id);
  append_integer(request.next_safe_stop_sequence);
  append_integer(request.pending_step_index);
  append_integer(request.pending_source_sequence);
  append_string(request.pending_transition_id);
  append_time(request.action_barrier_stamp);
  append_time(request.observation0_cutoff);
  append_integer(request.selected_zero_final_publisher_instance_id);
  append_integer(request.selected_zero_final_publish_sequence);
  append_integer(request.adjacent_boundary_final_publisher_instance_id);
  append_integer(request.adjacent_boundary_final_publish_sequence);
  append_integer(request.probe_start_request_sequence);
  return bytes;
}
bool IsZero(const builtin_interfaces::msg::Time &stamp)
{
  return stamp.sec == 0 && stamp.nanosec == 0;
}
bool LifecycleFieldsZero(const ControlRequest &request)
{
  return request.episode_generation == 0 && request.reset_epoch == 0 &&
      request.runtime_generation == 0 && request.lifecycle_sequence == 0 &&
      request.primary_state == ControlRequest::PRIMARY_UNCONFIGURED &&
      request.barrier_state == ControlRequest::BARRIER_INIT &&
      IsZero(request.lifecycle_header_stamp) &&
      request.lifecycle_frame_id.empty() && IsZero(request.barrier_stamp) &&
      !request.motion_permitted;
}
bool SourceFieldsZero(const ControlRequest &request)
{
  return request.final_publisher_instance_id == 0 &&
      request.policy_source_instance_id == 0 &&
      request.safe_stop_source_instance_id == 0 &&
      request.next_safe_stop_sequence == 0;
}
bool PendingStepFieldsZero(const ControlRequest &request)
{
  return request.pending_step_index == 0 &&
      request.pending_source_sequence == 0 &&
      request.pending_transition_id.empty() &&
      IsZero(request.action_barrier_stamp);
}
bool Observation0FieldsZero(const ControlRequest &request)
{
  return IsZero(request.observation0_cutoff) &&
      request.selected_zero_final_publisher_instance_id == 0 &&
      request.selected_zero_final_publish_sequence == 0 &&
      request.adjacent_boundary_final_publisher_instance_id == 0 &&
      request.adjacent_boundary_final_publish_sequence == 0;
}
bool OperationFieldsValid(const ControlRequest &request)
{
  const auto operation = request.operation;
  const bool lifecycle_used =
      operation == ControlRequest::OP_BIND_SESSION ||
      operation == ControlRequest::OP_BIND_RESET_CONTEXT ||
      operation == ControlRequest::OP_CONFIRM_OBSERVATION0 ||
      (operation == ControlRequest::OP_VERIFY_CONTACT_CAPABILITY &&
       request.probe_action == ControlRequest::PROBE_ACTION_START);
  const bool sources_used =
      operation == ControlRequest::OP_BIND_SESSION ||
      operation == ControlRequest::OP_BIND_RESET_CONTEXT;
  const bool pending_used =
      operation == ControlRequest::OP_BIND_PENDING_STEP;
  const bool observation_used =
      operation == ControlRequest::OP_CONFIRM_OBSERVATION0;
  const bool probe_used =
      operation == ControlRequest::OP_VERIFY_CONTACT_CAPABILITY;
  if ((!lifecycle_used && !LifecycleFieldsZero(request)) ||
      (!sources_used && !SourceFieldsZero(request)) ||
      (!pending_used && !PendingStepFieldsZero(request)) ||
      (!observation_used && !Observation0FieldsZero(request)))
    return false;
  if (!probe_used &&
      (request.probe_action != ControlRequest::PROBE_ACTION_NONE ||
       request.probe_start_request_sequence != 0))
    return false;
  if (probe_used &&
      (request.probe_action < ControlRequest::PROBE_ACTION_START ||
       request.probe_action > ControlRequest::PROBE_ACTION_ABORT))
    return false;
  if (probe_used && request.probe_action == ControlRequest::PROBE_ACTION_START &&
      request.probe_start_request_sequence != 0)
    return false;
  if (probe_used && request.probe_action != ControlRequest::PROBE_ACTION_START &&
      request.probe_start_request_sequence == 0)
    return false;
  return true;
}
}  // namespace

class BackendSystem final : public gz::sim::System,
                            public gz::sim::ISystemConfigure,
                            public gz::sim::ISystemPreUpdate,
                            public gz::sim::ISystemPostUpdate
{
public:
  BackendSystem()
  : gate_factory_([](GateBinding binding) {
      return std::make_shared<ReceiptGate>(std::move(binding));
    }),
    contact_coverage_factory_([](std::uint32_t count) {
      return std::make_shared<ContactCoverage>(count);
    }),
    runtime_resource_factory_([](
        backend_detail::RuntimeResourceKind,
        const std::function<void()> &create_real_resource) {
      create_real_resource();
      return std::function<void()>([] {});
    })
  {
  }

  ~BackendSystem() override
  {
    Shutdown();
  }

  void Configure(const gz::sim::Entity &entity,
                 const std::shared_ptr<const sdf::Element> &sdf,
                 gz::sim::EntityComponentManager &ecm,
                 gz::sim::EventManager &) override
  {
    if (!sdf || entity == gz::sim::kNullEntity ||
        gz::sim::entityTypeId(entity, ecm) != gz::sim::components::Model::typeId)
    {
      SetFault(BackendState::FAULT_CONTEXT, "plugin_requires_model_entity_and_sdf");
      return;
    }
    model_entity_ = entity;
    model_ = gz::sim::Model(model_entity_);
    world_entity_ = gz::sim::worldEntity(model_entity_, ecm);
    if (world_entity_ == gz::sim::kNullEntity)
    {
      SetFault(BackendState::FAULT_CONTEXT, "parent_world_missing");
      return;
    }
    world_name_ = sdf->Get<std::string>("world_name", "").first;
    session_id_ = sdf->Get<std::string>("session_id", "").first;
    config_hash_ = sdf->Get<std::string>("config_hash", "").first;
    asset_manifest_hash_ = sdf->Get<std::string>("asset_manifest_sha256", "").first;
    coordinator_ingress_instance_id_ =
        ParseU64(sdf, "coordinator_ingress_instance_id");
    const auto final_instance = ParseU64(sdf, "final_publisher_instance_id");
    const auto safe_instance = ParseU64(sdf, "safe_stop_source_instance_id");
    policy_instance_id_ = ParseU64(sdf, "policy_source_instance_id");
    model_name_ = sdf->Get<std::string>("robot_entity", "mecanum_b2").first;
    base_link_name_ = sdf->Get<std::string>("base_link", "base_link").first;
    world_ = gz::sim::World(world_entity_);
    const auto *world_name_component = ecm.Component<gz::sim::components::Name>(world_entity_);
    const auto *model_name_component = ecm.Component<gz::sim::components::Name>(model_entity_);
    if (!world_name_component || !model_name_component ||
        world_name_component->Data() != world_name_ ||
        model_name_component->Data() != model_name_)
    {
      SetFault(BackendState::FAULT_CONTEXT, "world_or_robot_identity_mismatch");
      return;
    }
    std::vector<std::pair<std::uint64_t, std::uint64_t>> same_name_models;
    ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
      [&](const gz::sim::Entity &candidate,
          const gz::sim::components::Model *,
          const gz::sim::components::Name *name)
      {
        const auto candidate_world = gz::sim::worldEntity(candidate, ecm);
        if (name && name->Data() == model_name_)
        {
          same_name_models.emplace_back(candidate, candidate_world);
        }
        return true;
      });
    if (!IsUniqueWorldModel(model_entity_, world_entity_, same_name_models))
    {
      SetFault(BackendState::FAULT_CONTEXT,
               "robot_model_cardinality_or_world_mismatch");
      return;
    }
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
    binding.barrier_stamp_ns = ParseU64(sdf, "barrier_stamp_ns");
    if (session_id_.empty() || session_id_ == "REQUIRED_RUN_ID" ||
        !LowerHex64(config_hash_) || final_instance == 0 || safe_instance == 0 ||
        policy_instance_id_ == 0 || binding.barrier_stamp_ns == 0 ||
        binding.next_safe_stop_sequence == 0)
    {
      // B2.3 binds source identities through the pinned control service. An
      // absent startup anchor is inhibited state, not a fabricated binding.
    }
    else
    {
      gate_ = gate_factory_(std::move(binding));
      if (!gate_)
        SetFault(BackendState::FAULT_CONTEXT, "receipt_gate_factory_failed");
    }
    if (coordinator_ingress_instance_id_ == 0)
      SetFault(BackendState::FAULT_CONTEXT,
               "trusted_coordinator_ingress_pin_missing");

    std::uint32_t tracked_count = 0;
    auto plugin_sdf = sdf->Clone();
    if (plugin_sdf->HasElement("tracked_collision"))
    {
      auto item = plugin_sdf->GetElement("tracked_collision");
      while (item)
      {
        const auto name_attribute = item->GetAttribute("name");
        const auto sensor_attribute = item->GetAttribute("sensor");
        const auto wheel_attribute = item->GetAttribute("wheel_floor_ignore");
        if (!name_attribute || !sensor_attribute || !wheel_attribute)
        {
          SetFault(BackendState::FAULT_CONTACT_COVERAGE,
                   "collision_registry_binding_incomplete");
          break;
        }
        const auto name = name_attribute->GetAsString();
        const auto sensor_name = sensor_attribute->GetAsString();
        const auto wheel_value = wheel_attribute->GetAsString();
        const auto matches = gz::sim::entitiesFromScopedName(name, ecm);
        const auto sensors = gz::sim::entitiesFromScopedName(sensor_name, ecm);
        if (matches.size() != 1 || sensors.size() != 1 ||
            gz::sim::scopedName(*matches.begin(), ecm, "::", false) != name ||
            gz::sim::scopedName(*sensors.begin(), ecm, "::", false) != sensor_name ||
            ecm.Component<gz::sim::components::Collision>(*matches.begin()) == nullptr ||
            ecm.Component<gz::sim::components::ContactSensor>(*sensors.begin()) == nullptr ||
            collision_bits_.find(name) != collision_bits_.end() ||
            collision_contact_bits_.find(*matches.begin()) !=
                collision_contact_bits_.end() ||
            (wheel_value != "true" && wheel_value != "false"))
        {
          SetFault(BackendState::FAULT_CONTACT_COVERAGE,
                   "collision_registry_resolution_not_exact_unique");
          break;
        }
        const auto sensor_component =
          ecm.Component<gz::sim::components::ContactSensor>(*sensors.begin());
        const auto sensor_sdf = sensor_component ? sensor_component->Data() : nullptr;
        if (!sensor_sdf || !sensor_sdf->HasElement("contact") ||
            sensor_sdf->GetElement("contact")->Get<std::string>(
              "collision", "").first != name.substr(name.rfind("::") + 2))
        {
          SetFault(BackendState::FAULT_CONTACT_COVERAGE,
                   "contact_sensor_collision_binding_mismatch");
          break;
        }
        const auto bit = tracked_count < 64 ? (std::uint64_t{1} << tracked_count) : 0;
        collision_bits_[name] = bit;
        collision_entity_names_[*matches.begin()] = name;
        // Gazebo Sim 8.11 Contact::CreateSensors creates ContactSensorData
        // on the collision entity, not on the ContactSensor entity.
        collision_contact_bits_[*matches.begin()] = bit;
        if (wheel_value == "true") wheel_floor_collisions_.insert(name);
        ++tracked_count;
        item = item->GetNextElement("tracked_collision");
      }
    }
    const std::string floor_collision_name =
      world_name_ + "::ground_plane::link::collision";
    const auto floor_matches =
      gz::sim::entitiesFromScopedName(floor_collision_name, ecm);
    if (floor_matches.size() != 1 ||
        gz::sim::scopedName(*floor_matches.begin(), ecm, "::", false) !=
          floor_collision_name ||
        ecm.Component<gz::sim::components::Collision>(
          *floor_matches.begin()) == nullptr)
    {
      SetFault(BackendState::FAULT_CONTACT_COVERAGE,
               "exact_ground_collision_resolution_failed");
    }
    else
    {
      floor_collision_entity_ = *floor_matches.begin();
    }
    contact_coverage_ = contact_coverage_factory_(tracked_count);
    if (!contact_coverage_)
    {
      SetFault(BackendState::FAULT_CONTACT_COVERAGE,
               "contact_coverage_factory_failed");
      return;
    }
    CapturePhysicsEngineFingerprint(ecm);
    backend_instance_id_ = BootNonce();
    if (tracked_count == 0 || tracked_count > 64 || asset_manifest_hash_.size() != 64)
      SetFault(BackendState::FAULT_CONTACT_COVERAGE, "invalid_asset_contact_manifest");

    try
    {
      if (after_native_resources_created_)
        after_native_resources_created_();
      for (const auto resource : backend_detail::kRuntimeResourceOrder)
      {
        const auto create_real_resource = [this, resource] {
          CreateActualRuntimeResource(resource);
        };
        auto release = runtime_resource_factory_(resource, create_real_resource);
        if (!release)
          throw std::runtime_error("runtime_resource_factory_missing_release");
        runtime_resource_releases_.emplace_back(resource, std::move(release));
        if (after_runtime_resource_created_)
          after_runtime_resource_created_(resource);
      }
      runtime_resources_ready_ =
          runtime_resource_releases_.size() ==
          backend_detail::kRuntimeResourceOrder.size();
    }
    catch (const std::exception &error)
    {
      SetFault(BackendState::FAULT_CONTEXT, std::string("ros_transport_init_failed:") + error.what());
      // A failed Configure is terminal for this plugin instance. Roll back any
      // resources created before the failure and leave every hook inhibited.
      Shutdown();
    }
    last_sim_ns_ = 0;
    last_sim_advance_steady_ns_ = NowSteadyNs();
    // Structural/plugin readiness is separate from actuator admission. A
    // missing trusted B2.3 binding keeps PreUpdate inhibited but still allows
    // the backend to publish its faulted, identity-bound status heartbeat.
    configured_ = runtime_resources_ready_ && base_link_.Valid(ecm);
  }

  void PreUpdate(const gz::sim::UpdateInfo &info,
                 gz::sim::EntityComponentManager &ecm) override
  {
    if (shutdown_started_) return;
    const auto steady_now_ns = NowSteadyNs();
    ProcessBackendControlRequests(
        ecm, TimeNs(info), info.iterations, steady_now_ns, info.paused);
    ProcessProbeServiceResults();
    AdvanceContactProbe(info, ecm, steady_now_ns);
    ProcessCallbackInputs();
    const auto pending_faults = callback_fault_flags_.exchange(0);
    if (pending_faults != 0) SetFault(pending_faults, "ros_callback_queue_or_context_fault");
    if (!configured_ || !gate_ || !contact_coverage_ ||
        base_link_.Entity() == gz::sim::kNullEntity ||
        !base_link_.Valid(ecm) || info.paused)
    {
      policy_open_ = false;
      local_zero_override_ = true;
      if (base_link_.Valid(ecm)) ApplyEmergencyZero(ecm);
      return;
    }
    const auto now_steady = NowSteadyNs();
    const auto now_sim = TimeNs(info);
    if (contact_capability_verified_)
    {
      const auto *engine = ecm.Component<gz::sim::components::PhysicsEnginePlugin>(
          world_entity_);
      if (!engine || engine->Data() != proof_physics_engine_plugin_)
        SetFault(BackendState::FAULT_CONTEXT,
                 "observed_physics_engine_identity_changed");
    }
    if (now_sim < last_sim_ns_)
    {
      probe_machine_.Invalidate();
      {
        std::lock_guard<std::mutex> lock(callback_mutex_);
        gate_->Invalidate("simulation_clock_rollback");
      }
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
      if (gate_->WatchdogExpired(now_steady))
      {
        fault_flags_ |= BackendState::FAULT_COMMAND_STALE;
        gate_->Invalidate("actuator_watchdog_expired");
        policy_open_ = false;
      }
    }
    if (decision.disposition == GateDisposition::Faulted)
      SetFault(BackendState::FAULT_COMMAND_SEQUENCE, decision.reason);
    if (decision.disposition == GateDisposition::Applied ||
        decision.disposition == GateDisposition::Anchored)
    {
      selected_receipt_ = decision.accepted;
      selected_steady_ns_ = now_steady;
      if (decision.accepted)
      {
        accepted_receipt_history_.push_back(*decision.accepted);
        if (accepted_receipt_history_.size() > 128)
          accepted_receipt_history_.erase(accepted_receipt_history_.begin());
      }
    }

    bool gate_faulted = false;
    {
      std::lock_guard<std::mutex> lock(callback_mutex_);
      gate_faulted = gate_->Faulted();
    }
    if (gate_faulted)
    {
      fault_flags_ |= BackendState::FAULT_COMMAND_STALE;
      policy_open_ = false;
      local_zero_override_ = true;
      ApplyEmergencyZero(ecm);
      return;
    }
    if (policy_open_ && (safety_receive_steady_ns_ == 0 || now_steady < safety_receive_steady_ns_ ||
        now_steady - safety_receive_steady_ns_ > 250'000'000))
    {
      fault_flags_ |= BackendState::FAULT_COMMAND_STALE;
      {
        std::lock_guard<std::mutex> lock(callback_mutex_);
        gate_->Invalidate("safety_input_steady_age_exceeded");
      }
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
      if (actuator_apply_)
        actuator_apply_(ecm, *command);
      else
      {
        base_link_.SetLinearVelocity(
            ecm, {command->linear[0], command->linear[1], command->linear[2]});
        base_link_.SetAngularVelocity(
            ecm, {command->angular[0], command->angular[1], command->angular[2]});
      }
      pending_applied_receipt_ = decision.accepted;
      local_zero_override_ = false;
    }
  }

  void PostUpdate(const gz::sim::UpdateInfo &info,
                  const gz::sim::EntityComponentManager &ecm) override
  {
    if (shutdown_started_ || !configured_ || !contact_coverage_ ||
        (!state_pub_ && !backend_state_sink_) ||
        base_link_.Entity() == gz::sim::kNullEntity || !base_link_.Valid(ecm))
    {
      return;
    }
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
    ObserveContactProbe(info, ecm, sim_ns);
    contact_history_.push_back({
        info.iterations, sim_ns, contact_decision_.coverage_complete,
        contact_decision_.healthy, contact_decision_.contact_active});
    if (contact_history_.size() > 128) contact_history_.erase(contact_history_.begin());
    if (!contact_decision_.healthy && !info.paused &&
        contact_decision_.reason != "contact_capability_unverified")
    {
      fault_flags_ |= contact_decision_.fault_flags ? contact_decision_.fault_flags : BackendState::FAULT_CONTACT_COVERAGE;
      if (contact_capability_verified_)
      {
        contact_capability_verified_ = false;
        ++capability_revision_;
      }
      probe_machine_.Invalidate();
      probe_running_ = false;
    }
    if (state_pub_ || backend_state_sink_)
      PublishBackendState(info, sim_ns);
  }

private:
  friend class BackendSystemTestPeer;

  std::atomic_bool shutdown_started_{};

  void Shutdown()
  {
    bool expected = false;
    if (!shutdown_started_.compare_exchange_strong(expected, true)) return;
    configured_ = false;
    runtime_resources_ready_ = false;
    policy_open_ = false;
    local_zero_override_ = true;
    if (executor_) executor_->cancel();
    if (executor_thread_.joinable()) executor_thread_.join();
    control_service_.reset();
    probe_spawn_client_.reset();
    probe_pose_client_.reset();
    probe_delete_client_.reset();
    receipt_sub_.reset();
    twist_sub_.reset();
    safety_sub_.reset();
    state_pub_.reset();
    gt_publisher_.reset();
    gt_pub_.reset();
    executor_.reset();
    node_.reset();
    if (context_ && context_->is_valid()) context_->shutdown("backend shutdown");
    context_.reset();
    for (auto resource = runtime_resource_releases_.rbegin();
         resource != runtime_resource_releases_.rend(); ++resource)
    {
      try
      {
        resource->second();
      }
      catch (...)
      {
        // Cleanup remains best-effort and fail-closed; continue releasing
        // every owned resource even if one injected/native release fails.
      }
    }
    runtime_resource_releases_.clear();
    gate_.reset();
    contact_coverage_.reset();
  }

  struct PendingControl
  {
    ControlRequest request;
    std::vector<std::uint8_t> request_bytes;
  };
  struct CachedControl
  {
    std::vector<std::uint8_t> request_bytes;
    ControlResponse response;
  };

  void EnqueueProbeServiceResult(
      std::uint64_t start_sequence, ProbeServiceKind kind, bool success)
  {
    if (shutdown_started_.load()) return;
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (probe_service_results_.size() >= 8)
    {
      callback_fault_flags_.fetch_or(BackendState::FAULT_QUEUE);
      return;
    }
    probe_service_results_.push_back({start_sequence, kind, success});
  }

  void ProcessProbeServiceResults()
  {
    std::deque<ProbeServiceResult> results;
    {
      std::lock_guard<std::mutex> lock(callback_mutex_);
      results.swap(probe_service_results_);
    }
    for (const auto &result : results)
    {
      if (result.start_sequence != probe_machine_.StartSequence()) continue;
      if (result.kind == ProbeServiceKind::Spawn)
        probe_machine_.SpawnCompleted(result.success);
      else if (result.kind == ProbeServiceKind::Lift)
        probe_machine_.LiftCompleted(result.success);
      else if (result.kind == ProbeServiceKind::Remove)
        probe_machine_.RemoveCompleted(result.success);
      if (!result.success)
      {
        probe_running_ = false;
        contact_capability_verified_ = false;
        probe_reason_ = "probe_world_service_failed";
      }
    }
  }

  void RequestProbeSpawn()
  {
    if (!probe_transport_.spawn_ready || !probe_transport_.spawn ||
        !probe_transport_.spawn_ready() ||
        !std::filesystem::is_regular_file(probe_model_sdf_path_))
    {
      probe_machine_.SpawnCompleted(false);
      return;
    }
    auto request = std::make_shared<SpawnEntity::Request>();
    request->entity_factory.name = "b2_capability_probe";
    request->entity_factory.allow_renaming = false;
    request->entity_factory.sdf_filename = probe_model_sdf_path_;
    request->entity_factory.relative_to = "world";
    request->entity_factory.pose.position.x = -2.0;
    request->entity_factory.pose.position.y = 0.0;
    request->entity_factory.pose.position.z = 0.07;
    request->entity_factory.pose.orientation.w = 1.0;
    const auto start_sequence = probe_machine_.StartSequence();
    probe_transport_.spawn(*request, [this, start_sequence](bool success) {
      EnqueueProbeServiceResult(start_sequence, ProbeServiceKind::Spawn, success);
    });
    probe_spawn_sent_ = true;
  }

  bool IsInBoundWorld(
      gz::sim::Entity entity,
      const gz::sim::EntityComponentManager &ecm) const
  {
    std::unordered_set<gz::sim::Entity> visited;
    while (entity != gz::sim::kNullEntity && visited.insert(entity).second)
    {
      if (ecm.Component<gz::sim::components::World>(entity))
      {
        const auto *name = ecm.Component<gz::sim::components::Name>(entity);
        return name && name->Data() == world_name_;
      }
      const auto *parent = ecm.Component<gz::sim::components::ParentEntity>(entity);
      if (!parent) return false;
      entity = parent->Data();
    }
    return false;
  }

  std::vector<gz::sim::Entity> FindProbeModels(
      const gz::sim::EntityComponentManager &ecm) const
  {
    std::vector<gz::sim::Entity> matches;
    ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
        [&](const gz::sim::Entity &entity,
            const gz::sim::components::Model *,
            const gz::sim::components::Name *name) {
          if (name && name->Data() == "b2_capability_probe" &&
              IsInBoundWorld(entity, ecm))
            matches.push_back(entity);
          return true;
        });
    return matches;
  }

  bool ResolveProbeFixture(gz::sim::EntityComponentManager &ecm)
  {
    const auto models = FindProbeModels(ecm);
    if (models.empty()) return false;
    if (models.size() != 1 ||
        gz::sim::scopedName(*models.begin(), ecm, "::", false) !=
            world_name_ + "::b2_capability_probe" ||
        gz::sim::entityTypeId(*models.begin(), ecm) !=
            gz::sim::components::Model::typeId)
    {
      probe_machine_.Invalidate();
      return false;
    }
    std::vector<gz::sim::Entity> collisions;
    ecm.Each<gz::sim::components::Name>(
        [&](const gz::sim::Entity &entity,
            const gz::sim::components::Name *name) {
          if (name && name->Data() == "collision" &&
              ecm.Component<gz::sim::components::Collision>(entity) &&
              IsInBoundWorld(entity, ecm) &&
              gz::sim::scopedName(entity, ecm, "::", false) ==
                world_name_ + "::b2_capability_probe::link::collision")
            collisions.push_back(entity);
          return true;
        });
    std::vector<gz::sim::Entity> sensors;
    ecm.Each<gz::sim::components::Name>(
        [&](const gz::sim::Entity &entity,
            const gz::sim::components::Name *name) {
          if (name && name->Data() == "contact_sensor" &&
              ecm.Component<gz::sim::components::ContactSensor>(entity) &&
              IsInBoundWorld(entity, ecm) &&
              gz::sim::scopedName(entity, ecm, "::", false) ==
                world_name_ + "::b2_capability_probe::link::contact_sensor")
            sensors.push_back(entity);
          return true;
        });
    if (collisions.size() != 1 ||
        sensors.size() != 1)
    {
      probe_machine_.Invalidate();
      return false;
    }
    const auto *sensor = ecm.Component<gz::sim::components::ContactSensor>(
        *sensors.begin());
    const auto sensor_sdf = sensor ? sensor->Data() : nullptr;
    const auto *collision_parent = ecm.Component<gz::sim::components::ParentEntity>(
        *collisions.begin());
    const auto *sensor_parent = ecm.Component<gz::sim::components::ParentEntity>(
        *sensors.begin());
    const auto link_entity = collision_parent ? collision_parent->Data() :
        gz::sim::kNullEntity;
    const auto *link_component =
        ecm.Component<gz::sim::components::Link>(link_entity);
    const auto *link_parent =
        ecm.Component<gz::sim::components::ParentEntity>(link_entity);
    if (!sensor_sdf || !sensor_sdf->HasElement("contact") ||
        sensor_sdf->GetElement("contact")->Get<std::string>(
            "collision", "").first != "collision" ||
        !collision_parent || !sensor_parent ||
        sensor_parent->Data() != link_entity || !link_component ||
        !link_parent || link_parent->Data() != *models.begin())
    {
      probe_machine_.Invalidate();
      return false;
    }
    probe_sensor_entity_ = *sensors.begin();
    return probe_machine_.BindFixture(
        *models.begin(), *collisions.begin(), floor_collision_entity_);
  }

  void RequestProbeLift()
  {
    if (!probe_transport_.pose_ready || !probe_transport_.set_pose ||
        !probe_transport_.pose_ready())
    {
      probe_machine_.LiftRequested();
      probe_machine_.LiftCompleted(false);
      return;
    }
    if (!probe_machine_.LiftRequested()) return;
    auto request = std::make_shared<SetEntityPose::Request>();
    request->entity.id = probe_machine_.ModelEntity();
    request->entity.name = "b2_capability_probe";
    request->entity.type = ros_gz_interfaces::msg::Entity::MODEL;
    request->pose.position.x = -2.0;
    request->pose.position.y = 0.0;
    request->pose.position.z = 0.20;
    request->pose.orientation.w = 1.0;
    const auto start_sequence = probe_machine_.StartSequence();
    probe_transport_.set_pose(*request, [this, start_sequence](bool success) {
      EnqueueProbeServiceResult(start_sequence, ProbeServiceKind::Lift, success);
    });
    probe_lift_sent_ = true;
  }

  void RequestProbeRemoval()
  {
    if (!probe_transport_.remove_ready || !probe_transport_.remove ||
        !probe_transport_.remove_ready()) return;
    if (!probe_machine_.RemoveRequested()) return;
    auto request = std::make_shared<DeleteEntity::Request>();
    request->entity.id = probe_machine_.ModelEntity();
    request->entity.name = "b2_capability_probe";
    request->entity.type = ros_gz_interfaces::msg::Entity::MODEL;
    const auto start_sequence = probe_machine_.StartSequence();
    probe_transport_.remove(*request, [this, start_sequence](bool success) {
      EnqueueProbeServiceResult(start_sequence, ProbeServiceKind::Remove, success);
    });
    probe_remove_sent_ = true;
  }

  static std::string Sha256(const std::string &input)
  {
    unsigned char digest[SHA256_DIGEST_LENGTH]{};
    SHA256(reinterpret_cast<const unsigned char *>(input.data()),
           input.size(), digest);
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (const auto value : digest) out << std::setw(2) << unsigned(value);
    return out.str();
  }

  void CapturePhysicsEngineFingerprint(
      const gz::sim::EntityComponentManager &ecm)
  {
    const auto *engine = ecm.Component<gz::sim::components::PhysicsEnginePlugin>(
        world_entity_);
    if (!engine || engine->Data().empty()) return;
    const std::filesystem::path library(engine->Data());
    if (!library.is_absolute() || !std::filesystem::is_regular_file(library))
      return;
    std::ifstream input(library, std::ios::binary);
    if (!input) return;
    std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> context(
        EVP_MD_CTX_new(), EVP_MD_CTX_free);
    if (!context || EVP_DigestInit_ex(context.get(), EVP_sha256(), nullptr) != 1)
      return;
    std::array<char, 64 * 1024> block{};
    while (input)
    {
      input.read(block.data(), static_cast<std::streamsize>(block.size()));
      const auto count = input.gcount();
      if (count > 0 && EVP_DigestUpdate(
            context.get(), block.data(), static_cast<std::size_t>(count)) != 1)
        return;
    }
    if (!input.eof()) return;
    std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
    unsigned int digest_size = 0;
    if (EVP_DigestFinal_ex(
          context.get(), digest.data(), &digest_size) != 1 ||
        digest_size != SHA256_DIGEST_LENGTH)
      return;
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (unsigned int index = 0; index < digest_size; ++index)
      out << std::setw(2) << unsigned(digest[index]);
    observed_engine_plugin_path_ = library.string();
    proof_physics_engine_fingerprint_sha256_ = out.str();
  }

  void RecordVerifiedProbeProof(
      const gz::sim::EntityComponentManager &ecm,
      std::int64_t sim_stamp_ns)
  {
    const auto *engine = ecm.Component<gz::sim::components::PhysicsEnginePlugin>(
        world_entity_);
    if (!engine || engine->Data().empty() ||
        probe_machine_.ModelEntity() == 0 || probe_machine_.CollisionEntity() == 0)
    {
      probe_machine_.Invalidate();
      contact_capability_verified_ = false;
      probe_reason_ = "observed_physics_engine_or_probe_identity_missing";
      return;
    }
    if (engine->Data() != observed_engine_plugin_path_ ||
        proof_physics_engine_fingerprint_sha256_.size() != 64)
    {
      probe_machine_.Invalidate();
      contact_capability_verified_ = false;
      probe_reason_ = "observed_physics_engine_binary_fingerprint_unavailable";
      return;
    }
    std::vector<std::string> names;
    names.reserve(collision_bits_.size());
    for (const auto &[name, bit] : collision_bits_)
    {
      (void)bit;
      names.push_back(name);
    }
    std::sort(names.begin(), names.end());
    std::ostringstream registry;
    for (const auto &name : names)
      registry << name << '|'
               << (wheel_floor_collisions_.find(name) !=
                       wheel_floor_collisions_.end() ? "wheel" : "solid")
               << '\n';
    proof_collision_registry_sha256_ = Sha256(registry.str());
    proof_physics_engine_plugin_ = engine->Data();
    proof_gz_sim_version_ = GZ_SIM_VERSION_FULL;
    proof_world_name_ = world_name_;
    proof_probe_model_name_ = world_name_ + "::b2_capability_probe";
    proof_probe_collision_name_ = proof_probe_model_name_ + "::link::collision";
    proof_floor_collision_name_ = world_name_ + "::ground_plane::link::collision";
    proof_contact_first_iteration_ = probe_machine_.FirstContactIteration();
    proof_contact_last_iteration_ = probe_machine_.LastContactIteration();
    proof_contact_first_stamp_ns_ = probe_machine_.FirstContactStampNs();
    proof_contact_last_stamp_ns_ = probe_machine_.LastContactStampNs();
    proof_empty_first_iteration_ = probe_machine_.FirstEmptyIteration();
    proof_empty_last_iteration_ = probe_machine_.LastEmptyIteration();
    proof_empty_first_stamp_ns_ = probe_machine_.FirstEmptyStampNs();
    proof_empty_last_stamp_ns_ = probe_machine_.LastEmptyStampNs();
    proof_stamp_ns_ = sim_stamp_ns;
    proof_backend_instance_id_ = backend_instance_id_;
    proof_session_id_ = session_id_;
    proof_config_hash_ = config_hash_;
    proof_asset_manifest_hash_ = asset_manifest_hash_;
    contact_capability_verified_ = true;
    ++capability_revision_;
    probe_reason_.clear();
  }

  void PopulateProbeResponse(ControlResponse &response) const
  {
    response.contact_capability_state = contact_capability_verified_ ?
        ControlResponse::CAPABILITY_VERIFIED :
        (probe_machine_.Running() ? ControlResponse::CAPABILITY_RUNNING :
         (probe_machine_.Phase() == ProbePhase::Failed ||
          probe_machine_.Phase() == ProbePhase::Cancelled ?
            ControlResponse::CAPABILITY_FAILED : ControlResponse::CAPABILITY_UNKNOWN));
    response.capability_revision = capability_revision_;
    response.proof_backend_instance_id = contact_capability_verified_ ?
        proof_backend_instance_id_ : 0;
    if (contact_capability_verified_)
    {
      response.proof_session_id = proof_session_id_;
      response.proof_config_hash = proof_config_hash_;
      response.proof_asset_manifest_sha256 = proof_asset_manifest_hash_;
      response.proof_collision_registry_sha256 = proof_collision_registry_sha256_;
      response.proof_world_name = proof_world_name_;
      response.proof_physics_engine_plugin = proof_physics_engine_plugin_;
      response.proof_gz_sim_version = proof_gz_sim_version_;
      response.proof_physics_engine_fingerprint_sha256 =
          proof_physics_engine_fingerprint_sha256_;
      response.probe_model_scoped_name = proof_probe_model_name_;
      response.probe_model_entity_id = probe_machine_.ModelEntity();
      response.probe_collision_scoped_name = proof_probe_collision_name_;
      response.probe_collision_entity_id = probe_machine_.CollisionEntity();
      response.floor_collision_scoped_name = proof_floor_collision_name_;
      response.floor_collision_entity_id = probe_machine_.FloorEntity();
    }
    response.contact_sample_count = probe_machine_.ContactSampleCount();
    response.contact_first_iteration = probe_machine_.FirstContactIteration();
    response.contact_last_iteration = probe_machine_.LastContactIteration();
    response.covered_empty_sample_count = probe_machine_.EmptySampleCount();
    response.empty_first_iteration = probe_machine_.FirstEmptyIteration();
    response.empty_last_iteration = probe_machine_.LastEmptyIteration();
    const auto set_time = [](std::int64_t ns, builtin_interfaces::msg::Time &stamp) {
      if (ns < 0) return;
      stamp.sec = static_cast<std::int32_t>(ns / 1'000'000'000LL);
      stamp.nanosec = static_cast<std::uint32_t>(ns % 1'000'000'000LL);
    };
    set_time(probe_machine_.FirstContactStampNs(), response.contact_first_stamp);
    set_time(probe_machine_.LastContactStampNs(), response.contact_last_stamp);
    set_time(probe_machine_.FirstEmptyStampNs(), response.empty_first_stamp);
    set_time(probe_machine_.LastEmptyStampNs(), response.empty_last_stamp);
  }

  void AdvanceContactProbe(
      const gz::sim::UpdateInfo &info,
      gz::sim::EntityComponentManager &ecm,
      std::int64_t steady_now_ns)
  {
    if (probe_machine_.Running() && probe_machine_.Expire(steady_now_ns))
    {
      probe_reason_ = "probe_deadline_cleanup_reserve_started";
      probe_running_ = false;
    }
    switch (probe_machine_.Phase())
    {
      case ProbePhase::AwaitSpawn:
        if (!probe_spawn_sent_) RequestProbeSpawn();
        break;
      case ProbePhase::AwaitFixture:
        if (!probe_machine_.NeedsCleanup()) ResolveProbeFixture(ecm);
        break;
      case ProbePhase::AwaitLift:
        if (!probe_lift_sent_) RequestProbeLift();
        break;
      case ProbePhase::AwaitRemove:
      case ProbePhase::Failed:
      case ProbePhase::Cancelled:
        if (probe_machine_.NeedsCleanup() && !probe_remove_sent_ &&
            steady_now_ns < probe_machine_.DeadlineNs())
          RequestProbeRemoval();
        break;
      case ProbePhase::AwaitRemoval:
      {
        const auto remaining = FindProbeModels(ecm);
        if (remaining.empty())
        {
          const bool verified = probe_machine_.ObserveRemoval(true);
          probe_running_ = false;
          if (verified)
            RecordVerifiedProbeProof(ecm, TimeNs(info));
          else
            probe_reason_ = "probe_finished_without_complete_verified_proof";
          probe_remove_sent_ = false;
          probe_spawn_sent_ = false;
          probe_lift_sent_ = false;
        }
        break;
      }
      default:
        break;
    }
    if (steady_now_ns >= probe_machine_.DeadlineNs() &&
        probe_machine_.NeedsCleanup())
    {
      probe_running_ = false;
      if (probe_machine_.ModelEntity() != 0)
        probe_reason_ = "probe_cleanup_deadline_expired_fixture_residue_possible";
    }
    if (probe_machine_.Phase() == ProbePhase::Failed ||
        probe_machine_.Phase() == ProbePhase::Cancelled)
      probe_running_ = false;
  }

  void ObserveContactProbe(
      const gz::sim::UpdateInfo &info,
      const gz::sim::EntityComponentManager &ecm,
      std::int64_t sim_stamp_ns)
  {
    const auto phase = probe_machine_.Phase();
    if (phase != ProbePhase::AwaitContact &&
        phase != ProbePhase::AwaitSeparation &&
        phase != ProbePhase::AwaitEmpty)
      return;
    const auto collision_entity = probe_machine_.CollisionEntity();
    const auto *collision = ecm.Component<gz::sim::components::Collision>(
        collision_entity);
    const auto *component = collision ?
        ecm.Component<gz::sim::components::ContactSensorData>(collision_entity) :
        nullptr;
    ProbeObservation observation;
    observation.iteration = info.iterations;
    observation.sim_stamp_ns = sim_stamp_ns;
    observation.component_present = component != nullptr;
    observation.coverage_complete = component != nullptr;
    observation.paused = info.paused;
    if (component)
    {
      const auto &contacts = component->Data();
      for (int index = 0; index < contacts.contact_size(); ++index)
      {
        const auto &contact = contacts.contact(index);
        const auto first = static_cast<gz::sim::Entity>(contact.collision1().id());
        const auto second = static_cast<gz::sim::Entity>(contact.collision2().id());
        const bool fixture_first = first == probe_machine_.CollisionEntity();
        const bool fixture_second = second == probe_machine_.CollisionEntity();
        if (!fixture_first && !fixture_second) continue;
        const auto other = fixture_first ? second : first;
        if (other == probe_machine_.FloorEntity())
        {
          observation.exact_fixture_floor_pair = true;
          const bool this_pair_valid = contact.normal_size() > 0 &&
              contact.normal_size() == contact.depth_size();
          if (this_pair_valid)
          {
            bool valid = true;
            for (int normal_index = 0;
                 normal_index < contact.normal_size(); ++normal_index)
            {
              const auto &normal = contact.normal(normal_index);
              const auto depth = contact.depth(normal_index);
              const double norm = std::sqrt(normal.x()*normal.x() +
                  normal.y()*normal.y() + normal.z()*normal.z());
              if (!std::isfinite(normal.x()) || !std::isfinite(normal.y()) ||
                  !std::isfinite(normal.z()) || !std::isfinite(depth) ||
                  norm <= 0.0 || depth < 0.0)
                valid = false;
            }
            observation.normal_depth_valid = observation.normal_depth_valid || valid;
            if (!valid) observation.coverage_complete = false;
          }
          else
          {
            observation.normal_depth_valid = false;
            observation.coverage_complete = false;
          }
        }
        else if (collision_entity_names_.find(other) != collision_entity_names_.end())
          observation.exact_fixture_robot_pair = true;
        else
          observation.coverage_complete = false;
      }
      if (!observation.exact_fixture_floor_pair)
        observation.normal_depth_valid = true;
    }
    const auto *probe_pose = ecm.Component<gz::sim::components::WorldPose>(
        probe_machine_.ModelEntity());
    observation.fixture_measured_separated = probe_pose &&
        Finite(probe_pose->Data()) && probe_pose->Data().Pos().Z() > 0.07;
    if (!probe_machine_.Observe(observation))
    {
      probe_running_ = false;
      contact_capability_verified_ = false;
      probe_reason_ = "probe_contact_coverage_or_identity_invalid";
    }
  }

  ControlResponse NewControlResponse(std::uint64_t request_sequence) const
  {
    ControlResponse response;
    response.schema_version = ControlResponse::RESPONSE_SCHEMA_VERSION;
    response.result = ControlResponse::RESULT_REJECTED;
    response.reason_code = ControlResponse::REASON_NONE;
    response.request_sequence = request_sequence;
    response.backend_instance_id = backend_instance_id_;
    response.binding_revision = 0;
    response.applied_binding_revision = 0;
    response.applied_physics_iteration = 0;
    response.applied_sim_stamp.sec = 0;
    response.applied_sim_stamp.nanosec = 0;
    response.contact_capability_state = ControlResponse::CAPABILITY_UNKNOWN;
    response.capability_revision = 0;
    response.proof_backend_instance_id = 0;
    response.proof_session_id.clear();
    response.proof_config_hash.clear();
    response.proof_asset_manifest_sha256.clear();
    response.proof_collision_registry_sha256.clear();
    response.proof_world_name.clear();
    response.proof_physics_engine_plugin.clear();
    response.proof_gz_sim_version.clear();
    response.proof_physics_engine_fingerprint_sha256.clear();
    response.probe_model_scoped_name.clear();
    response.probe_model_entity_id = 0;
    response.probe_collision_scoped_name.clear();
    response.probe_collision_entity_id = 0;
    response.floor_collision_scoped_name.clear();
    response.floor_collision_entity_id = 0;
    response.contact_sample_count = 0;
    response.contact_first_iteration = 0;
    response.contact_last_iteration = 0;
    response.contact_first_stamp.sec = 0;
    response.contact_first_stamp.nanosec = 0;
    response.contact_last_stamp.sec = 0;
    response.contact_last_stamp.nanosec = 0;
    response.covered_empty_sample_count = 0;
    response.empty_first_iteration = 0;
    response.empty_last_iteration = 0;
    response.empty_first_stamp.sec = 0;
    response.empty_first_stamp.nanosec = 0;
    response.empty_last_stamp.sec = 0;
    response.empty_last_stamp.nanosec = 0;
    return response;
  }

  void CacheControlResponse(
      std::uint64_t sequence, std::vector<std::uint8_t> request_bytes,
      ControlResponse response)
  {
    control_cache_[sequence] = {std::move(request_bytes), std::move(response)};
    while (control_cache_.size() > 128) control_cache_.erase(control_cache_.begin());
  }

  void CreateActualRuntimeResource(backend_detail::RuntimeResourceKind resource)
  {
    switch (resource)
    {
      case backend_detail::RuntimeResourceKind::Context:
        context_ = std::make_shared<rclcpp::Context>();
        context_->init(0, nullptr);
        if (!context_->is_valid())
          throw std::runtime_error("runtime_context_invalid");
        return;
      case backend_detail::RuntimeResourceKind::Node:
      {
        rclcpp::NodeOptions options;
        options.context(context_);
        node_ = std::make_shared<rclcpp::Node>("mecanum_sim_backend", options);
        if (!node_) throw std::runtime_error("runtime_node_missing");
        return;
      }
      case backend_detail::RuntimeResourceKind::ReceiptSubscription:
      {
        const auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().transient_local();
        receipt_sub_ = node_->create_subscription<Receipt>(
            "/mecanum/final_issued_command", qos,
            [this](Receipt::ConstSharedPtr msg) { OnReceipt(*msg); });
        if (!receipt_sub_) throw std::runtime_error("receipt_subscription_missing");
        return;
      }
      case backend_detail::RuntimeResourceKind::TwistSubscription:
      {
        const auto qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable().durability_volatile();
        twist_sub_ = node_->create_subscription<geometry_msgs::msg::Twist>(
            "/cmd_vel", qos,
            [this](geometry_msgs::msg::Twist::ConstSharedPtr msg) {
              if (shutdown_started_.load()) return;
              std::lock_guard<std::mutex> lock(callback_mutex_);
              if (shutdown_started_.load()) return;
              captured_twist_ = *msg;
              captured_twist_received_steady_ns_ = NowSteadyNs();
            });
        if (!twist_sub_) throw std::runtime_error("twist_subscription_missing");
        return;
      }
      case backend_detail::RuntimeResourceKind::SafetySubscription:
      {
        const auto qos = rclcpp::QoS(rclcpp::KeepLast(10)).reliable().durability_volatile();
        safety_sub_ = node_->create_subscription<SafetyInput>(
            "/mecanum/local_training/safety_input", qos,
            [this](SafetyInput::ConstSharedPtr msg) { OnSafetyInput(*msg); });
        if (!safety_sub_) throw std::runtime_error("safety_subscription_missing");
        return;
      }
      case backend_detail::RuntimeResourceKind::BackendStatePublisher:
      {
        const auto qos = rclcpp::QoS(rclcpp::KeepLast(50)).reliable().durability_volatile();
        state_pub_ = node_->create_publisher<BackendState>(
            "/mecanum/local_training/backend_state", qos);
        if (!state_pub_) throw std::runtime_error("backend_state_publisher_missing");
        return;
      }
      case backend_detail::RuntimeResourceKind::BackendControlService:
        control_service_ = node_->create_service<BackendControl>(
            "/mecanum/local_training/backend_control",
            [this](const std::shared_ptr<ControlRequest> request,
                   std::shared_ptr<ControlResponse> response) {
              OnBackendControl(*request, *response);
            });
        if (!control_service_) throw std::runtime_error("control_service_missing");
        return;
      case backend_detail::RuntimeResourceKind::ProbeSpawnClient:
        probe_spawn_client_ = node_->create_client<SpawnEntity>(
            "/world/" + world_name_ + "/create");
        if (!probe_spawn_client_) throw std::runtime_error("probe_spawn_client_missing");
        return;
      case backend_detail::RuntimeResourceKind::ProbePoseClient:
        probe_pose_client_ = node_->create_client<SetEntityPose>(
            "/world/" + world_name_ + "/set_pose");
        if (!probe_pose_client_) throw std::runtime_error("probe_pose_client_missing");
        return;
      case backend_detail::RuntimeResourceKind::ProbeDeleteClient:
        probe_delete_client_ = node_->create_client<DeleteEntity>(
            "/world/" + world_name_ + "/remove");
        if (!probe_delete_client_) throw std::runtime_error("probe_remove_client_missing");
        probe_transport_.spawn_ready = [this] {
          return probe_spawn_client_ && probe_spawn_client_->service_is_ready();
        };
        probe_transport_.pose_ready = [this] {
          return probe_pose_client_ && probe_pose_client_->service_is_ready();
        };
        probe_transport_.remove_ready = [this] {
          return probe_delete_client_ && probe_delete_client_->service_is_ready();
        };
        probe_transport_.spawn = [this](
            const SpawnEntity::Request &request,
            std::function<void(bool)> completion) {
          auto req = std::make_shared<SpawnEntity::Request>(request);
          probe_spawn_client_->async_send_request(req,
              [completion = std::move(completion)](
                  rclcpp::Client<SpawnEntity>::SharedFuture future) {
                bool success = false;
                try { success = future.get() && future.get()->success; }
                catch (const std::exception &) { success = false; }
                completion(success);
              });
        };
        probe_transport_.set_pose = [this](
            const SetEntityPose::Request &request,
            std::function<void(bool)> completion) {
          auto req = std::make_shared<SetEntityPose::Request>(request);
          probe_pose_client_->async_send_request(req,
              [completion = std::move(completion)](
                  rclcpp::Client<SetEntityPose>::SharedFuture future) {
                bool success = false;
                try { success = future.get() && future.get()->success; }
                catch (const std::exception &) { success = false; }
                completion(success);
              });
        };
        probe_transport_.remove = [this](
            const DeleteEntity::Request &request,
            std::function<void(bool)> completion) {
          auto req = std::make_shared<DeleteEntity::Request>(request);
          probe_delete_client_->async_send_request(req,
              [completion = std::move(completion)](
                  rclcpp::Client<DeleteEntity>::SharedFuture future) {
                bool success = false;
                try { success = future.get() && future.get()->success; }
                catch (const std::exception &) { success = false; }
                completion(success);
              });
        };
        probe_model_sdf_path_ = ament_index_cpp::get_package_share_directory(
            "ROBOT_URDF_final_description") +
            "/models/b2_contact_probe/model.sdf";
        return;
      case backend_detail::RuntimeResourceKind::Executor:
      {
        rclcpp::ExecutorOptions options;
        options.context = context_;
        executor_ = std::make_shared<rclcpp::executors::SingleThreadedExecutor>(
            options);
        if (!executor_) throw std::runtime_error("backend_executor_missing");
        return;
      }
      case backend_detail::RuntimeResourceKind::ExecutorNodeRegistration:
        executor_->add_node(node_);
        return;
      case backend_detail::RuntimeResourceKind::ExecutorThread:
        executor_thread_ = std::thread([this] { executor_->spin(); });
        if (!executor_thread_.joinable())
          throw std::runtime_error("backend_executor_thread_missing");
        return;
      case backend_detail::RuntimeResourceKind::GazeboTransportNode:
        gt_pub_ = std::make_unique<gz::transport::Node>();
        if (!gt_pub_) throw std::runtime_error("ground_truth_node_missing");
        return;
      case backend_detail::RuntimeResourceKind::GroundTruthPublisher:
        gt_publisher_ = std::make_unique<gz::transport::Node::Publisher>(
            gt_pub_->Advertise<gz::msgs::Odometry>("/b2/ground_truth/odom"));
        if (!gt_publisher_)
          throw std::runtime_error("ground_truth_publisher_missing");
        return;
    }
    throw std::runtime_error("unknown_runtime_resource_kind");
  }

  void OnBackendControl(
      const ControlRequest &request, ControlResponse &response)
  {
    response = NewControlResponse(request.request_sequence);
    if (shutdown_started_.load())
    {
      response.result = ControlResponse::RESULT_REJECTED;
      response.reason_code = ControlResponse::REASON_FAULT_LATCHED;
      return;
    }
    if (request.schema_version != ControlRequest::SCHEMA_VERSION)
    {
      response.reason_code = ControlResponse::REASON_BAD_SCHEMA;
      return;
    }
    if (request.coordinator_ingress_instance_id == 0 ||
        request.coordinator_ingress_instance_id !=
            coordinator_ingress_instance_id_ ||
        request.expected_backend_instance_id != backend_instance_id_ ||
        request.session_id != session_id_ ||
        request.config_hash != config_hash_ ||
        request.asset_manifest_sha256 != asset_manifest_hash_ ||
        !LowerHex64(request.config_hash) ||
        !LowerHex64(request.asset_manifest_sha256))
    {
      response.reason_code = ControlResponse::REASON_IDENTITY_MISMATCH;
      return;
    }
    const auto request_bytes = SerializeControlRequest(request);
    std::lock_guard<std::mutex> lock(callback_mutex_);
    response.binding_revision = control_binding_revision_;
    const auto cached = control_cache_.find(request.request_sequence);
    if (cached != control_cache_.end())
    {
      if (cached->second.request_bytes != request_bytes)
      {
        callback_fault_flags_.fetch_or(BackendState::FAULT_COMMAND_INVALID);
        response.result = ControlResponse::RESULT_FAULTED;
        response.reason_code =
            ControlResponse::REASON_DUPLICATE_CONTENT_CONFLICT;
        return;
      }
      response = cached->second.response;
      return;
    }
    if (request.request_sequence < next_control_request_sequence_)
    {
      response.reason_code = ControlResponse::REASON_REQUEST_REPLAY;
      return;
    }
    if (request.request_sequence != next_control_request_sequence_)
    {
      callback_fault_flags_.fetch_or(BackendState::FAULT_COMMAND_SEQUENCE);
      response.result = ControlResponse::RESULT_FAULTED;
      response.reason_code = ControlResponse::REASON_REQUEST_GAP;
      return;
    }
    ++next_control_request_sequence_;
    if (request.operation < ControlRequest::OP_BIND_SESSION ||
        request.operation > ControlRequest::OP_BIND_RESET_CONTEXT)
    {
      response.reason_code = ControlResponse::REASON_BAD_OPERATION;
      CacheControlResponse(request.request_sequence, request_bytes, response);
      return;
    }
    if (!OperationFieldsValid(request))
    {
      response.reason_code = ControlResponse::REASON_UNUSED_FIELD_NONZERO;
      CacheControlResponse(request.request_sequence, request_bytes, response);
      return;
    }
    if (request.operation != ControlRequest::OP_INHIBIT &&
        request.expected_binding_revision != control_binding_revision_)
    {
      response.reason_code = ControlResponse::REASON_REVISION_MISMATCH;
      CacheControlResponse(request.request_sequence, request_bytes, response);
      return;
    }
    if (control_queue_.size() >= 8)
    {
      callback_fault_flags_.fetch_or(BackendState::FAULT_QUEUE);
      response.result = ControlResponse::RESULT_FAULTED;
      response.reason_code = ControlResponse::REASON_QUEUE_OVERFLOW;
      CacheControlResponse(request.request_sequence, request_bytes, response);
      return;
    }
    if (control_mutation_pending_ &&
        request.operation != ControlRequest::OP_INHIBIT &&
        !(request.operation == ControlRequest::OP_VERIFY_CONTACT_CAPABILITY &&
          request.probe_action == ControlRequest::PROBE_ACTION_QUERY) &&
        !(request.operation == ControlRequest::OP_VERIFY_CONTACT_CAPABILITY &&
          request.probe_action == ControlRequest::PROBE_ACTION_ABORT))
    {
      response.reason_code = ControlResponse::REASON_BUSY;
      CacheControlResponse(request.request_sequence, request_bytes, response);
      return;
    }
    PendingControl control{request, request_bytes};
    if (request.operation == ControlRequest::OP_INHIBIT)
    {
      for (auto it = control_queue_.begin(); it != control_queue_.end();) {
        const auto pending_sequence = it->request.request_sequence;
        auto pending_cache = control_cache_.find(pending_sequence);
        if (pending_cache != control_cache_.end()) {
          pending_cache->second.response.result =
              ControlResponse::RESULT_REJECTED;
          pending_cache->second.response.reason_code =
              ControlResponse::REASON_CANCELLED;
        }
        it = control_queue_.erase(it);
      }
      control_mutation_pending_ = false;
      control_queue_.push_front(std::move(control));
    }
    else
    {
      control_queue_.push_back(std::move(control));
      if (request.operation != ControlRequest::OP_VERIFY_CONTACT_CAPABILITY ||
          request.probe_action == ControlRequest::PROBE_ACTION_START)
        control_mutation_pending_ = true;
    }
    response.result = ControlResponse::RESULT_QUEUED;
    response.reason_code = ControlResponse::REASON_NONE;
    CacheControlResponse(request.request_sequence, request_bytes, response);
  }

  void ProcessBackendControlRequests(
      gz::sim::EntityComponentManager &ecm,
      std::int64_t sim_stamp_ns, std::uint64_t update_iteration,
      std::int64_t steady_now_ns,
      bool world_paused)
  {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (control_queue_.empty()) return;
    auto pending = std::move(control_queue_.front());
    control_queue_.pop_front();
    auto &request = pending.request;
    auto cached = control_cache_.find(request.request_sequence);
    if (cached == control_cache_.end()) return;
    auto &response = cached->second.response;
    std::uint16_t reason = ControlResponse::REASON_NONE;
    bool applied = false;
    if (request.operation != ControlRequest::OP_INHIBIT &&
        request.expected_binding_revision != control_binding_revision_)
    {
      reason = ControlResponse::REASON_REVISION_MISMATCH;
    }
    else if (request.operation == ControlRequest::OP_INHIBIT)
    {
      policy_open_ = false;
      if (gate_) gate_->Invalidate("backend_control_inhibit");
      if (probe_machine_.Running())
      {
        probe_machine_.Abort();
        probe_running_ = false;
        ++capability_revision_;
      }
      if (base_link_.Valid(ecm)) ApplyEmergencyZero(ecm);
      local_zero_override_ = true;
      applied = true;
      ++control_binding_revision_;
    }
    else if (request.operation == ControlRequest::OP_BIND_SESSION)
    {
      const auto barrier_ns = TimeNs(request.barrier_stamp);
      const auto lifecycle_ns = TimeNs(request.lifecycle_header_stamp);
      if (control_session_bound_ || request.motion_permitted ||
          request.primary_state > ControlRequest::PRIMARY_ACTIVE ||
          request.barrier_state != ControlRequest::BARRIER_READY ||
          request.lifecycle_sequence == 0 || barrier_ns <= 0 ||
          lifecycle_ns < 0 || request.lifecycle_frame_id != world_name_ ||
          request.final_publisher_instance_id == 0 ||
          request.policy_source_instance_id == 0 ||
          request.safe_stop_source_instance_id == 0 ||
          request.next_safe_stop_sequence == 0)
      {
        reason = ControlResponse::REASON_LIFECYCLE_MISMATCH;
      }
      else
      {
        GateBinding binding;
        binding.session_id = session_id_;
        binding.config_hash = config_hash_;
        binding.final_publisher_instance_id =
            request.final_publisher_instance_id;
        binding.safe_stop_source_instance_id =
            request.safe_stop_source_instance_id;
        binding.policy_source_instance_id = request.policy_source_instance_id;
        binding.next_safe_stop_sequence = request.next_safe_stop_sequence;
        binding.barrier_stamp_ns = barrier_ns;
        binding.episode_generation = request.episode_generation;
        binding.reset_epoch = request.reset_epoch;
        binding.runtime_generation = request.runtime_generation;
        gate_ = gate_factory_(std::move(binding));
        if (!gate_)
          reason = ControlResponse::REASON_FAULT_LATCHED;
        else
        {
          control_session_bound_ = true;
          bound_final_publisher_instance_id_ =
              request.final_publisher_instance_id;
          bound_policy_source_instance_id_ =
              request.policy_source_instance_id;
          bound_safe_stop_source_instance_id_ =
              request.safe_stop_source_instance_id;
          lifecycle_sequence_ = request.lifecycle_sequence;
          lifecycle_header_stamp_ns_ = lifecycle_ns;
          barrier_stamp_ns_ = barrier_ns;
          episode_generation_ = request.episode_generation;
          reset_epoch_ = request.reset_epoch;
          runtime_generation_ = request.runtime_generation;
          applied = true;
          ++control_binding_revision_;
        }
      }
    }
    else if (request.operation == ControlRequest::OP_BIND_PENDING_STEP)
    {
      const auto action_barrier_ns = TimeNs(request.action_barrier_stamp);
      if (!control_session_bound_ || request.motion_permitted || !gate_ ||
          probe_machine_.Running() || probe_machine_.NeedsCleanup() ||
          request.pending_step_index == 0 ||
          request.pending_source_sequence != request.pending_step_index ||
          request.pending_transition_id.empty() ||
          action_barrier_ns <= barrier_stamp_ns_)
      {
        reason = ControlResponse::REASON_PENDING_STEP_MISMATCH;
      }
      else if (!gate_->SetExpectedPolicyStep(
                   request.pending_step_index,
                   request.pending_source_sequence,
                   request.pending_transition_id))
      {
        reason = ControlResponse::REASON_PENDING_STEP_MISMATCH;
      }
      else
      {
        applied = true;
        ++control_binding_revision_;
      }
    }
    else if (request.operation == ControlRequest::OP_CONFIRM_OBSERVATION0)
    {
      const auto cutoff_ns = TimeNs(request.observation0_cutoff);
      const auto lifecycle_ns = TimeNs(request.lifecycle_header_stamp);
      const bool lifecycle_matches = control_session_bound_ &&
          !request.motion_permitted && gate_ &&
          request.primary_state == ControlRequest::PRIMARY_ACTIVE &&
          request.barrier_state == ControlRequest::BARRIER_READY &&
          request.lifecycle_sequence == lifecycle_sequence_ &&
          request.episode_generation == episode_generation_ &&
          request.reset_epoch == reset_epoch_ &&
          request.runtime_generation == runtime_generation_ &&
          request.lifecycle_frame_id == world_name_ &&
          lifecycle_ns == lifecycle_header_stamp_ns_ &&
          lifecycle_ns <= sim_stamp_ns &&
          sim_stamp_ns - lifecycle_ns <= 500'000'000 &&
          TimeNs(request.barrier_stamp) == barrier_stamp_ns_ &&
          request.selected_zero_final_publisher_instance_id ==
              bound_final_publisher_instance_id_ &&
          request.adjacent_boundary_final_publisher_instance_id ==
              bound_final_publisher_instance_id_ &&
          cutoff_ns > barrier_stamp_ns_ && cutoff_ns <= sim_stamp_ns;
      if (!lifecycle_matches || observation0_authorized_ || probe_running_ ||
          probe_machine_.Running() || probe_machine_.NeedsCleanup())
      {
        reason = ControlResponse::REASON_OBSERVATION0_PROOF_MISMATCH;
      }
      else
      {
        const auto proof = ValidateObservation0Proof(
            accepted_receipt_history_, application_history_, contact_history_,
            session_id_, config_hash_,
            bound_final_publisher_instance_id_,
            bound_safe_stop_source_instance_id_, episode_generation_,
            reset_epoch_, runtime_generation_, barrier_stamp_ns_,
            request.selected_zero_final_publish_sequence,
            request.adjacent_boundary_final_publish_sequence,
            cutoff_ns, sim_stamp_ns);
        if (!proof.valid)
        {
          reason = ControlResponse::REASON_OBSERVATION0_PROOF_MISMATCH;
        }
        else
        {
          observation0_authorized_ = true;
          policy_open_ = false;
          local_zero_override_ = true;
          applied = true;
          ++control_binding_revision_;
        }
      }
    }
    else if (request.operation == ControlRequest::OP_VERIFY_CONTACT_CAPABILITY)
    {
      const auto lifecycle_ns = TimeNs(request.lifecycle_header_stamp);
      if (request.probe_action == ControlRequest::PROBE_ACTION_START)
      {
        const auto existing_fixture = FindProbeModels(ecm);
        const bool lifecycle_matches = control_session_bound_ && gate_ &&
            !request.motion_permitted &&
            request.primary_state == ControlRequest::PRIMARY_ACTIVE &&
            request.barrier_state == ControlRequest::BARRIER_READY &&
            request.lifecycle_sequence == lifecycle_sequence_ &&
            request.episode_generation == episode_generation_ &&
            request.reset_epoch == reset_epoch_ &&
            request.runtime_generation == runtime_generation_ &&
            request.lifecycle_frame_id == world_name_ &&
            lifecycle_ns == lifecycle_header_stamp_ns_ &&
            lifecycle_ns <= sim_stamp_ns &&
            sim_stamp_ns - lifecycle_ns <= 500'000'000 &&
            TimeNs(request.barrier_stamp) == barrier_stamp_ns_;
        const bool services_ready = probe_transport_.spawn_ready &&
            probe_transport_.pose_ready && probe_transport_.remove_ready &&
            probe_transport_.spawn_ready() && probe_transport_.pose_ready() &&
            probe_transport_.remove_ready() && probe_transport_.spawn &&
            probe_transport_.set_pose && probe_transport_.remove;
        const auto admission = EvaluateProbeAdmission(
            lifecycle_matches, !policy_open_, world_paused, fault_flags_ != 0,
            observation0_authorized_, gate_ && gate_->HasPendingPolicyStep(),
            probe_machine_.Running() || probe_machine_.NeedsCleanup(),
            contact_capability_verified_, !existing_fixture.empty(),
            services_ready && !probe_model_sdf_path_.empty() &&
              std::filesystem::is_regular_file(probe_model_sdf_path_) &&
              !observed_engine_plugin_path_.empty() &&
              LowerHex64(proof_physics_engine_fingerprint_sha256_));
        if (admission != ProbeAdmission::Ready)
        {
          reason = admission == ProbeAdmission::FixtureConflict ?
              ControlResponse::REASON_FIXTURE_CONFLICT :
              ControlResponse::REASON_CONTACT_PROBE_NOT_READY;
        }
        else if (!probe_machine_.Start(request.request_sequence, steady_now_ns))
        {
          reason = ControlResponse::REASON_BUSY;
        }
        else
        {
          probe_start_request_sequence_ = request.request_sequence;
          probe_running_ = true;
          probe_spawn_sent_ = probe_lift_sent_ = probe_remove_sent_ = false;
          contact_capability_verified_ = false;
          ++capability_revision_;
          probe_reason_.clear();
          applied = true;
        }
      }
      else if (request.probe_action == ControlRequest::PROBE_ACTION_QUERY)
      {
        if (request.probe_start_request_sequence !=
                probe_start_request_sequence_ ||
            request.probe_start_request_sequence == 0)
          reason = ControlResponse::REASON_CONTACT_PROBE_NOT_READY;
        else if (probe_machine_.Phase() == ProbePhase::Failed ||
                 probe_machine_.Phase() == ProbePhase::Cancelled)
          reason = ControlResponse::REASON_CONTACT_PROBE_FAILED;
        else
          applied = true;
      }
      else if (request.probe_action == ControlRequest::PROBE_ACTION_ABORT)
      {
        if (request.probe_start_request_sequence !=
                probe_start_request_sequence_ ||
            request.probe_start_request_sequence == 0 ||
            (!probe_machine_.Running() && !probe_machine_.NeedsCleanup()))
          reason = ControlResponse::REASON_CONTACT_PROBE_NOT_READY;
        else
        {
          probe_machine_.Abort();
          probe_running_ = false;
          contact_capability_verified_ = false;
          ++capability_revision_;
          probe_reason_ = "probe_aborted_by_control_request";
          applied = true;
        }
      }
      else reason = ControlResponse::REASON_BAD_OPERATION;
    }
    else if (request.operation == ControlRequest::OP_BIND_RESET_CONTEXT)
    {
      const auto barrier_ns = TimeNs(request.barrier_stamp);
      const auto lifecycle_ns = TimeNs(request.lifecycle_header_stamp);
      const bool context_forward = gate_ && IsForwardResetContext(
          lifecycle_sequence_, request.lifecycle_sequence,
          barrier_stamp_ns_, barrier_ns, episode_generation_,
          request.episode_generation, reset_epoch_, request.reset_epoch,
          runtime_generation_, request.runtime_generation,
          gate_->ExpectedSafeStopSequence(), request.next_safe_stop_sequence);
      const bool interrupted_by_inhibit = std::any_of(
          control_queue_.begin(), control_queue_.end(),
          [](const PendingControl &queued) {
            return queued.request.operation == ControlRequest::OP_INHIBIT;
          });
      if (!control_session_bound_ || !gate_ || request.motion_permitted ||
          policy_open_ || interrupted_by_inhibit || probe_running_ ||
          probe_machine_.Running() || probe_machine_.NeedsCleanup() ||
          request.primary_state == ControlRequest::PRIMARY_UNCONFIGURED ||
          request.primary_state > ControlRequest::PRIMARY_ACTIVE ||
          request.barrier_state != ControlRequest::BARRIER_READY ||
          request.lifecycle_sequence <= lifecycle_sequence_ ||
          lifecycle_ns < 0 || lifecycle_ns <= lifecycle_header_stamp_ns_ ||
          lifecycle_ns > sim_stamp_ns || lifecycle_ns < barrier_ns ||
          request.lifecycle_frame_id != world_name_ ||
          barrier_ns <= barrier_stamp_ns_ || barrier_ns > sim_stamp_ns ||
          !context_forward ||
          request.final_publisher_instance_id !=
              bound_final_publisher_instance_id_ ||
          request.policy_source_instance_id !=
              bound_policy_source_instance_id_ ||
          request.safe_stop_source_instance_id !=
              bound_safe_stop_source_instance_id_ ||
          request.next_safe_stop_sequence == 0)
      {
        reason = ControlResponse::REASON_CONTEXT_NOT_NEW;
      }
      else if (!gate_->BindResetContext(
                   barrier_ns, request.episode_generation,
                   request.reset_epoch, request.runtime_generation,
                   request.next_safe_stop_sequence))
      {
        reason = ControlResponse::REASON_CONTEXT_NOT_NEW;
      }
      else
      {
        policy_open_ = false;
        observation0_authorized_ = false;
        selected_receipt_.reset();
        pending_applied_receipt_.reset();
        lifecycle_sequence_ = request.lifecycle_sequence;
        lifecycle_header_stamp_ns_ = lifecycle_ns;
        barrier_stamp_ns_ = barrier_ns;
        episode_generation_ = request.episode_generation;
        reset_epoch_ = request.reset_epoch;
        runtime_generation_ = request.runtime_generation;
        local_zero_override_ = true;
        applied = true;
        ++control_binding_revision_;
      }
    }
    else
    {
      reason = ControlResponse::REASON_BAD_OPERATION;
    }
    if (applied)
    {
      response.result = ControlResponse::RESULT_APPLIED;
      response.reason_code = ControlResponse::REASON_NONE;
      response.binding_revision = control_binding_revision_;
      response.applied_binding_revision = control_binding_revision_;
      response.applied_physics_iteration = update_iteration;
      if (sim_stamp_ns >= 0)
      {
        response.applied_sim_stamp.sec = static_cast<std::int32_t>(
            sim_stamp_ns / 1'000'000'000LL);
        response.applied_sim_stamp.nanosec = static_cast<std::uint32_t>(
            sim_stamp_ns % 1'000'000'000LL);
      }
    }
    else
    {
      response.result = ControlResponse::RESULT_REJECTED;
      response.reason_code = reason;
    }
    response.backend_instance_id = backend_instance_id_;
    PopulateProbeResponse(response);
    control_mutation_pending_ = false;
    if (request.operation == ControlRequest::OP_INHIBIT ||
        request.operation == ControlRequest::OP_BIND_SESSION ||
        request.operation == ControlRequest::OP_BIND_PENDING_STEP ||
        request.operation == ControlRequest::OP_BIND_RESET_CONTEXT ||
        request.operation == ControlRequest::OP_CONFIRM_OBSERVATION0 ||
        (request.operation == ControlRequest::OP_VERIFY_CONTACT_CAPABILITY &&
         request.probe_action == ControlRequest::PROBE_ACTION_START))
      control_mutation_pending_ = false;
    (void)steady_now_ns;
  }

  void OnReceipt(const Receipt &msg)
  {
    if (shutdown_started_.load()) return;
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
    if (!gate_ || !gate_->Enqueue(std::move(facts), NowSteadyNs()))
      callback_fault_flags_.fetch_or(BackendState::FAULT_QUEUE);
  }

  void OnSafetyInput(const SafetyInput &msg)
  {
    if (shutdown_started_.load()) return;
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
      // Public B2.1 input has no observation0 proof and cannot bind the B2.3
      // pending step. Keep the backend inhibited until B2.3 supplies it.
      // backend inhibited until that binding is supplied through its private
      // trusted port in a later work package.
      policy_open_ = false;
      if (msg.session_id != session_id_ || msg.config_hash != config_hash_ ||
          msg.schema_version != SafetyInput::SCHEMA_VERSION ||
          msg.ingress_instance_id == 0 || msg.sample_sequence == 0 ||
          msg.runtime_generation == 0 || msg.episode_generation == 0 ||
          msg.header.frame_id != "base_link")
      {
        SetFault(BackendState::FAULT_CONTEXT, "safety_input_identity_invalid");
        continue;
      }
      if (msg.odometry_status == SafetyInput::ODOM_VALID)
      {
        if (msg.measured_twist.size() != 3 ||
            !std::all_of(msg.measured_twist.begin(), msg.measured_twist.end(),
              [](double value) { return std::isfinite(value); }))
        {
          SetFault(BackendState::FAULT_CONTEXT, "safety_input_twist_invalid");
          continue;
        }
      }
      else if (!msg.measured_twist.empty())
      {
        SetFault(BackendState::FAULT_CONTEXT, "nonvalid_odometry_has_twist");
        continue;
      }
      safety_input_ = msg;
      safety_receive_steady_ns_ = received_ns;
    }
  }

  void ApplyEmergencyZero(gz::sim::EntityComponentManager &ecm)
  {
    if (actuator_apply_)
    {
      actuator_apply_(ecm, BodyCommand3D{});
    }
    else
    {
      base_link_.SetLinearVelocity(ecm, {0, 0, 0});
      base_link_.SetAngularVelocity(ecm, {0, 0, 0});
    }
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
    for (const auto &[collision, bit] : collision_contact_bits_)
    {
      const auto *component = ecm.Component<gz::sim::components::ContactSensorData>(collision);
      if (!component) continue;
      const auto &contacts = component->Data();
      out.observed_mask |= bit;
      out.component_present = true;
      for (int i = 0; i < contacts.contact_size(); ++i)
      {
        const auto &contact = contacts.contact(i);
        const auto collision1 = static_cast<gz::sim::Entity>(
          contact.collision1().id());
        const auto collision2 = static_cast<gz::sim::Entity>(
          contact.collision2().id());
        const auto pair = ClassifyContactPair(
          collision1, collision2, floor_collision_entity_,
          collision_entity_names_, wheel_floor_collisions_);
        if (!pair.tracked) continue;
        const bool floor_pair = pair.exact_floor_pair;
        const bool wheel_floor_ignore = pair.wheel_floor_ignore;
        if (floor_pair && wheel_floor_ignore)
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
    if (ground_truth_sink_)
    {
      ground_truth_sink_(msg);
      return;
    }
    if (!gt_pub_ || !gt_publisher_)
    {
      SetFault(BackendState::FAULT_CONTEXT,
               "ground_truth_transport_not_initialized");
      return;
    }
    gt_publisher_->Publish(msg);
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
      application_history_.push_back({
          pending_applied_receipt_->key.publisher_instance_id,
          pending_applied_receipt_->key.publish_sequence, info.iterations,
          stamp_ns, true, false});
      if (application_history_.size() > 128)
        application_history_.erase(application_history_.begin());
    }
    else
    {
      msg.applied_receipt_valid = false;
      msg.applied_final_publisher_instance_id = 0; msg.applied_final_publish_sequence = 0;
      msg.applied_physics_iteration = 0; msg.applied_sim_stamp.sec = 0; msg.applied_sim_stamp.nanosec = 0;
    }
    if (backend_state_sink_)
      backend_state_sink_(msg);
    else
      state_pub_->publish(msg);
    if (pending_applied_receipt_)
      last_accepted_key_ = pending_applied_receipt_->key;
    pending_applied_receipt_.reset();
  }

  void SetFault(std::uint32_t flag, std::string reason)
  {
    fault_flags_ |= flag;
    if (fault_reason_.empty())
    {
      fault_reason_ = std::move(reason);
      gzerr << "mecanum_sim_backend inhibited: " << fault_reason_ << std::endl;
    }
    policy_open_ = false;
    if (contact_capability_verified_ || probe_machine_.Running())
    {
      contact_capability_verified_ = false;
      ++capability_revision_;
      probe_machine_.Invalidate();
      probe_running_ = false;
      probe_reason_ = "backend_fault_invalidated_contact_capability";
    }
  }

  gz::sim::Entity world_entity_{gz::sim::kNullEntity};
  gz::sim::Entity model_entity_{gz::sim::kNullEntity};
  gz::sim::Entity floor_collision_entity_{gz::sim::kNullEntity};
  gz::sim::Entity probe_sensor_entity_{gz::sim::kNullEntity};
  gz::sim::World world_{gz::sim::kNullEntity};
  gz::sim::Model model_{gz::sim::kNullEntity};
  gz::sim::Link base_link_{gz::sim::kNullEntity};
  std::string world_name_, model_name_, base_link_name_, session_id_, config_hash_, asset_manifest_hash_;
  std::string probe_collision_name_, fault_reason_;
  std::shared_ptr<ReceiptGate> gate_;
  std::shared_ptr<ContactCoverage> contact_coverage_;
  std::function<std::shared_ptr<ReceiptGate>(GateBinding)> gate_factory_;
  std::function<std::shared_ptr<ContactCoverage>(std::uint32_t)>
      contact_coverage_factory_;
  std::function<void()> after_native_resources_created_;
  std::function<std::function<void()>(
      backend_detail::RuntimeResourceKind, const std::function<void()> &)>
      runtime_resource_factory_;
  std::function<void(backend_detail::RuntimeResourceKind)>
      after_runtime_resource_created_;
  std::vector<std::pair<backend_detail::RuntimeResourceKind,
                        std::function<void()>>> runtime_resource_releases_;
  std::function<void(const BackendState &)> backend_state_sink_;
  std::function<void(const gz::msgs::Odometry &)> ground_truth_sink_;
  std::function<void(gz::sim::EntityComponentManager &,
                     const BodyCommand3D &)> actuator_apply_;
  std::unordered_map<std::string,std::uint64_t> collision_bits_;
  std::unordered_map<std::uint64_t,std::string> collision_entity_names_;
  std::unordered_map<gz::sim::Entity,std::uint64_t> collision_contact_bits_;
  std::unordered_set<std::string> wheel_floor_collisions_;
  std::shared_ptr<rclcpp::Context> context_;
  rclcpp::Node::SharedPtr node_;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> executor_;
  std::thread executor_thread_;
  rclcpp::Subscription<Receipt>::SharedPtr receipt_sub_;
  rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr twist_sub_;
  rclcpp::Subscription<SafetyInput>::SharedPtr safety_sub_;
  rclcpp::Publisher<BackendState>::SharedPtr state_pub_;
  rclcpp::Service<BackendControl>::SharedPtr control_service_;
  rclcpp::Client<SpawnEntity>::SharedPtr probe_spawn_client_;
  rclcpp::Client<SetEntityPose>::SharedPtr probe_pose_client_;
  rclcpp::Client<DeleteEntity>::SharedPtr probe_delete_client_;
  ProbeServiceTransport probe_transport_;
  std::unique_ptr<gz::transport::Node> gt_pub_;
  std::unique_ptr<gz::transport::Node::Publisher> gt_publisher_;
  std::mutex callback_mutex_;
  std::deque<std::pair<SafetyInput, std::int64_t>> safety_queue_;
  std::deque<PendingControl> control_queue_;
  std::deque<ProbeServiceResult> probe_service_results_;
  std::map<std::uint64_t, CachedControl> control_cache_;
  std::atomic<std::uint32_t> callback_fault_flags_{};
  SafetyInput safety_input_;
  geometry_msgs::msg::Twist captured_twist_;
  std::int64_t captured_twist_received_steady_ns_{};
  std::int64_t safety_receive_steady_ns_{};
  std::uint64_t policy_instance_id_{}, backend_instance_id_{1}, status_sequence_{}, physics_iteration_{};
  std::uint64_t coordinator_ingress_instance_id_{};
  std::uint64_t bound_final_publisher_instance_id_{};
  std::uint64_t bound_policy_source_instance_id_{};
  std::uint64_t bound_safe_stop_source_instance_id_{};
  std::uint64_t next_control_request_sequence_{1};
  std::uint64_t control_binding_revision_{};
  std::uint64_t lifecycle_sequence_{}, episode_generation_{};
  std::int64_t barrier_stamp_ns_{};
  std::int64_t lifecycle_header_stamp_ns_{};
  std::uint32_t reset_epoch_{}, runtime_generation_{};
  std::uint32_t fault_flags_{};
  std::int64_t last_sim_ns_{}, last_sim_advance_steady_ns_{}, selected_steady_ns_{};
  bool configured_{}, runtime_resources_ready_{}, policy_open_{};
  bool local_zero_override_{true}, measurement_healthy_{};
  bool contact_capability_verified_{};
  bool probe_running_{};
  bool observation0_authorized_{};
  bool control_session_bound_{}, control_mutation_pending_{};
  std::optional<ReceiptFacts> selected_receipt_, pending_applied_receipt_;
  std::optional<ReceiptKey> last_accepted_key_;
  std::vector<ReceiptFacts> accepted_receipt_history_;
  std::vector<AppliedReceiptFact> application_history_;
  std::vector<ContactHistoryFact> contact_history_;
  ContactProbeMachine probe_machine_;
  ContactDecision contact_decision_;
  std::string probe_model_sdf_path_, probe_reason_;
  std::string proof_collision_registry_sha256_, proof_world_name_;
  std::string proof_physics_engine_plugin_, proof_gz_sim_version_;
  std::string observed_engine_plugin_path_;
  std::string proof_physics_engine_fingerprint_sha256_;
  std::string proof_probe_model_name_, proof_probe_collision_name_;
  std::string proof_floor_collision_name_, proof_session_id_;
  std::string proof_config_hash_, proof_asset_manifest_hash_;
  std::uint64_t capability_revision_{}, probe_start_request_sequence_{};
  std::uint64_t proof_backend_instance_id_{}, proof_contact_first_iteration_{};
  std::uint64_t proof_contact_last_iteration_{}, proof_empty_first_iteration_{};
  std::uint64_t proof_empty_last_iteration_{};
  std::int64_t proof_contact_first_stamp_ns_{}, proof_contact_last_stamp_ns_{};
  std::int64_t proof_empty_first_stamp_ns_{}, proof_empty_last_stamp_ns_{};
  std::int64_t proof_stamp_ns_{};
  bool probe_spawn_sent_{}, probe_lift_sent_{}, probe_remove_sent_{};
};
}  // namespace mecanum_sim_backend

GZ_ADD_PLUGIN(mecanum_sim_backend::BackendSystem, gz::sim::System,
              gz::sim::ISystemConfigure, gz::sim::ISystemPreUpdate,
              gz::sim::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(mecanum_sim_backend::BackendSystem,
                    "mecanum_sim_backend::BackendSystem")
