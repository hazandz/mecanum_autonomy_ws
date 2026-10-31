#include <gtest/gtest.h>
#include <limits>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/LinearVelocity.hh>
#include <gz/sim/components/AngularVelocity.hh>
#include <gz/sim/components/Sensor.hh>
#include <gz/sim/components/World.hh>
#include <sdf/Root.hh>
#include "../src/backend_system.cpp"
#include "mecanum_sim_backend/backend_system.hpp"
#include "mecanum_sim_backend/contact_coverage.hpp"
using namespace mecanum_sim_backend;
using ControlRequest = mecanum_nav_rl_interfaces::srv::LocalTrainingBackendControl::Request;
using ControlResponse = mecanum_nav_rl_interfaces::srv::LocalTrainingBackendControl::Response;

namespace mecanum_sim_backend
{
struct NativeFactoryCounters
{
  std::uint32_t contact_created{};
  std::uint32_t contact_released{};
  std::uint32_t runtime_boundary_calls{};
  std::uint32_t context_created{};
  std::uint32_t context_released{};
  std::array<std::uint32_t, 15> runtime_created{};
  std::array<std::uint32_t, 15> runtime_released{};
  std::uint32_t actuator_calls{};
  std::uint32_t backend_state_calls{};
  std::uint32_t ground_truth_calls{};
};

struct NativeResetChainIo
{
  std::uint32_t spawn_calls{};
  std::uint32_t lift_calls{};
  std::uint32_t remove_calls{};
  std::uint32_t actuator_calls{};
  std::uint32_t backend_state_calls{};
  std::uint32_t ground_truth_calls{};
  std::vector<BodyCommand3D> applied_commands;
};

class BackendSystemTestPeer
{
public:
  static void SeedRunDescriptor(BackendSystem &system)
  {
    system.world_name_ = "b2_training_arena";
    system.session_id_ = "test-session";
    system.config_hash_ = std::string(64, 'a');
    system.asset_manifest_hash_ = std::string(64, 'b');
    system.coordinator_ingress_instance_id_ = 7;
    system.backend_instance_id_ = 8;
  }

  static void SeedObservationHistory(
      BackendSystem &system, bool local_override = false,
      std::uint64_t adjacent_sequence = 42,
      std::uint64_t selected_sequence = 41,
      bool selected_zero = true,
      std::int64_t selected_stamp = 120,
      bool contact_history_complete = true)
  {
    ReceiptFacts selected;
    selected.session_id = system.session_id_;
    selected.config_hash = system.config_hash_;
    selected.key = {11, selected_sequence};
    selected.episode_generation = 2;
    selected.reset_epoch = 3;
    selected.runtime_generation = 4;
    selected.source = 4;
    selected.sequence = 6;
    selected.source_instance_id = 33;
    selected.stamp_ns = selected_stamp;
    selected.frame_id = "base_link";
    selected.twist = selected_zero ?
        std::array<double, 6>{0, 0, 0, 0, 0, 0} :
        std::array<double, 6>{0.01, 0, 0, 0, 0, 0};
    ReceiptFacts adjacent = selected;
    adjacent.key.publish_sequence = adjacent_sequence;
    adjacent.source = 1;
    adjacent.sequence = 7;
    adjacent.source_instance_id = 22;
    adjacent.stamp_ns = 151;
    adjacent.twist = {0.1, 0, 0, 0, 0, 0};
    system.accepted_receipt_history_ = {selected, adjacent};
    system.application_history_ = {{11, 41, 12, 130, true, local_override}};
    system.contact_history_ = contact_history_complete ?
      std::vector<ContactHistoryFact>{
        {12, 130, true, true, false},
        {13, 140, true, true, false},
        {14, 150, true, true, false}} :
      std::vector<ContactHistoryFact>{};
  }

  static void MutateObservationHistory(BackendSystem &system, int mutation)
  {
    switch (mutation)
    {
      case 0:
        system.application_history_.front().publisher_instance_id = 99;
        break;
      case 1:
        system.application_history_.front().physics_iteration = 0;
        break;
      case 2:
        system.accepted_receipt_history_.front().session_id = "foreign-session";
        break;
      case 3:
        system.accepted_receipt_history_.front().config_hash = std::string(64, 'c');
        break;
      case 4:
        system.accepted_receipt_history_.front().reset_epoch += 1;
        break;
      case 5:
        system.contact_history_.clear();
        break;
      case 6:
        system.contact_history_[1].physics_iteration += 2;
        break;
      default:
        break;
    }
  }

  static void Tick(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      std::int64_t sim_ns = 200, std::uint64_t iteration = 20,
      std::int64_t steady_ns = 2'000'000'000)
  {
    system.ProcessBackendControlRequests(ecm, sim_ns, iteration, steady_ns, false);
  }

  static bool SessionBound(const BackendSystem &system)
  {
    return system.control_session_bound_;
  }

  static void ConfigureMissingModel(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm)
  {
    gz::sim::EventManager events;
    system.Configure(gz::sim::kNullEntity, nullptr, ecm, events);
  }

  static bool ConfigureInvalidModel(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      bool create_world)
  {
    sdf::Root root;
    const auto errors = root.Load(
        "/home/hazan/roadmap-b-b22-simulation-substrate/ros2_ws/src/"
        "ROBOT_URDF_final_description/models/mecanum_b2/model.sdf");
    if (!errors.empty() || !root.Model() || root.Model()->Plugins().empty())
      return false;
    gz::sim::Entity parent = gz::sim::kNullEntity;
    if (create_world)
    {
      parent = ecm.CreateEntity();
      ecm.CreateComponent(parent,
          gz::sim::components::Name("b2_training_arena"));
      ecm.CreateComponent(parent, gz::sim::components::World());
    }
    const auto model = ecm.CreateEntity();
    ecm.CreateComponent(model, gz::sim::components::Name("mecanum_b2"));
    ecm.CreateComponent(model, gz::sim::components::Model());
    if (create_world)
      ecm.CreateComponent(model, gz::sim::components::ParentEntity(parent));
    gz::sim::EventManager events;
    system.Configure(model, root.Model()->Plugins().front().Element(),
                     ecm, events);
    return true;
  }

  static bool ConfigureWithInjectedRuntimeFailure(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      const std::shared_ptr<NativeFactoryCounters> &counters,
      std::size_t fail_after)
  {
    sdf::Root root;
    const auto errors = root.Load(
        "/home/hazan/roadmap-b-b22-simulation-substrate/ros2_ws/src/"
        "ROBOT_URDF_final_description/models/mecanum_b2/model.sdf");
    if (!errors.empty() || !root.Model() || root.Model()->Plugins().empty())
      return false;

    const auto world = ecm.CreateEntity();
    ecm.CreateComponent(world,
        gz::sim::components::Name("b2_training_arena"));
    ecm.CreateComponent(world, gz::sim::components::World());
    const auto model = ecm.CreateEntity();
    ecm.CreateComponent(model, gz::sim::components::Name("mecanum_b2"));
    ecm.CreateComponent(model, gz::sim::components::Model());
    ecm.CreateComponent(model, gz::sim::components::ParentEntity(world));
    const auto link = ecm.CreateEntity();
    ecm.CreateComponent(link, gz::sim::components::Name("base_link"));
    ecm.CreateComponent(link, gz::sim::components::Link());
    ecm.CreateComponent(link, gz::sim::components::ParentEntity(model));

    system.contact_coverage_factory_ = [counters](std::uint32_t count) {
      ++counters->contact_created;
      return std::shared_ptr<ContactCoverage>(
          new ContactCoverage(count), [counters](ContactCoverage *resource) {
            ++counters->contact_released;
            delete resource;
          });
    };
    system.after_native_resources_created_ = [counters] {
      ++counters->runtime_boundary_calls;
    };
    system.runtime_resource_factory_ = [counters](
        backend_detail::RuntimeResourceKind resource,
        const std::function<void()> &) {
      const auto index = static_cast<std::size_t>(resource);
      ++counters->runtime_created.at(index);
      if (resource == backend_detail::RuntimeResourceKind::Context)
        ++counters->context_created;
      return [counters, resource] {
        const auto released_index = static_cast<std::size_t>(resource);
        ++counters->runtime_released.at(released_index);
        if (resource == backend_detail::RuntimeResourceKind::Context)
          ++counters->context_released;
      };
    };
    system.actuator_apply_ = [counters](
        gz::sim::EntityComponentManager &, const BodyCommand3D &) {
      ++counters->actuator_calls;
    };
    system.backend_state_sink_ = [counters](const BackendState &) {
      ++counters->backend_state_calls;
    };
    system.ground_truth_sink_ = [counters](const gz::msgs::Odometry &) {
      ++counters->ground_truth_calls;
    };
    system.after_runtime_resource_created_ = [fail_after](
        backend_detail::RuntimeResourceKind resource) {
      if (static_cast<std::size_t>(resource) + 1 == fail_after)
        throw std::runtime_error("injected failure after runtime resource");
    };

    gz::sim::EventManager events;
    system.Configure(model, root.Model()->Plugins().front().Element(),
                     ecm, events);
    return true;
  }

  static bool ConfigureForNativeResetChain(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      const std::shared_ptr<NativeResetChainIo> &io)
  {
    constexpr const char *model_path =
        "/home/hazan/roadmap-b-b22-simulation-substrate/ros2_ws/src/"
        "ROBOT_URDF_final_description/models/mecanum_b2/model.sdf";
    constexpr const char *probe_path =
        "/home/hazan/roadmap-b-b22-simulation-substrate/ros2_ws/src/"
        "ROBOT_URDF_final_description/models/b2_contact_probe/model.sdf";
    constexpr const char *physics_path =
        "/opt/ros/jazzy/opt/gz_physics_vendor/lib/gz-physics-7/"
        "engine-plugins/libgz-physics7-bullet-plugin.so.7.6.0";
    sdf::Root root;
    if (!root.Load(model_path).empty() || !root.Model() ||
        root.Model()->Plugins().empty())
      return false;
    auto plugin = root.Model()->Plugins().front().Element();
    const auto set_string = [&plugin](
        const std::string &key, const std::string &value) {
      const auto element = plugin->GetElement(key);
      return element && element->Set<std::string>(value);
    };
    const auto set_u64 = [&plugin](const std::string &key, std::uint64_t value) {
      const auto element = plugin->GetElement(key);
      return element && element->Set<std::uint64_t>(value);
    };
    if (!set_string("session_id", "native-reset-chain") ||
        !set_string("config_hash", std::string(64, 'a')) ||
        !set_string("asset_manifest_sha256", std::string(64, 'b')) ||
        !set_u64("coordinator_ingress_instance_id", 7))
      return false;

    const auto world = ecm.CreateEntity();
    ecm.CreateComponent(world,
        gz::sim::components::Name("b2_training_arena"));
    ecm.CreateComponent(world, gz::sim::components::World());
    ecm.CreateComponent(world,
        gz::sim::components::PhysicsEnginePlugin(physics_path));
    const auto floor_model = ecm.CreateEntity();
    ecm.CreateComponent(floor_model,
        gz::sim::components::Name("ground_plane"));
    ecm.CreateComponent(floor_model, gz::sim::components::Model());
    ecm.CreateComponent(floor_model,
        gz::sim::components::ParentEntity(world));
    const auto floor_link = ecm.CreateEntity();
    ecm.CreateComponent(floor_link, gz::sim::components::Name("link"));
    ecm.CreateComponent(floor_link, gz::sim::components::Link());
    ecm.CreateComponent(floor_link,
        gz::sim::components::ParentEntity(floor_model));
    const auto floor_collision = ecm.CreateEntity();
    ecm.CreateComponent(floor_collision,
        gz::sim::components::Name("collision"));
    ecm.CreateComponent(floor_collision,
        gz::sim::components::Collision());
    ecm.CreateComponent(floor_collision,
        gz::sim::components::ParentEntity(floor_link));

    const auto model = ecm.CreateEntity();
    ecm.CreateComponent(model, gz::sim::components::Name("mecanum_b2"));
    ecm.CreateComponent(model, gz::sim::components::Model());
    ecm.CreateComponent(model, gz::sim::components::ParentEntity(world));
    for (std::uint64_t link_index = 0;
         link_index < root.Model()->LinkCount(); ++link_index)
    {
      const auto *link_sdf = root.Model()->LinkByIndex(link_index);
      if (!link_sdf) return false;
      const auto link = ecm.CreateEntity();
      ecm.CreateComponent(link,
          gz::sim::components::Name(link_sdf->Name()));
      ecm.CreateComponent(link, gz::sim::components::Link());
      ecm.CreateComponent(link, gz::sim::components::ParentEntity(model));
      if (link_sdf->Name() == "base_link")
      {
        ecm.CreateComponent(link, gz::sim::components::WorldPose(
            gz::math::Pose3d(0, 0, 0.10, 0, 0, 0)));
        ecm.CreateComponent(link, gz::sim::components::WorldLinearVelocity(
            gz::math::Vector3d::Zero));
        ecm.CreateComponent(link, gz::sim::components::WorldAngularVelocity(
            gz::math::Vector3d::Zero));
      }
      for (std::uint64_t collision_index = 0;
           collision_index < link_sdf->CollisionCount(); ++collision_index)
      {
        const auto *collision_sdf = link_sdf->CollisionByIndex(collision_index);
        if (!collision_sdf) return false;
        const auto collision = ecm.CreateEntity();
        ecm.CreateComponent(collision,
            gz::sim::components::Name(collision_sdf->Name()));
        ecm.CreateComponent(collision, gz::sim::components::Collision());
        ecm.CreateComponent(collision,
            gz::sim::components::ParentEntity(link));
        ecm.CreateComponent(collision,
            gz::sim::components::ContactSensorData(gz::msgs::Contacts()));
      }
      for (std::uint64_t sensor_index = 0;
           sensor_index < link_sdf->SensorCount(); ++sensor_index)
      {
        const auto *sensor_sdf = link_sdf->SensorByIndex(sensor_index);
        if (!sensor_sdf || sensor_sdf->Type() != sdf::SensorType::CONTACT)
          continue;
        const auto sensor = ecm.CreateEntity();
        ecm.CreateComponent(sensor,
            gz::sim::components::Name(sensor_sdf->Name()));
        ecm.CreateComponent(sensor, gz::sim::components::Sensor());
        ecm.CreateComponent(sensor,
            gz::sim::components::ParentEntity(link));
        ecm.CreateComponent(sensor,
            gz::sim::components::ContactSensor(sensor_sdf->Element()));
      }
    }

    system.runtime_resource_factory_ = [](
        backend_detail::RuntimeResourceKind,
        const std::function<void()> &) {
      return std::function<void()>([] {});
    };
    system.probe_model_sdf_path_ = probe_path;
    system.backend_state_sink_ = [io](const BackendState &) {
      ++io->backend_state_calls;
    };
    system.ground_truth_sink_ = [io](const gz::msgs::Odometry &) {
      ++io->ground_truth_calls;
    };
    system.actuator_apply_ = [io](
          gz::sim::EntityComponentManager &, const BodyCommand3D &command) {
        ++io->actuator_calls;
        io->applied_commands.push_back(command);
      };
    system.probe_transport_.spawn_ready = [] { return true; };
    system.probe_transport_.pose_ready = [] { return true; };
    system.probe_transport_.remove_ready = [] { return true; };
    system.probe_transport_.spawn = [io](
          const SpawnEntity::Request &,
          std::function<void(bool)> completion) {
        ++io->spawn_calls;
        completion(true);
      };
    system.probe_transport_.set_pose = [io](
          const SetEntityPose::Request &,
          std::function<void(bool)> completion) {
        ++io->lift_calls;
        completion(true);
      };
    system.probe_transport_.remove = [io](
          const DeleteEntity::Request &,
          std::function<void(bool)> completion) {
        ++io->remove_calls;
        completion(true);
      };
    gz::sim::EventManager events;
    system.Configure(model, plugin, ecm, events);
    return system.configured_ && system.fault_flags_ == 0;
  }

  static bool AddProbeFixture(
      gz::sim::EntityComponentManager &ecm,
      gz::sim::Entity world)
  {
    sdf::Root root;
    const auto path =
        "/home/hazan/roadmap-b-b22-simulation-substrate/ros2_ws/src/"
        "ROBOT_URDF_final_description/models/b2_contact_probe/model.sdf";
    if (!root.Load(path).empty() || !root.Model()) return false;
    const auto *link_sdf = root.Model()->LinkByName("link");
    const auto *sensor_sdf = link_sdf ?
        link_sdf->SensorByName("contact_sensor") : nullptr;
    if (!link_sdf || !sensor_sdf) return false;
    const auto model = ecm.CreateEntity();
    ecm.CreateComponent(model,
        gz::sim::components::Name("b2_capability_probe"));
    ecm.CreateComponent(model, gz::sim::components::Model());
    ecm.CreateComponent(model, gz::sim::components::ParentEntity(world));
    ecm.CreateComponent(model, gz::sim::components::WorldPose(
        gz::math::Pose3d(-2, 0, 0.07, 0, 0, 0)));
    const auto link = ecm.CreateEntity();
    ecm.CreateComponent(link, gz::sim::components::Name("link"));
    ecm.CreateComponent(link, gz::sim::components::Link());
    ecm.CreateComponent(link, gz::sim::components::ParentEntity(model));
    const auto collision = ecm.CreateEntity();
    ecm.CreateComponent(collision, gz::sim::components::Name("collision"));
    ecm.CreateComponent(collision, gz::sim::components::Collision());
    ecm.CreateComponent(collision,
        gz::sim::components::ParentEntity(link));
    ecm.CreateComponent(collision,
        gz::sim::components::ContactSensorData(gz::msgs::Contacts()));
    const auto sensor = ecm.CreateEntity();
    ecm.CreateComponent(sensor,
        gz::sim::components::Name("contact_sensor"));
    ecm.CreateComponent(sensor, gz::sim::components::Sensor());
    ecm.CreateComponent(sensor, gz::sim::components::ParentEntity(link));
    ecm.CreateComponent(sensor,
        gz::sim::components::ContactSensor(sensor_sdf->Element()));
    return true;
  }

  static void RunProductionTick(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      std::uint64_t iteration, std::int64_t sim_ns)
  {
    gz::sim::UpdateInfo info;
    info.iterations = iteration;
    info.simTime = std::chrono::nanoseconds(sim_ns);
    info.paused = false;
    system.PreUpdate(info, ecm);
    system.PostUpdate(info, ecm);
  }

  static std::uint64_t BackendInstance(const BackendSystem &system)
  {
    return system.backend_instance_id_;
  }

  static gz::sim::Entity WorldEntity(const BackendSystem &system)
  {
    return system.world_entity_;
  }

  static std::uint64_t ProbeCollisionEntity(const BackendSystem &system)
  {
    return system.probe_machine_.CollisionEntity();
  }

  static void RemoveProbeFixture(gz::sim::EntityComponentManager &ecm)
  {
    const auto model = ecm.EntityByComponents(
        gz::sim::components::Name("b2_capability_probe"),
        gz::sim::components::Model());
    if (model == gz::sim::kNullEntity) return;
    const auto children = ecm.EntitiesByComponents(
        gz::sim::components::ParentEntity(model));
    for (const auto child : children)
    {
      const auto grandchildren = ecm.EntitiesByComponents(
          gz::sim::components::ParentEntity(child));
      for (const auto grandchild : grandchildren)
        ecm.RequestRemoveEntity(grandchild);
      ecm.RequestRemoveEntity(child);
    }
    ecm.RequestRemoveEntity(model);
    ecm.ProcessRemoveEntityRequests();
  }

  static std::uint64_t RobotBaseLink(
      const gz::sim::EntityComponentManager &ecm)
  {
    return ecm.EntityByComponents(
        gz::sim::components::Name("base_link"),
        gz::sim::components::Link());
  }

  static void RemoveBaseLinkVelocityComponents(
      gz::sim::EntityComponentManager &ecm)
  {
    const auto link = ecm.EntityByComponents(
        gz::sim::components::Name("base_link"),
        gz::sim::components::Link());
    if (link == gz::sim::kNullEntity) return;
    ecm.RemoveComponent<gz::sim::components::WorldLinearVelocity>(link);
    ecm.RemoveComponent<gz::sim::components::WorldAngularVelocity>(link);
  }

  static void RemoveOneRegisteredContactComponent(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm)
  {
    if (system.collision_contact_bits_.empty()) return;
    ecm.RemoveComponent<gz::sim::components::ContactSensorData>(
        system.collision_contact_bits_.begin()->first);
  }

  static bool MeasurementHealthy(const BackendSystem &system)
  {
    return system.measurement_healthy_;
  }

  static std::vector<AppliedReceiptFact> ApplicationHistory(
      const BackendSystem &system)
  {
    return system.application_history_;
  }

  static void EarlyReceipt(BackendSystem &system, const Receipt &receipt)
  {
    system.OnReceipt(receipt);
  }

  static std::uint32_t CallbackFaultFlags(const BackendSystem &system)
  {
    return system.callback_fault_flags_.load();
  }

  static void CallUpdateHooks(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm)
  {
    gz::sim::UpdateInfo info;
    info.iterations = 1;
    info.simTime = std::chrono::milliseconds(10);
    system.PreUpdate(info, ecm);
    system.PostUpdate(info, ecm);
  }

  static bool Configured(const BackendSystem &system)
  {
    return system.configured_;
  }

  static void Shutdown(BackendSystem &system)
  {
    system.Shutdown();
  }

  static bool LocalOverride(const BackendSystem &system)
  {
    return system.local_zero_override_;
  }

  static std::uint32_t FaultFlags(const BackendSystem &system)
  {
    return system.fault_flags_;
  }

  static bool ObservationAuthorized(const BackendSystem &system)
  {
    return system.observation0_authorized_;
  }

  static std::uint64_t Revision(const BackendSystem &system)
  {
    return system.control_binding_revision_;
  }

  static std::size_t QueueSize(const BackendSystem &system)
  {
    return system.control_queue_.size();
  }

  static ControlResponse Cached(const BackendSystem &system, std::uint64_t seq)
  {
    return system.control_cache_.at(seq).response;
  }

  static std::uint64_t GateWatermark(const BackendSystem &system)
  {
    return system.gate_ ? system.gate_->Watermark() : 0;
  }

  static std::uint64_t ExpectedSafeStopSequence(
      const BackendSystem &system)
  {
    return system.gate_ ? system.gate_->ExpectedSafeStopSequence() : 0;
  }

  static GateResult ConsumeGateReceipt(
      BackendSystem &system, const ReceiptFacts &facts,
      std::int64_t ros_now_ns, std::int64_t steady_now_ns)
  {
    if (!system.gate_ ||
        !system.gate_->Enqueue(facts, steady_now_ns - 1))
      return {GateDisposition::Faulted, "test_receipt_enqueue_failed", {}, false};
    return system.gate_->ConsumeNext(ros_now_ns, steady_now_ns);
  }

  static ControlResponse Receive(
      BackendSystem &system, const ControlRequest &request)
  {
    ControlResponse response;
    system.OnBackendControl(request, response);
    return response;
  }

  static void ChangeRevision(BackendSystem &system, std::uint64_t revision)
  {
    system.control_binding_revision_ = revision;
  }

  static void PrepareProbe(BackendSystem &system)
  {
    system.probe_model_sdf_path_ =
        "/home/hazan/roadmap-b-b22-simulation-substrate/ros2_ws/src/"
        "ROBOT_URDF_final_description/models/b2_contact_probe/model.sdf";
    system.observed_engine_plugin_path_ = "/observed/physics-engine.so";
    system.proof_physics_engine_fingerprint_sha256_ = std::string(64, 'c');
  }

  static void InjectProbeTransport(
      BackendSystem &system,
      std::function<void(const ros_gz_interfaces::srv::SpawnEntity::Request &,
                         std::function<void(bool)>)> spawn,
      std::function<void(const ros_gz_interfaces::srv::SetEntityPose::Request &,
                         std::function<void(bool)>)> set_pose,
      std::function<void(const ros_gz_interfaces::srv::DeleteEntity::Request &,
                         std::function<void(bool)>)> remove)
  {
    system.probe_transport_.spawn_ready = [] { return true; };
    system.probe_transport_.pose_ready = [] { return true; };
    system.probe_transport_.remove_ready = [] { return true; };
    system.probe_transport_.spawn = std::move(spawn);
    system.probe_transport_.set_pose = std::move(set_pose);
    system.probe_transport_.remove = std::move(remove);
  }

  static void RequestSpawn(BackendSystem &system)
  {
    system.RequestProbeSpawn();
  }

  static void ProcessProbeResults(BackendSystem &system)
  {
    system.ProcessProbeServiceResults();
  }

  static ProbePhase CurrentProbePhase(const BackendSystem &system)
  {
    return system.probe_machine_.Phase();
  }

  static bool ProbeRunning(const BackendSystem &system)
  {
    return system.probe_machine_.Running();
  }

  static bool CapabilityVerified(const BackendSystem &system)
  {
    return system.contact_capability_verified_;
  }

  static bool PolicyOpen(const BackendSystem &system)
  {
    return system.policy_open_;
  }

  static std::int64_t ProbeDeadline(const BackendSystem &system)
  {
    return system.probe_machine_.DeadlineNs();
  }

  static bool SeedProbeEntities(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      bool put_contact_data_on_sensor = false)
  {
    sdf::Root root;
    if (!root.Load(system.probe_model_sdf_path_).empty() || !root.Model())
      return false;
    const auto *link_sdf = root.Model()->LinkByName("link");
    const auto *sensor_sdf = link_sdf ?
        link_sdf->SensorByName("contact_sensor") : nullptr;
    if (!sensor_sdf) return false;

    const auto world = ecm.CreateEntity();
    ecm.CreateComponent(world, gz::sim::components::Name("b2_training_arena"));
    ecm.CreateComponent(world, gz::sim::components::World());
    system.world_entity_ = world;
    system.world_name_ = "b2_training_arena";
    ecm.CreateComponent(world, gz::sim::components::PhysicsEnginePlugin(
        system.observed_engine_plugin_path_));

    const auto floor = ecm.CreateEntity();
    ecm.CreateComponent(floor, gz::sim::components::Name("floor_collision"));
    ecm.CreateComponent(floor, gz::sim::components::ParentEntity(world));
    ecm.CreateComponent(floor, gz::sim::components::Collision());
    system.floor_collision_entity_ = floor;

    const auto model = ecm.CreateEntity();
    ecm.CreateComponent(model, gz::sim::components::Name("b2_capability_probe"));
    ecm.CreateComponent(model, gz::sim::components::ParentEntity(world));
    ecm.CreateComponent(model, gz::sim::components::Model());
    ecm.CreateComponent(model, gz::sim::components::WorldPose(
        gz::math::Pose3d(0, 0, 0.07, 0, 0, 0)));
    const auto link = ecm.CreateEntity();
    ecm.CreateComponent(link, gz::sim::components::Name("link"));
    ecm.CreateComponent(link, gz::sim::components::ParentEntity(model));
    ecm.CreateComponent(link, gz::sim::components::Link());
    const auto collision = ecm.CreateEntity();
    ecm.CreateComponent(collision, gz::sim::components::Name("collision"));
    ecm.CreateComponent(collision, gz::sim::components::ParentEntity(link));
    ecm.CreateComponent(collision, gz::sim::components::Collision());
    const auto sensor = ecm.CreateEntity();
    ecm.CreateComponent(sensor, gz::sim::components::Name("contact_sensor"));
    ecm.CreateComponent(sensor, gz::sim::components::ParentEntity(link));
    ecm.CreateComponent(sensor, gz::sim::components::Sensor());
    ecm.CreateComponent(sensor, gz::sim::components::ContactSensor(
        sensor_sdf->Element()));
    const auto data_entity = put_contact_data_on_sensor ? sensor : collision;
    ecm.CreateComponent(data_entity,
        gz::sim::components::ContactSensorData(gz::msgs::Contacts()));
    system.probe_sensor_entity_ = sensor;
    system.collision_entity_names_[floor] =
        "b2_training_arena::floor_collision";
    return true;
  }

  static void SetProbeContact(
      gz::sim::EntityComponentManager &ecm, std::uint64_t data_entity,
      std::uint64_t fixture_collision, std::uint64_t floor_collision,
      bool touching, bool include_normal_depth = true)
  {
    gz::msgs::Contacts contacts;
    if (touching)
    {
      auto *contact = contacts.add_contact();
      contact->mutable_collision1()->set_id(fixture_collision);
      contact->mutable_collision2()->set_id(floor_collision);
      if (include_normal_depth)
      {
        auto *normal = contact->add_normal();
        normal->set_z(1.0);
        contact->add_depth(0.001);
      }
    }
    ecm.SetComponentData<gz::sim::components::ContactSensorData>(
        data_entity, contacts);
  }

  static ContactSample BuildRegisteredCollisionSample(
      BackendSystem &system, const gz::sim::EntityComponentManager &ecm,
      std::uint64_t collision, std::uint64_t iteration)
  {
    const std::string name =
        "b2_training_arena::b2_capability_probe::link::collision";
    system.collision_bits_[name] = 1;
    system.collision_entity_names_[collision] = name;
    system.collision_contact_bits_[collision] = 1;
    gz::sim::UpdateInfo info;
    info.iterations = iteration;
    info.simTime = std::chrono::milliseconds(iteration * 10);
    return system.BuildContactSample(info, ecm);
  }

  static std::uint64_t ProbeSensor(const BackendSystem &system)
  {
    return system.probe_sensor_entity_;
  }

  static std::uint64_t ProbeCollision(const BackendSystem &system)
  {
    return system.probe_machine_.CollisionEntity();
  }

  static std::uint64_t ProbeFloor(const BackendSystem &system)
  {
    return system.floor_collision_entity_;
  }

  static void ObserveProbe(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      std::uint64_t iteration, std::int64_t sim_ns, bool paused = false)
  {
    gz::sim::UpdateInfo info;
    info.iterations = iteration;
    info.simTime = std::chrono::nanoseconds(sim_ns);
    info.paused = paused;
    system.ObserveContactProbe(info, ecm, sim_ns);
  }

  static void AdvanceProbe(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm,
      std::uint64_t iteration, std::int64_t sim_ns,
      std::int64_t steady_ns)
  {
    gz::sim::UpdateInfo info;
    info.iterations = iteration;
    info.simTime = std::chrono::nanoseconds(sim_ns);
    system.AdvanceContactProbe(info, ecm, steady_ns);
  }

  static bool ResolveProbeFixture(
      BackendSystem &system, gz::sim::EntityComponentManager &ecm)
  {
    return system.ResolveProbeFixture(ecm);
  }

  static void SetProbePose(
      gz::sim::EntityComponentManager &ecm, std::uint64_t model,
      double z)
  {
    ecm.SetComponentData<gz::sim::components::WorldPose>(
        model, gz::math::Pose3d(0, 0, z, 0, 0, 0));
  }

  static void RemoveProbeEntities(
      gz::sim::EntityComponentManager &ecm, std::uint64_t model,
      std::uint64_t link, std::uint64_t collision, std::uint64_t sensor)
  {
    ecm.RequestRemoveEntity(sensor);
    ecm.RequestRemoveEntity(collision);
    ecm.RequestRemoveEntity(link);
    ecm.RequestRemoveEntity(model);
    ecm.ProcessRemoveEntityRequests();
  }

  static std::uint64_t ProbeModel(const BackendSystem &system)
  {
    return system.probe_machine_.ModelEntity();
  }

  static std::string NamedProbeScope(
      const gz::sim::EntityComponentManager &ecm)
  {
    const auto model = ecm.EntityByComponents(
        gz::sim::components::Name("b2_capability_probe"),
        gz::sim::components::Model());
    return model == gz::sim::kNullEntity ? "<missing>" :
        gz::sim::scopedName(model, ecm, "::", false);
  }

  static gz::sim::Entity ProbeWorld(const BackendSystem &system)
  {
    return system.world_entity_;
  }

  static std::size_t ProbeModelCount(
      const gz::sim::EntityComponentManager &ecm)
  {
    return ecm.EntitiesByComponents(
        gz::sim::components::Name("b2_capability_probe"),
        gz::sim::components::Model()).size();
  }

  static bool IsProbeInBoundWorld(
      const BackendSystem &system,
      const gz::sim::EntityComponentManager &ecm)
  {
    const auto model = ecm.EntityByComponents(
        gz::sim::components::Name("b2_capability_probe"),
        gz::sim::components::Model());
    return system.IsInBoundWorld(model, ecm);
  }

  static void SetCapabilityPrerequisites(BackendSystem &system)
  {
    system.observed_engine_plugin_path_ = "/observed/physics-engine.so";
    system.proof_physics_engine_fingerprint_sha256_ = std::string(64, 'c');
  }
};
}  // namespace mecanum_sim_backend

namespace
{
void SetStamp(builtin_interfaces::msg::Time &stamp, std::int64_t ns)
{
  stamp.sec = static_cast<std::int32_t>(ns / 1'000'000'000LL);
  stamp.nanosec = static_cast<std::uint32_t>(ns % 1'000'000'000LL);
}

ControlRequest BaseControlRequest(std::uint64_t sequence)
{
  ControlRequest request;
  request.schema_version = ControlRequest::SCHEMA_VERSION;
  request.coordinator_ingress_instance_id = 7;
  request.request_sequence = sequence;
  request.expected_binding_revision = 0;
  request.expected_backend_instance_id = 8;
  request.session_id = "test-session";
  request.config_hash = std::string(64, 'a');
  request.asset_manifest_sha256 = std::string(64, 'b');
  return request;
}

ControlRequest BindSessionRequest()
{
  auto request = BaseControlRequest(1);
  request.operation = ControlRequest::OP_BIND_SESSION;
  request.episode_generation = 2;
  request.reset_epoch = 3;
  request.runtime_generation = 4;
  request.lifecycle_sequence = 1;
  request.primary_state = ControlRequest::PRIMARY_ACTIVE;
  request.barrier_state = ControlRequest::BARRIER_READY;
  SetStamp(request.lifecycle_header_stamp, 100);
  request.lifecycle_frame_id = "b2_training_arena";
  SetStamp(request.barrier_stamp, 90);
  request.final_publisher_instance_id = 11;
  request.policy_source_instance_id = 22;
  request.safe_stop_source_instance_id = 33;
  request.next_safe_stop_sequence = 1;
  return request;
}

bool BindThroughProductionReceiver(BackendSystem &system,
                                   gz::sim::EntityComponentManager &ecm)
{
  const auto response = BackendSystemTestPeer::Receive(
      system, BindSessionRequest());
  if (response.result != ControlResponse::RESULT_QUEUED) return false;
  BackendSystemTestPeer::Tick(system, ecm);
  return BackendSystemTestPeer::Cached(system, 1).result ==
      ControlResponse::RESULT_APPLIED;
}

ControlRequest Observation0Request(std::uint64_t sequence = 2)
{
  auto request = BaseControlRequest(sequence);
  request.operation = ControlRequest::OP_CONFIRM_OBSERVATION0;
  request.expected_binding_revision = 1;
  request.episode_generation = 2;
  request.reset_epoch = 3;
  request.runtime_generation = 4;
  request.lifecycle_sequence = 1;
  request.primary_state = ControlRequest::PRIMARY_ACTIVE;
  request.barrier_state = ControlRequest::BARRIER_READY;
  SetStamp(request.lifecycle_header_stamp, 100);
  request.lifecycle_frame_id = "b2_training_arena";
  SetStamp(request.barrier_stamp, 90);
  SetStamp(request.observation0_cutoff, 145);
  request.selected_zero_final_publisher_instance_id = 11;
  request.selected_zero_final_publish_sequence = 41;
  request.adjacent_boundary_final_publisher_instance_id = 11;
  request.adjacent_boundary_final_publish_sequence = 42;
  return request;
}

ControlRequest ResetContextRequest()
{
  auto request = BaseControlRequest(2);
  request.operation = ControlRequest::OP_BIND_RESET_CONTEXT;
  request.expected_binding_revision = 1;
  request.episode_generation = 3;
  request.reset_epoch = 4;
  request.runtime_generation = 4;
  request.lifecycle_sequence = 2;
  request.primary_state = ControlRequest::PRIMARY_ACTIVE;
  request.barrier_state = ControlRequest::BARRIER_READY;
  SetStamp(request.lifecycle_header_stamp, 120);
  request.lifecycle_frame_id = "b2_training_arena";
  SetStamp(request.barrier_stamp, 110);
  request.final_publisher_instance_id = 11;
  request.policy_source_instance_id = 22;
  request.safe_stop_source_instance_id = 33;
  request.next_safe_stop_sequence = 2;
  return request;
}

ControlRequest ProbeStartRequest()
{
  auto request = BaseControlRequest(2);
  request.operation = ControlRequest::OP_VERIFY_CONTACT_CAPABILITY;
  request.probe_action = ControlRequest::PROBE_ACTION_START;
  request.expected_binding_revision = 1;
  request.episode_generation = 2;
  request.reset_epoch = 3;
  request.runtime_generation = 4;
  request.lifecycle_sequence = 1;
  request.primary_state = ControlRequest::PRIMARY_ACTIVE;
  request.barrier_state = ControlRequest::BARRIER_READY;
  SetStamp(request.lifecycle_header_stamp, 100);
  request.lifecycle_frame_id = "b2_training_arena";
  SetStamp(request.barrier_stamp, 90);
  return request;
}

void BindTestRequestToConfiguredBackend(
    ControlRequest &request, const BackendSystem &system)
{
  request.expected_backend_instance_id =
      BackendSystemTestPeer::BackendInstance(system);
  request.session_id = "native-reset-chain";
  request.config_hash = std::string(64, 'a');
  request.asset_manifest_sha256 = std::string(64, 'b');
}

Receipt SafeStopReceipt(
    std::uint64_t publication_sequence, std::uint64_t source_sequence,
    std::uint64_t episode, std::uint32_t reset_epoch,
    std::int64_t stamp_ns)
{
  Receipt receipt;
  receipt.header.frame_id = "base_link";
  SetStamp(receipt.header.stamp, stamp_ns);
  receipt.final_publisher_instance_id = 11;
  receipt.final_publish_sequence = publication_sequence;
  receipt.episode_generation = episode;
  receipt.reset_epoch = reset_epoch;
  receipt.runtime_generation = 4;
  receipt.source = Receipt::SOURCE_SAFE_STOP;
  receipt.sequence = source_sequence;
  receipt.source_instance_id = 33;
  return receipt;
}
}  // namespace

TEST(BackendInvariants, BodyFrameConversionPreservesVyAndMeasuredVerticalComponents)
{
  const double h=0.7071067811865476;
  MeasuredWorldTwist3D measured{{0,1,0.2},{0.1,0.2,0.3}}; std::string reason;
  auto body=ComposeBodyPlanarCommand(measured,{0,0,h,h},0.2,-0.1,0.4,reason);
  ASSERT_TRUE(body.has_value()) << reason;
  EXPECT_NEAR(body->linear[0],0.2,1e-12); EXPECT_NEAR(body->linear[1],-0.1,1e-12);
  EXPECT_NEAR(body->linear[2],0.2,1e-12); EXPECT_NEAR(body->angular[0],0.2,1e-12);
  EXPECT_NEAR(body->angular[1],-0.1,1e-12); EXPECT_NEAR(body->angular[2],0.4,1e-12);
}

TEST(BackendInvariants, ConvertsYawPlusMinusNinetyWithoutDoubleRotation)
{
  std::string reason; MeasuredWorldTwist3D m{{0,1,0},{0,0,0}};
  auto positive=ComposeBodyPlanarCommand(m,{0,0,0.7071067811865476,0.7071067811865476},0.25,-0.20,0.80,reason);
  ASSERT_TRUE(positive); EXPECT_DOUBLE_EQ(positive->linear[0],0.25); EXPECT_DOUBLE_EQ(positive->linear[1],-0.20);
  auto negative=ComposeBodyPlanarCommand(m,{0,0,-0.7071067811865476,0.7071067811865476},0.25,-0.20,0.80,reason);
  ASSERT_TRUE(negative); EXPECT_DOUBLE_EQ(negative->linear[0],0.25); EXPECT_DOUBLE_EQ(negative->linear[1],-0.20);
}

TEST(BackendInvariants, RollPitchOrientationAndMissingMeasurementFailClosed)
{
  std::string reason; MeasuredWorldTwist3D m{{0.2,0.3,0.4},{0.1,0.2,0.3}};
  auto body=ComposeBodyPlanarCommand(m,{0.2,0.3,0.1,0.9},0.25,0.2,0.8,reason);
  ASSERT_TRUE(body); EXPECT_DOUBLE_EQ(body->linear[0],0.25); EXPECT_DOUBLE_EQ(body->linear[1],0.2);
  m.linear[2]=std::numeric_limits<double>::quiet_NaN();
  EXPECT_FALSE(ComposeBodyPlanarCommand(m,{0,0,0,1},0.1,0.1,0.1,reason));
  EXPECT_EQ(reason,"missing_or_non_finite_linear_measurement");
}

TEST(BackendInvariants, ZeroCommandIsNotAZeroMeasurement)
{
  MeasuredWorldTwist3D missing{{NAN,0,0},{0,0,0}}; std::string reason;
  EXPECT_FALSE(ComposeBodyPlanarCommand(missing,{0,0,0,1},0,0,0,reason));
}

TEST(BackendInvariants, ContactPairsUseCollisionEntityIdsAndExactFloorPair)
{
  const std::unordered_map<std::uint64_t, std::string> tracked{
      {11, "world::mecanum_b2::Wheel_LF_1::wheel_collision"},
      {12, "world::mecanum_b2::base_link::chassis_collision"},
  };
  const std::unordered_set<std::string> wheel_floor{
      "world::mecanum_b2::Wheel_LF_1::wheel_collision",
  };
  const auto wheel = ClassifyContactPair(11, 99, 99, tracked, wheel_floor);
  EXPECT_TRUE(wheel.tracked);
  EXPECT_TRUE(wheel.exact_floor_pair);
  EXPECT_TRUE(wheel.wheel_floor_ignore);
  const auto chassis = ClassifyContactPair(12, 99, 99, tracked, wheel_floor);
  EXPECT_TRUE(chassis.tracked);
  EXPECT_TRUE(chassis.exact_floor_pair);
  EXPECT_FALSE(chassis.wheel_floor_ignore);
  const auto other_floor = ClassifyContactPair(11, 98, 99, tracked, wheel_floor);
  EXPECT_TRUE(other_floor.tracked);
  EXPECT_FALSE(other_floor.exact_floor_pair);
  EXPECT_FALSE(other_floor.wheel_floor_ignore);
  EXPECT_FALSE(ClassifyContactPair(98, 97, 99, tracked, wheel_floor).tracked);
}

TEST(BackendInvariants, ServerSceneRequiresOneExpectedRobotInExpectedWorld)
{
  EXPECT_TRUE(IsUniqueWorldModel(10, 1, {{10, 1}}));
  EXPECT_FALSE(IsUniqueWorldModel(10, 1, {}));
  EXPECT_FALSE(IsUniqueWorldModel(10, 1, {{10, 1}, {11, 1}}));
  EXPECT_FALSE(IsUniqueWorldModel(10, 2, {{10, 1}}));
  EXPECT_FALSE(IsUniqueWorldModel(0, 1, {{10, 1}}));
}

TEST(BackendSystemLifecycle, MissingModelAndEarlyCallbackRemainInhibited)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::ConfigureMissingModel(system, ecm);
  EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
  EXPECT_NE(BackendSystemTestPeer::FaultFlags(system), 0u);

  Receipt receipt;
  BackendSystemTestPeer::EarlyReceipt(system, receipt);
  BackendSystemTestPeer::CallUpdateHooks(system, ecm);
  EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
  EXPECT_TRUE(BackendSystemTestPeer::LocalOverride(system));
  EXPECT_NE(BackendSystemTestPeer::FaultFlags(system), 0u);
}

TEST(BackendSystemLifecycle, MissingWorldAndLinkStayInhibitedAcrossHooks)
{
  for (const bool create_world : {false, true})
  {
    BackendSystem system;
    gz::sim::EntityComponentManager ecm;
    ASSERT_TRUE(BackendSystemTestPeer::ConfigureInvalidModel(
        system, ecm, create_world));
    EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
    EXPECT_NE(BackendSystemTestPeer::FaultFlags(system), 0u);
    Receipt receipt;
    BackendSystemTestPeer::EarlyReceipt(system, receipt);
    BackendSystemTestPeer::CallUpdateHooks(system, ecm);
    BackendSystemTestPeer::CallUpdateHooks(system, ecm);
    EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
    EXPECT_TRUE(BackendSystemTestPeer::LocalOverride(system));
    EXPECT_NE(BackendSystemTestPeer::FaultFlags(system), 0u);
    BackendSystemTestPeer::Shutdown(system);
    BackendSystemTestPeer::Shutdown(system);
    BackendSystemTestPeer::CallUpdateHooks(system, ecm);
    EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
    EXPECT_TRUE(BackendSystemTestPeer::LocalOverride(system));
  }
}

TEST(BackendSystemLifecycle, NativeResourceFactoryFailureRollsBackExactlyOnce)
{
  for (std::size_t fail_after = 1; fail_after <= 15; ++fail_after)
  {
    BackendSystem system;
    gz::sim::EntityComponentManager ecm;
    const auto counters = std::make_shared<NativeFactoryCounters>();
    ASSERT_TRUE(BackendSystemTestPeer::ConfigureWithInjectedRuntimeFailure(
        system, ecm, counters, fail_after));

    EXPECT_EQ(counters->contact_created, 1u);
    EXPECT_EQ(counters->runtime_boundary_calls, 1u);
    EXPECT_EQ(counters->context_created, 1u);
    EXPECT_EQ(counters->context_released, 1u);
    EXPECT_EQ(BackendSystemTestPeer::FaultFlags(system),
              static_cast<std::uint32_t>(BackendState::FAULT_CONTEXT |
                                         BackendState::FAULT_CONTACT_COVERAGE));
    EXPECT_FALSE(BackendSystemTestPeer::Configured(system));

    std::uint32_t created = 0;
    std::uint32_t released = 0;
    for (std::size_t index = 0; index < 15; ++index)
    {
      const auto expected = index < fail_after ? 1u : 0u;
      EXPECT_EQ(counters->runtime_created[index], expected);
      EXPECT_EQ(counters->runtime_released[index], expected);
      created += counters->runtime_created[index];
      released += counters->runtime_released[index];
    }
    EXPECT_EQ(created, fail_after);
    EXPECT_EQ(released, fail_after);
    EXPECT_EQ(counters->context_created, 1u);
    EXPECT_EQ(counters->context_released, 1u);
    EXPECT_EQ(counters->contact_released, 1u);

    Receipt early_receipt;
    BackendSystemTestPeer::EarlyReceipt(system, early_receipt);
    EXPECT_EQ(BackendSystemTestPeer::CallbackFaultFlags(system), 0u);
    BackendSystemTestPeer::CallUpdateHooks(system, ecm);
    EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
    EXPECT_TRUE(BackendSystemTestPeer::LocalOverride(system));
    EXPECT_EQ(counters->actuator_calls, 0u);
    EXPECT_EQ(counters->backend_state_calls, 0u);
    EXPECT_EQ(counters->ground_truth_calls, 0u);

    BackendSystemTestPeer::Shutdown(system);
    EXPECT_EQ(counters->contact_released, 1u);
    for (std::size_t index = 0; index < 15; ++index)
      EXPECT_EQ(counters->runtime_released[index], index < fail_after ? 1u : 0u);
    BackendSystemTestPeer::Shutdown(system);
    BackendSystemTestPeer::CallUpdateHooks(system, ecm);
    EXPECT_EQ(counters->contact_released, 1u);
    for (std::size_t index = 0; index < 15; ++index)
      EXPECT_EQ(counters->runtime_released[index], index < fail_after ? 1u : 0u);
    EXPECT_FALSE(BackendSystemTestPeer::Configured(system));
    EXPECT_TRUE(BackendSystemTestPeer::LocalOverride(system));
    EXPECT_EQ(counters->actuator_calls, 0u);
    EXPECT_EQ(counters->backend_state_calls, 0u);
    EXPECT_EQ(counters->ground_truth_calls, 0u);
  }
}

static void RunNativeResetObservation0Chain(
    bool mismatch_confirmation_context, bool missing_measurement_on_apply,
    bool reset_between_application_and_confirmation = false,
    bool inhibit_before_confirmation_apply = false,
    bool contact_gap_after_application = false)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  const auto io = std::make_shared<NativeResetChainIo>();
  ASSERT_TRUE(BackendSystemTestPeer::ConfigureForNativeResetChain(
      system, ecm, io));

  auto bind = BindSessionRequest();
  BindTestRequestToConfiguredBackend(bind, system);
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, bind).result,
            ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 1, 200'000'000);
  ASSERT_EQ(BackendSystemTestPeer::Cached(system, 1).result,
            ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(BackendSystemTestPeer::Revision(system), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));

  auto start = ProbeStartRequest();
  BindTestRequestToConfiguredBackend(start, system);
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, start).result,
            ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 2, 210'000'000);
  ASSERT_EQ(BackendSystemTestPeer::Cached(system, 2).result,
            ControlResponse::RESULT_APPLIED)
      << "reason=" << BackendSystemTestPeer::Cached(system, 2).reason_code;
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  ASSERT_EQ(io->spawn_calls, 1u);

  ASSERT_TRUE(BackendSystemTestPeer::AddProbeFixture(
      ecm, BackendSystemTestPeer::WorldEntity(system)));
  const auto probe_collision = gz::sim::entitiesFromScopedName(
      "b2_training_arena::b2_capability_probe::link::collision", ecm);
  const auto floor_collision = gz::sim::entitiesFromScopedName(
      "b2_training_arena::ground_plane::link::collision", ecm);
  ASSERT_EQ(probe_collision.size(), 1u);
  ASSERT_EQ(floor_collision.size(), 1u);
  for (std::uint64_t iteration = 3; iteration <= 5; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(
        ecm, *probe_collision.begin(), *probe_collision.begin(),
        *floor_collision.begin(), true);
    BackendSystemTestPeer::RunProductionTick(
        system, ecm, iteration, 210'000'000 +
            static_cast<std::int64_t>(iteration - 1) * 10'000'000);
    EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
    EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  }
  ASSERT_EQ(io->lift_calls, 0u);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 6, 260'000'000);
  EXPECT_EQ(io->lift_calls, 1u);
  BackendSystemTestPeer::SetProbePose(
      ecm, *ecm.EntitiesByComponents(
          gz::sim::components::Name("b2_capability_probe"),
          gz::sim::components::Model()).begin(), 0.20);
  BackendSystemTestPeer::SetProbeContact(
      ecm, *probe_collision.begin(), *probe_collision.begin(),
      *floor_collision.begin(), false);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 7, 270'000'000);
  for (std::uint64_t iteration = 8; iteration <= 10; ++iteration)
    BackendSystemTestPeer::RunProductionTick(
        system, ecm, iteration, 270'000'000 +
            static_cast<std::int64_t>(iteration - 7) * 10'000'000);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));

  BackendSystemTestPeer::RunProductionTick(system, ecm, 11, 310'000'000);
  ASSERT_EQ(io->remove_calls, 1u);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  BackendSystemTestPeer::RemoveProbeFixture(ecm);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 12, 320'000'000);
  ASSERT_TRUE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  EXPECT_EQ(io->spawn_calls, 1u);
  EXPECT_EQ(io->lift_calls, 1u);
  EXPECT_EQ(io->remove_calls, 1u);

  auto query = BaseControlRequest(3);
  BindTestRequestToConfiguredBackend(query, system);
  query.operation = ControlRequest::OP_VERIFY_CONTACT_CAPABILITY;
  query.probe_action = ControlRequest::PROBE_ACTION_QUERY;
  query.expected_binding_revision = 1;
  query.probe_start_request_sequence = 2;
  const auto queued_query = BackendSystemTestPeer::Receive(system, query);
  ASSERT_EQ(queued_query.result, ControlResponse::RESULT_QUEUED)
      << "reason=" << queued_query.reason_code
      << " revision=" << queued_query.binding_revision
      << " cached_start=" << BackendSystemTestPeer::Cached(system, 2).result
      << " capability=" << BackendSystemTestPeer::CapabilityVerified(system);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 13, 330'000'000);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 3).result,
            ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 3).contact_capability_state,
            ControlResponse::CAPABILITY_VERIFIED);
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));

  for (std::uint64_t iteration = 14; iteration <= 16; ++iteration)
    BackendSystemTestPeer::RunProductionTick(
        system, ecm, iteration, 330'000'000 +
            static_cast<std::int64_t>(iteration - 13) * 10'000'000);

  auto reset = ResetContextRequest();
  BindTestRequestToConfiguredBackend(reset, system);
  reset.request_sequence = 4;
  reset.expected_binding_revision = 1;
  reset.next_safe_stop_sequence = 1;
  reset.episode_generation = 3;
  reset.reset_epoch = 4;
  reset.runtime_generation = 4;
  reset.lifecycle_sequence = 2;
  SetStamp(reset.lifecycle_header_stamp, 370'000'000);
  SetStamp(reset.barrier_stamp, 360'000'000);
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, reset).result,
            ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::RunProductionTick(system, ecm, 17, 380'000'000);
  ASSERT_EQ(BackendSystemTestPeer::Cached(system, 4).result,
            ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(BackendSystemTestPeer::Revision(system), 2u);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));

  if (missing_measurement_on_apply)
    BackendSystemTestPeer::RemoveBaseLinkVelocityComponents(ecm);
  BackendSystemTestPeer::EarlyReceipt(
      system, SafeStopReceipt(1, 1, 3, 4, 361'000'000));
  BackendSystemTestPeer::RunProductionTick(system, ecm, 18, 390'000'000);
  EXPECT_GT(io->actuator_calls, 0u);
  const auto selected_application =
      BackendSystemTestPeer::ApplicationHistory(system);
  ASSERT_EQ(selected_application.size(), missing_measurement_on_apply ? 0u : 1u);
  if (!missing_measurement_on_apply)
  {
    EXPECT_EQ(selected_application.front().publisher_instance_id, 11u);
    EXPECT_EQ(selected_application.front().publish_sequence, 1u);
    EXPECT_TRUE(selected_application.front().receipt_valid);
    EXPECT_FALSE(selected_application.front().local_zero_override);
  }
  EXPECT_EQ(io->ground_truth_calls, missing_measurement_on_apply ? 17u : 18u);
  EXPECT_EQ(io->backend_state_calls, 18u);
  EXPECT_EQ(BackendSystemTestPeer::MeasurementHealthy(system),
            !missing_measurement_on_apply);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));

  if (contact_gap_after_application)
    BackendSystemTestPeer::RemoveOneRegisteredContactComponent(system, ecm);
  if (reset_between_application_and_confirmation)
  {
    auto next_reset = ResetContextRequest();
    BindTestRequestToConfiguredBackend(next_reset, system);
    next_reset.request_sequence = 5;
    next_reset.expected_binding_revision = 2;
    next_reset.next_safe_stop_sequence = 2;
    next_reset.episode_generation = 4;
    next_reset.reset_epoch = 5;
    next_reset.lifecycle_sequence = 3;
    SetStamp(next_reset.lifecycle_header_stamp, 400'000'000);
    SetStamp(next_reset.barrier_stamp, 395'000'000);
    ASSERT_EQ(BackendSystemTestPeer::Receive(system, next_reset).result,
              ControlResponse::RESULT_QUEUED);
    BackendSystemTestPeer::RunProductionTick(system, ecm, 19, 400'000'000);
    ASSERT_EQ(BackendSystemTestPeer::Cached(system, 5).result,
              ControlResponse::RESULT_APPLIED);
    EXPECT_EQ(BackendSystemTestPeer::Revision(system), 3u);
    EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
    BackendSystemTestPeer::EarlyReceipt(
        system, SafeStopReceipt(2, 2, 3, 4, 410'000'000));
    BackendSystemTestPeer::RunProductionTick(system, ecm, 20, 420'000'000);
  }
  else
  {
    BackendSystemTestPeer::RunProductionTick(system, ecm, 19, 400'000'000);
    BackendSystemTestPeer::EarlyReceipt(
        system, SafeStopReceipt(2, 2, 3, 4, 410'000'000));
    BackendSystemTestPeer::RunProductionTick(system, ecm, 20, 420'000'000);
  }

  auto confirm = Observation0Request(
      reset_between_application_and_confirmation ? 6 : 5);
  BindTestRequestToConfiguredBackend(confirm, system);
  confirm.expected_binding_revision =
      reset_between_application_and_confirmation ? 3 : 2;
  confirm.episode_generation = 3;
  confirm.reset_epoch = mismatch_confirmation_context ? 5 : 4;
  confirm.runtime_generation = 4;
  confirm.lifecycle_sequence = 2;
  SetStamp(confirm.lifecycle_header_stamp, 370'000'000);
  SetStamp(confirm.barrier_stamp, 360'000'000);
  SetStamp(confirm.observation0_cutoff, 400'000'000);
  confirm.selected_zero_final_publish_sequence = 1;
  confirm.adjacent_boundary_final_publish_sequence = 2;
  const auto confirm_queued = BackendSystemTestPeer::Receive(system, confirm);
  ASSERT_EQ(confirm_queued.result,
            ControlResponse::RESULT_QUEUED);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
  if (inhibit_before_confirmation_apply)
  {
    auto inhibit = BaseControlRequest(6);
    inhibit.operation = ControlRequest::OP_INHIBIT;
    BindTestRequestToConfiguredBackend(inhibit, system);
    const auto inhibit_queued = BackendSystemTestPeer::Receive(system, inhibit);
    ASSERT_EQ(inhibit_queued.result, ControlResponse::RESULT_QUEUED);
  }
  BackendSystemTestPeer::RunProductionTick(system, ecm, 21, 430'000'000);
  const auto confirm_sequence =
      reset_between_application_and_confirmation ? 6u : 5u;
  const auto applied = BackendSystemTestPeer::Cached(system, confirm_sequence);
  if (inhibit_before_confirmation_apply)
  {
    EXPECT_EQ(applied.result, ControlResponse::RESULT_REJECTED);
    EXPECT_EQ(applied.reason_code, ControlResponse::REASON_CANCELLED);
    EXPECT_EQ(BackendSystemTestPeer::Cached(system, 6).result,
              ControlResponse::RESULT_APPLIED);
    EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
    EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
    EXPECT_EQ(BackendSystemTestPeer::Revision(system), 3u);
    return;
  }
  const bool reject_confirmation = mismatch_confirmation_context ||
      missing_measurement_on_apply || reset_between_application_and_confirmation ||
      contact_gap_after_application;
  EXPECT_EQ(applied.result, reject_confirmation ?
      ControlResponse::RESULT_REJECTED : ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(applied.reason_code, reject_confirmation ?
      ControlResponse::REASON_OBSERVATION0_PROOF_MISMATCH :
      ControlResponse::REASON_NONE);
  EXPECT_EQ(applied.applied_binding_revision,
      reject_confirmation ? 0u : 3u);
  EXPECT_EQ(BackendSystemTestPeer::Revision(system),
      reset_between_application_and_confirmation ? 3u :
      reject_confirmation ? 2u : 3u);
  EXPECT_EQ(BackendSystemTestPeer::ObservationAuthorized(system),
      !reject_confirmation);
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  const auto final_applications =
      BackendSystemTestPeer::ApplicationHistory(system);
  ASSERT_EQ(final_applications.size(), missing_measurement_on_apply ? 0u :
      (reset_between_application_and_confirmation || contact_gap_after_application) ?
          1u : 2u);
  if (!missing_measurement_on_apply)
  {
    EXPECT_EQ(final_applications[0].publish_sequence, 1u);
    if (!reset_between_application_and_confirmation &&
        !contact_gap_after_application)
      EXPECT_EQ(final_applications[1].publish_sequence, 2u);
  }
}

TEST(BackendSystemControlReceiver, NativeResetObservation0ChainUsesProductionFacts)
{
  RunNativeResetObservation0Chain(false, false);
}

TEST(BackendSystemControlReceiver,
     NativeResetObservation0ChainRejectsConfirmationContextMismatch)
{
  RunNativeResetObservation0Chain(true, false);
}

TEST(BackendSystemControlReceiver,
     NativeResetObservation0ChainRejectsReceiptWithoutMeasurementApplication)
{
  RunNativeResetObservation0Chain(false, true);
}

TEST(BackendSystemControlReceiver,
     NativeResetObservation0ChainRejectsAfterNewResetContext)
{
  RunNativeResetObservation0Chain(false, false, true);
}

TEST(BackendSystemControlReceiver,
     NativeResetObservation0ChainInhibitCancelsQueuedConfirmation)
{
  RunNativeResetObservation0Chain(false, false, false, true);
}

TEST(BackendSystemControlReceiver,
     NativeResetObservation0ChainRejectsContactCoverageGap)
{
  RunNativeResetObservation0Chain(false, false, false, false, true);
}

TEST(BackendInvariants, ResetContextMustAdvanceWithoutRewindingIdentity)
{
  EXPECT_TRUE(IsForwardResetContext(5, 6, 100, 101, 2, 3, 4, 4, 7, 7, 9, 9));
  EXPECT_FALSE(IsForwardResetContext(5, 5, 100, 101, 2, 3, 4, 4, 7, 7, 9, 9));
  EXPECT_FALSE(IsForwardResetContext(5, 6, 100, 100, 2, 3, 4, 4, 7, 7, 9, 9));
  EXPECT_FALSE(IsForwardResetContext(5, 6, 100, 101, 2, 1, 4, 5, 7, 7, 9, 9));
  EXPECT_FALSE(IsForwardResetContext(5, 6, 100, 101, 2, 3, 4, 4, 7, 7, 9, 10));
}

TEST(BackendSystemControlReceiver, ResetContextKeepsPublicationWatermark)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));

  ReceiptFacts first_anchor;
  first_anchor.session_id = "test-session";
  first_anchor.config_hash = std::string(64, 'a');
  first_anchor.key = {11, 1};
  first_anchor.episode_generation = 2;
  first_anchor.reset_epoch = 3;
  first_anchor.runtime_generation = 4;
  first_anchor.source = Receipt::SOURCE_SAFE_STOP;
  first_anchor.sequence = 1;
  first_anchor.source_instance_id = 33;
  first_anchor.stamp_ns = 101;
  first_anchor.frame_id = "base_link";
  EXPECT_EQ(BackendSystemTestPeer::ConsumeGateReceipt(
      system, first_anchor, 110, 10).disposition,
      GateDisposition::Anchored);
  ASSERT_EQ(BackendSystemTestPeer::GateWatermark(system), 1u);

  const auto request = ResetContextRequest();
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, request).result,
            ControlResponse::RESULT_QUEUED);
  EXPECT_EQ(BackendSystemTestPeer::GateWatermark(system), 1u);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  const auto applied = BackendSystemTestPeer::Cached(system, 2);
  EXPECT_EQ(applied.result, ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(applied.applied_binding_revision, 2u);
  EXPECT_EQ(BackendSystemTestPeer::GateWatermark(system), 1u);
  EXPECT_EQ(BackendSystemTestPeer::ExpectedSafeStopSequence(system), 2u);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));

  auto old_context_receipt = first_anchor;
  old_context_receipt.key.publish_sequence = 2;
  old_context_receipt.sequence = 2;
  EXPECT_EQ(BackendSystemTestPeer::ConsumeGateReceipt(
      system, old_context_receipt, 130, 20).disposition,
      GateDisposition::Faulted);
  EXPECT_EQ(BackendSystemTestPeer::GateWatermark(system), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
}

TEST(BackendInvariants, Observation0RequiresSelectedAppliedZeroAndAdjacentBoundary)
{
  ReceiptFacts selected;
  selected.session_id = "run";
  selected.config_hash = std::string(64, 'a');
  selected.key = {17, 41};
  selected.episode_generation = 3;
  selected.reset_epoch = 2;
  selected.runtime_generation = 5;
  selected.source = 4;
  selected.sequence = 9;
  selected.source_instance_id = 29;
  selected.stamp_ns = 120;
  selected.frame_id = "base_link";
  selected.twist = {0, 0, 0, 0, 0, 0};

  ReceiptFacts adjacent = selected;
  adjacent.key.publish_sequence = 42;
  adjacent.source = 1;
  adjacent.sequence = 8;
  adjacent.step_index = 8;
  adjacent.transition_id = "next-policy-transition";
  adjacent.source_instance_id = 31;
  adjacent.stamp_ns = 151;
  adjacent.twist = {0.1, 0.0, 0, 0, 0, 0};

  const std::vector<ReceiptFacts> publications{selected, adjacent};
  const std::vector<AppliedReceiptFact> applications{{17, 41, 12, 130, true, false}};
  const std::vector<ContactHistoryFact> contacts{
      {12, 130, true, true, false}, {13, 140, true, true, false},
      {14, 150, true, true, true}};
  const auto valid = ValidateObservation0Proof(
      publications, applications, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155);
  EXPECT_TRUE(valid.valid) << valid.reason;

  const auto wrong_adjacent = ValidateObservation0Proof(
      publications, applications, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 43, 145, 155);
  EXPECT_FALSE(wrong_adjacent.valid);
  const auto missing_application = ValidateObservation0Proof(
      publications, {}, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155);
  EXPECT_FALSE(missing_application.valid);
  auto foreign_session = publications;
  foreign_session[0].session_id = "other-run";
  EXPECT_FALSE(ValidateObservation0Proof(
      foreign_session, applications, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155).valid);
  auto foreign_config = publications;
  foreign_config[0].config_hash = std::string(64, 'b');
  EXPECT_FALSE(ValidateObservation0Proof(
      foreign_config, applications, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155).valid);
}

TEST(BackendInvariants, Observation0RejectsOverrideContactAndHistoryGaps)
{
  ReceiptFacts selected;
  selected.session_id = "run";
  selected.config_hash = std::string(64, 'a');
  selected.key = {17, 41};
  selected.episode_generation = 3;
  selected.reset_epoch = 2;
  selected.runtime_generation = 5;
  selected.source = 4;
  selected.source_instance_id = 29;
  selected.stamp_ns = 120;
  selected.frame_id = "base_link";
  selected.twist = {0, 0, 0, 0, 0, 0};
  ReceiptFacts adjacent = selected;
  adjacent.key.publish_sequence = 42;
  adjacent.source = 4;
  adjacent.sequence = 10;
  adjacent.stamp_ns = 151;
  const std::vector<ReceiptFacts> publications{selected, adjacent};
  const std::vector<ContactHistoryFact> healthy{
      {12, 130, true, true, false}, {13, 140, true, true, false},
      {14, 150, true, true, false}};
  const AppliedReceiptFact applied{17, 41, 12, 130, true, false};

  auto override_fact = applied;
  override_fact.local_zero_override = true;
  EXPECT_FALSE(ValidateObservation0Proof(
      publications, {override_fact}, healthy, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155).valid);
  auto active = healthy;
  active[1].contact_active = true;
  EXPECT_FALSE(ValidateObservation0Proof(
      publications, {applied}, active, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155).valid);
  auto gap = healthy;
  gap[1].physics_iteration = 15;
  EXPECT_FALSE(ValidateObservation0Proof(
      publications, {applied}, gap, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 155).valid);
}

TEST(BackendInvariants, Observation0RejectsStaleAndFutureBoundaryReceipts)
{
  ReceiptFacts selected;
  selected.session_id = "run";
  selected.config_hash = std::string(64, 'a');
  selected.key = {17, 41};
  selected.episode_generation = 3;
  selected.reset_epoch = 2;
  selected.runtime_generation = 5;
  selected.source = 4;
  selected.source_instance_id = 29;
  selected.stamp_ns = 120;
  selected.frame_id = "base_link";
  selected.twist = {0, 0, 0, 0, 0, 0};
  ReceiptFacts adjacent = selected;
  adjacent.key.publish_sequence = 42;
  adjacent.source = 1;
  adjacent.stamp_ns = 151;
  const std::vector<AppliedReceiptFact> applications{{17, 41, 12, 130, true, false}};
  const std::vector<ContactHistoryFact> contacts{
      {12, 130, true, true, false}, {13, 140, true, true, false},
      {14, 150, true, true, false}};
  EXPECT_FALSE(ValidateObservation0Proof(
      {selected, adjacent}, applications, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 600'000'121).valid);
  adjacent.stamp_ns = 601;
  EXPECT_FALSE(ValidateObservation0Proof(
      {selected, adjacent}, applications, contacts, "run", std::string(64, 'a'),
      17, 29, 3, 2, 5, 100, 41, 42, 145, 600).valid);
}

TEST(ContactProbeMachine, RequiresContactSeparationAndOwnedTeardown)
{
  ContactProbeMachine probe;
  ASSERT_TRUE(probe.Start(11, 1'000'000));
  EXPECT_EQ(probe.Phase(), ProbePhase::AwaitSpawn);
  ASSERT_TRUE(probe.SpawnCompleted(true));
  ASSERT_TRUE(probe.BindFixture(21, 22, 23));
  for (std::uint64_t i = 1; i <= 3; ++i)
    ASSERT_TRUE(probe.Observe({i, static_cast<std::int64_t>(i) * 10'000'000,
        true, true, false, true, false, true, false}));
  EXPECT_EQ(probe.Phase(), ProbePhase::AwaitLift);
  ASSERT_TRUE(probe.LiftRequested());
  ASSERT_TRUE(probe.LiftCompleted(true));
  ASSERT_TRUE(probe.Observe({4, 40'000'000, true, true, false,
      false, false, true, true}));
  for (std::uint64_t i = 5; i <= 7; ++i)
    ASSERT_TRUE(probe.Observe({i, static_cast<std::int64_t>(i) * 10'000'000,
        true, true, false, false, false, true, false}));
  EXPECT_EQ(probe.Phase(), ProbePhase::AwaitRemove);
  EXPECT_FALSE(probe.IsVerified());
  ASSERT_TRUE(probe.RemoveRequested());
  ASSERT_TRUE(probe.RemoveCompleted(true));
  ASSERT_TRUE(probe.ObserveRemoval(true));
  EXPECT_TRUE(probe.IsVerified());
  EXPECT_EQ(probe.StartSequence(), 11u);
  EXPECT_EQ(probe.ContactSampleCount(), 3u);
  EXPECT_EQ(probe.EmptySampleCount(), 3u);
}

TEST(ContactProbeMachine, RejectsMissingDataGapsRobotContactAndBadTeardown)
{
  ContactProbeMachine missing;
  ASSERT_TRUE(missing.Start(1, 0));
  ASSERT_TRUE(missing.SpawnCompleted(true));
  ASSERT_TRUE(missing.BindFixture(3, 4, 5));
  EXPECT_FALSE(missing.Observe({1, 1, false, false, false,
      false, false, false, false}));
  EXPECT_TRUE(missing.NeedsCleanup());
  EXPECT_FALSE(missing.IsVerified());

  ContactProbeMachine gap;
  ASSERT_TRUE(gap.Start(1, 0));
  ASSERT_TRUE(gap.SpawnCompleted(true));
  ASSERT_TRUE(gap.BindFixture(3, 4, 5));
  ASSERT_TRUE(gap.Observe({1, 1, true, true, false,
      true, false, true, false}));
  EXPECT_FALSE(gap.Observe({3, 20'000'001, true, true, false,
      true, false, true, false}));

  ContactProbeMachine invalid_normal;
  ASSERT_TRUE(invalid_normal.Start(1, 0));
  ASSERT_TRUE(invalid_normal.SpawnCompleted(true));
  ASSERT_TRUE(invalid_normal.BindFixture(3, 4, 5));
  EXPECT_FALSE(invalid_normal.Observe({1, 10'000'000, true, true, false,
      true, false, false, false}));

  ContactProbeMachine duplicate;
  ASSERT_TRUE(duplicate.Start(1, 0));
  ASSERT_TRUE(duplicate.SpawnCompleted(true));
  ASSERT_TRUE(duplicate.BindFixture(3, 4, 5));
  ASSERT_TRUE(duplicate.Observe({1, 10'000'000, true, true, false,
      true, false, true, false}));
  EXPECT_FALSE(duplicate.Observe({1, 10'000'000, true, true, false,
      true, false, true, false}));

  ContactProbeMachine robot_contact;
  ASSERT_TRUE(robot_contact.Start(1, 0));
  ASSERT_TRUE(robot_contact.SpawnCompleted(true));
  ASSERT_TRUE(robot_contact.BindFixture(3, 4, 5));
  EXPECT_FALSE(robot_contact.Observe({1, 1, true, true, false,
      false, true, true, false}));

  ContactProbeMachine teardown;
  ASSERT_TRUE(teardown.Start(1, 0));
  ASSERT_TRUE(teardown.SpawnCompleted(true));
  ASSERT_TRUE(teardown.BindFixture(3, 4, 5));
  for (std::uint64_t i = 1; i <= 3; ++i)
    ASSERT_TRUE(teardown.Observe({i, static_cast<std::int64_t>(i) * 10'000'000,
        true, true, false, true, false, true, false}));
  ASSERT_TRUE(teardown.LiftRequested());
  ASSERT_TRUE(teardown.LiftCompleted(true));
  ASSERT_TRUE(teardown.Observe({4, 40'000'000, true, true, false,
      false, false, true, true}));
  for (std::uint64_t i = 5; i <= 7; ++i)
    ASSERT_TRUE(teardown.Observe({i, static_cast<std::int64_t>(i) * 10'000'000,
        true, true, false, false, false, true, false}));
  ASSERT_TRUE(teardown.RemoveRequested());
  EXPECT_FALSE(teardown.RemoveCompleted(false));
  EXPECT_FALSE(teardown.ObserveRemoval(false));
  EXPECT_FALSE(teardown.IsVerified());
}

TEST(ContactProbeMachine, DeadlineAbortAndInvalidationNeverVerify)
{
  ContactProbeMachine timeout;
  ASSERT_TRUE(timeout.Start(1, 10));
  EXPECT_TRUE(timeout.Expire(10 + ContactProbeMachine::kDeadlineNs -
                             ContactProbeMachine::kCleanupReserveNs));
  EXPECT_EQ(timeout.Phase(), ProbePhase::Failed);
  EXPECT_FALSE(timeout.IsVerified());

  ContactProbeMachine abort;
  ASSERT_TRUE(abort.Start(1, 0));
  ASSERT_TRUE(abort.SpawnCompleted(true));
  ASSERT_TRUE(abort.BindFixture(3, 4, 5));
  abort.Abort();
  EXPECT_TRUE(abort.NeedsCleanup());
  EXPECT_EQ(abort.Phase(), ProbePhase::Cancelled);
  ASSERT_TRUE(abort.RemoveRequested());
  ASSERT_TRUE(abort.RemoveCompleted(true));
  EXPECT_FALSE(abort.ObserveRemoval(false));
  EXPECT_FALSE(abort.IsVerified());

  ContactProbeMachine rollback;
  ASSERT_TRUE(rollback.Start(1, 0));
  ASSERT_TRUE(rollback.SpawnCompleted(true));
  ASSERT_TRUE(rollback.BindFixture(3, 4, 5));
  ASSERT_TRUE(rollback.Observe({2, 20'000'000, true, true, false,
      true, false, true, false}));
  EXPECT_FALSE(rollback.Observe({1, 10'000'000, true, true, false,
      true, false, true, false}));
  EXPECT_FALSE(rollback.IsVerified());
}

TEST(ContactProbeAdmission, UsesProductionFailClosedPreconditions)
{
  EXPECT_EQ(EvaluateProbeAdmission(true, true, false, false, false, false,
      false, false, false, true), ProbeAdmission::Ready);
  EXPECT_EQ(EvaluateProbeAdmission(false, true, false, false, false, false,
      false, false, false, true), ProbeAdmission::NotReady);
  EXPECT_EQ(EvaluateProbeAdmission(true, true, true, false, false, false,
      false, false, false, true), ProbeAdmission::NotReady);
  EXPECT_EQ(EvaluateProbeAdmission(true, true, false, false, true, false,
      false, false, false, true), ProbeAdmission::NotReady);
  EXPECT_EQ(EvaluateProbeAdmission(true, true, false, false, false, true,
      false, false, false, true), ProbeAdmission::NotReady);
  EXPECT_EQ(EvaluateProbeAdmission(true, true, false, false, false, false,
      true, false, false, true), ProbeAdmission::NotReady);
  EXPECT_EQ(EvaluateProbeAdmission(true, true, false, false, false, false,
      false, false, true, true), ProbeAdmission::FixtureConflict);
  EXPECT_EQ(EvaluateProbeAdmission(true, true, false, false, false, false,
      false, false, false, false), ProbeAdmission::NotReady);
}

TEST(ContactProbeMachine, LateRemoveCompletionAfterAbortOrDeadlineCannotVerify)
{
  const auto prepare_remove = [](ContactProbeMachine &probe) {
    EXPECT_TRUE(probe.Start(8, 0));
    EXPECT_TRUE(probe.SpawnCompleted(true));
    EXPECT_TRUE(probe.BindFixture(31, 32, 33));
    for (std::uint64_t i = 1; i <= 3; ++i)
      EXPECT_TRUE(probe.Observe({i, static_cast<std::int64_t>(i) * 10'000'000,
          true, true, false, true, false, true, false}));
    EXPECT_TRUE(probe.LiftRequested());
    EXPECT_TRUE(probe.LiftCompleted(true));
    EXPECT_TRUE(probe.Observe({4, 40'000'000, true, true, false,
        false, false, true, true}));
    for (std::uint64_t i = 5; i <= 7; ++i)
      EXPECT_TRUE(probe.Observe({i, static_cast<std::int64_t>(i) * 10'000'000,
          true, true, false, false, false, true, false}));
    EXPECT_TRUE(probe.RemoveRequested());
  };

  ContactProbeMachine aborted;
  prepare_remove(aborted);
  aborted.Abort();
  ASSERT_TRUE(aborted.RemoveCompleted(true));
  EXPECT_FALSE(aborted.ObserveRemoval(true));
  EXPECT_EQ(aborted.Phase(), ProbePhase::Cancelled);
  EXPECT_FALSE(aborted.IsVerified());

  ContactProbeMachine expired;
  prepare_remove(expired);
  EXPECT_TRUE(expired.Expire(ContactProbeMachine::kDeadlineNs));
  ASSERT_TRUE(expired.RemoveCompleted(true));
  EXPECT_FALSE(expired.ObserveRemoval(true));
  EXPECT_EQ(expired.Phase(), ProbePhase::Failed);
  EXPECT_FALSE(expired.IsVerified());
}

TEST(BackendSystemControlReceiver, Observation0AppliesOnlyOnUpdateAndCachesResult)
{
  BackendSystem system;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  gz::sim::EntityComponentManager ecm;
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  ASSERT_TRUE(BackendSystemTestPeer::SessionBound(system));
  ASSERT_EQ(BackendSystemTestPeer::Revision(system), 1u);
  BackendSystemTestPeer::SeedObservationHistory(system);

  const auto request = Observation0Request();
  const auto queued = BackendSystemTestPeer::Receive(system, request);
  ASSERT_EQ(queued.result, ControlResponse::RESULT_QUEUED);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
  EXPECT_EQ(BackendSystemTestPeer::Revision(system), 1u);
  EXPECT_EQ(BackendSystemTestPeer::QueueSize(system), 1u);

  const auto duplicate_before_tick = BackendSystemTestPeer::Receive(
      system, request);
  EXPECT_EQ(duplicate_before_tick.result, ControlResponse::RESULT_QUEUED);
  EXPECT_EQ(BackendSystemTestPeer::QueueSize(system), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));

  BackendSystemTestPeer::Tick(system, ecm, 200, 20);
  const auto applied = BackendSystemTestPeer::Cached(system, 2);
  EXPECT_EQ(applied.result, ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(applied.applied_binding_revision, 2u);
  EXPECT_TRUE(BackendSystemTestPeer::ObservationAuthorized(system));
  EXPECT_EQ(BackendSystemTestPeer::Revision(system), 2u);

  const auto duplicate_after_tick = BackendSystemTestPeer::Receive(
      system, request);
  EXPECT_EQ(duplicate_after_tick.result, ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(BackendSystemTestPeer::Revision(system), 2u);
}

TEST(BackendSystemControlReceiver, Observation0RejectsInvalidApplicationAndBoundary)
{
  const auto run_case = [](
      bool local_override, std::uint64_t adjacent_seq,
      std::uint64_t selected_seq = 41, bool selected_zero = true,
      std::int64_t selected_stamp = 120,
      bool contact_history_complete = true) {
    BackendSystem system;
    BackendSystemTestPeer::SeedRunDescriptor(system);
    gz::sim::EntityComponentManager ecm;
    if (!BindThroughProductionReceiver(system, ecm)) return false;
    BackendSystemTestPeer::SeedObservationHistory(
        system, local_override, adjacent_seq, selected_seq, selected_zero,
        selected_stamp, contact_history_complete);
    auto request = Observation0Request();
    const auto response = BackendSystemTestPeer::Receive(system, request);
    if (response.result != ControlResponse::RESULT_QUEUED) return false;
    BackendSystemTestPeer::Tick(system, ecm, 200, 20);
    return BackendSystemTestPeer::Cached(system, 2).result ==
            ControlResponse::RESULT_REJECTED &&
        !BackendSystemTestPeer::ObservationAuthorized(system) &&
        BackendSystemTestPeer::Revision(system) == 1;
  };
  EXPECT_TRUE(run_case(true, 42));
  EXPECT_TRUE(run_case(false, 43));
  EXPECT_TRUE(run_case(false, 42, 40));
  EXPECT_TRUE(run_case(false, 42, 41, false));
  EXPECT_TRUE(run_case(false, 42, 41, true, 700'000'000));
  EXPECT_TRUE(run_case(false, 42, 41, true, 120, false));
}

TEST(BackendSystemControlReceiver, Observation0RejectsApplicationAndContextMismatch)
{
  for (int mutation = 0; mutation <= 6; ++mutation)
  {
    BackendSystem system;
    BackendSystemTestPeer::SeedRunDescriptor(system);
    gz::sim::EntityComponentManager ecm;
    ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
    BackendSystemTestPeer::SeedObservationHistory(system);
    BackendSystemTestPeer::MutateObservationHistory(system, mutation);

    const auto queued = BackendSystemTestPeer::Receive(
        system, Observation0Request());
    ASSERT_EQ(queued.result, ControlResponse::RESULT_QUEUED);
    EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
    BackendSystemTestPeer::Tick(system, ecm, 200, 20);
    EXPECT_EQ(BackendSystemTestPeer::Cached(system, 2).result,
              ControlResponse::RESULT_REJECTED);
    EXPECT_EQ(BackendSystemTestPeer::Revision(system), 1u);
    EXPECT_FALSE(BackendSystemTestPeer::ObservationAuthorized(system));
  }
}

TEST(BackendSystemControlReceiver, InhibitCancelsQueuedMutationBeforeApply)
{
  BackendSystem system;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  gz::sim::EntityComponentManager ecm;
  auto bind = BindSessionRequest();
  const auto queued_bind = BackendSystemTestPeer::Receive(system, bind);
  ASSERT_EQ(queued_bind.result, ControlResponse::RESULT_QUEUED);
  EXPECT_FALSE(BackendSystemTestPeer::SessionBound(system));

  auto inhibit = BaseControlRequest(2);
  inhibit.operation = ControlRequest::OP_INHIBIT;
  const auto queued_inhibit = BackendSystemTestPeer::Receive(system, inhibit);
  ASSERT_EQ(queued_inhibit.result, ControlResponse::RESULT_QUEUED);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 1).reason_code,
            ControlResponse::REASON_CANCELLED);
  EXPECT_EQ(BackendSystemTestPeer::QueueSize(system), 1u);

  BackendSystemTestPeer::Tick(system, ecm);
  EXPECT_FALSE(BackendSystemTestPeer::SessionBound(system));
  EXPECT_EQ(BackendSystemTestPeer::Revision(system), 1u);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 2).result,
            ControlResponse::RESULT_APPLIED);
}

TEST(BackendSystemControlReceiver, CasIsRecheckedAtUpdateAndCacheEvictsOldReplay)
{
  BackendSystem system;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  gz::sim::EntityComponentManager ecm;
  auto bind = BindSessionRequest();
  const auto queued = BackendSystemTestPeer::Receive(system, bind);
  ASSERT_EQ(queued.result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::ChangeRevision(system, 9);
  BackendSystemTestPeer::Tick(system, ecm);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 1).reason_code,
            ControlResponse::REASON_REVISION_MISMATCH);
  EXPECT_FALSE(BackendSystemTestPeer::SessionBound(system));

  BackendSystem cache_system;
  BackendSystemTestPeer::SeedRunDescriptor(cache_system);
  for (std::uint64_t sequence = 1; sequence <= 129; ++sequence)
  {
    auto inhibit = BaseControlRequest(sequence);
    inhibit.operation = ControlRequest::OP_INHIBIT;
    const auto response = BackendSystemTestPeer::Receive(cache_system, inhibit);
    ASSERT_EQ(response.result, ControlResponse::RESULT_QUEUED);
    BackendSystemTestPeer::Tick(cache_system, ecm);
  }
  auto evicted = BaseControlRequest(1);
  evicted.operation = ControlRequest::OP_INHIBIT;
  const auto replay = BackendSystemTestPeer::Receive(cache_system, evicted);
  EXPECT_EQ(replay.reason_code, ControlResponse::REASON_REQUEST_REPLAY);
  EXPECT_EQ(BackendSystemTestPeer::QueueSize(cache_system), 0u);
}

TEST(BackendSystemControlReceiver, ExactDuplicateConflictGapAndQueueOverflow)
{
  BackendSystem system;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  auto query = BaseControlRequest(1);
  query.operation = ControlRequest::OP_VERIFY_CONTACT_CAPABILITY;
  query.probe_action = ControlRequest::PROBE_ACTION_QUERY;
  query.probe_start_request_sequence = 77;
  const auto first = BackendSystemTestPeer::Receive(system, query);
  ASSERT_EQ(first.result, ControlResponse::RESULT_QUEUED);
  const auto duplicate = BackendSystemTestPeer::Receive(system, query);
  EXPECT_EQ(duplicate.result, ControlResponse::RESULT_QUEUED);
  EXPECT_EQ(BackendSystemTestPeer::QueueSize(system), 1u);

  auto conflict = query;
  conflict.probe_start_request_sequence = 78;
  const auto changed = BackendSystemTestPeer::Receive(system, conflict);
  EXPECT_EQ(changed.reason_code,
            ControlResponse::REASON_DUPLICATE_CONTENT_CONFLICT);

  BackendSystem gap_system;
  BackendSystemTestPeer::SeedRunDescriptor(gap_system);
  auto gap = query;
  gap.request_sequence = 2;
  const auto gap_response = BackendSystemTestPeer::Receive(
      gap_system, gap);
  EXPECT_EQ(gap_response.reason_code, ControlResponse::REASON_REQUEST_GAP);

  BackendSystem full_system;
  BackendSystemTestPeer::SeedRunDescriptor(full_system);
  for (std::uint64_t sequence = 1; sequence <= 8; ++sequence)
  {
    auto request = query;
    request.request_sequence = sequence;
    const auto response = BackendSystemTestPeer::Receive(full_system, request);
    ASSERT_EQ(response.result, ControlResponse::RESULT_QUEUED);
  }
  auto overflow = query;
  overflow.request_sequence = 9;
  const auto overflow_response = BackendSystemTestPeer::Receive(
      full_system, overflow);
  EXPECT_EQ(overflow_response.reason_code, ControlResponse::REASON_QUEUE_OVERFLOW);
  EXPECT_EQ(BackendSystemTestPeer::QueueSize(full_system), 8u);
}

TEST(BackendSystemControlReceiver, ProbeStartUsesReceiverUpdateAndInjectedTransport)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);

  std::vector<ros_gz_interfaces::srv::SpawnEntity::Request> spawn_requests;
  std::vector<std::function<void(bool)>> spawn_completions;
  std::size_t pose_calls = 0;
  std::size_t remove_calls = 0;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [&](const auto &request, std::function<void(bool)> completion) {
        spawn_requests.push_back(request);
        spawn_completions.push_back(std::move(completion));
      },
      [&](const auto &, std::function<void(bool)> completion) {
        ++pose_calls;
        completion(true);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        ++remove_calls;
        completion(true);
      });

  const auto request = ProbeStartRequest();
  const auto queued = BackendSystemTestPeer::Receive(system, request);
  ASSERT_EQ(queued.result, ControlResponse::RESULT_QUEUED);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);

  const auto applied = BackendSystemTestPeer::Cached(system, 2);
  ASSERT_EQ(applied.result, ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(applied.contact_capability_state,
            ControlResponse::CAPABILITY_RUNNING);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitSpawn);

  BackendSystemTestPeer::RequestSpawn(system);
  ASSERT_EQ(spawn_requests.size(), 1u);
  EXPECT_EQ(spawn_requests.front().entity_factory.name,
            "b2_capability_probe");
  EXPECT_FALSE(spawn_requests.front().entity_factory.allow_renaming);
  EXPECT_DOUBLE_EQ(spawn_requests.front().entity_factory.pose.position.x, -2.0);
  EXPECT_DOUBLE_EQ(spawn_requests.front().entity_factory.pose.position.y, 0.0);
  EXPECT_DOUBLE_EQ(spawn_requests.front().entity_factory.pose.position.z, 0.07);
  EXPECT_EQ(pose_calls, 0u);
  EXPECT_EQ(remove_calls, 0u);

  const auto duplicate = BackendSystemTestPeer::Receive(system, request);
  EXPECT_EQ(duplicate.result, ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(spawn_requests.size(), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));

  ASSERT_EQ(spawn_completions.size(), 1u);
  spawn_completions.front()(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitFixture);
  EXPECT_TRUE(BackendSystemTestPeer::ProbeRunning(system));
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemControlReceiver, ProbeSpawnReplyRequiresOwnedEcmEntity)
{
  for (const bool service_success : {false, true})
  {
    BackendSystem system;
    gz::sim::EntityComponentManager ecm;
    BackendSystemTestPeer::SeedRunDescriptor(system);
    ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
    BackendSystemTestPeer::PrepareProbe(system);
    std::function<void(bool)> spawn_completion;
    std::size_t spawn_calls = 0;
    BackendSystemTestPeer::InjectProbeTransport(
        system,
        [&](const auto &, std::function<void(bool)> completion) {
          ++spawn_calls;
          spawn_completion = std::move(completion);
        },
        [](const auto &, std::function<void(bool)> completion) {
          completion(true);
        },
        [](const auto &, std::function<void(bool)> completion) {
          completion(true);
        });
    BackendSystemTestPeer::SetCapabilityPrerequisites(system);

    ASSERT_EQ(BackendSystemTestPeer::Receive(
        system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
    BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
    ASSERT_EQ(BackendSystemTestPeer::Cached(system, 2).result,
              ControlResponse::RESULT_APPLIED);
    BackendSystemTestPeer::RequestSpawn(system);
    ASSERT_EQ(spawn_calls, 1u);
    spawn_completion(service_success);
    BackendSystemTestPeer::ProcessProbeResults(system);
    BackendSystemTestPeer::AdvanceProbe(
        system, ecm, 201, 30, 2'010'000'000);

    EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
    EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
    if (service_success)
    {
      EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
                ProbePhase::AwaitFixture);
      EXPECT_EQ(BackendSystemTestPeer::ProbeModelCount(ecm), 0u);
    }
    else
    {
      EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
                ProbePhase::Failed);
      EXPECT_EQ(BackendSystemTestPeer::ProbeModelCount(ecm), 0u);
    }
  }
}

TEST(BackendSystemControlReceiver, ProbeLiftAndCleanupFailuresStayInhibited)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  std::function<void(bool)> lift_completion;
  std::size_t remove_calls = 0;
  std::function<void(bool)> remove_completion;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        lift_completion = std::move(completion);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        ++remove_calls;
        remove_completion = std::move(completion);
      });
  BackendSystemTestPeer::SetCapabilityPrerequisites(system);
  ASSERT_EQ(BackendSystemTestPeer::Receive(
      system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  BackendSystemTestPeer::RequestSpawn(system);
  BackendSystemTestPeer::ProcessProbeResults(system);
  ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm));
  ASSERT_TRUE(BackendSystemTestPeer::ResolveProbeFixture(system, ecm));
  const auto collision = BackendSystemTestPeer::ProbeCollision(system);
  const auto floor = BackendSystemTestPeer::ProbeFloor(system);
  for (std::uint64_t iteration = 1; iteration <= 3; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(
        ecm, collision, collision, floor, true);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration,
        static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  ASSERT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitLift);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 4, 40'000'000, 2'040'000'000);
  ASSERT_TRUE(static_cast<bool>(lift_completion));
  lift_completion(false);
  BackendSystemTestPeer::ProcessProbeResults(system);
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::Failed);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));

  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 5, 50'000'000, 2'050'000'000);
  ASSERT_EQ(remove_calls, 1u);
  remove_completion(false);
  BackendSystemTestPeer::ProcessProbeResults(system);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 6, 60'000'000, 2'060'000'000);
  EXPECT_NE(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::Verified);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemControlReceiver, ProbeRemoveAckDoesNotVerifyWhileFixtureRemains)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  std::function<void(bool)> lift_completion;
  std::function<void(bool)> remove_completion;
  std::size_t remove_calls = 0;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        lift_completion = std::move(completion);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        ++remove_calls;
        remove_completion = std::move(completion);
      });
  BackendSystemTestPeer::SetCapabilityPrerequisites(system);

  ASSERT_EQ(BackendSystemTestPeer::Receive(
      system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  BackendSystemTestPeer::RequestSpawn(system);
  ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm));
  BackendSystemTestPeer::ProcessProbeResults(system);
  ASSERT_TRUE(BackendSystemTestPeer::ResolveProbeFixture(system, ecm));
  const auto collision = BackendSystemTestPeer::ProbeCollision(system);
  const auto floor = BackendSystemTestPeer::ProbeFloor(system);
  for (std::uint64_t iteration = 1; iteration <= 3; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(
        ecm, collision, collision, floor, true);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration,
        static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  ASSERT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitLift);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 4, 40'000'000, 2'040'000'000);
  ASSERT_TRUE(static_cast<bool>(lift_completion));
  lift_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  BackendSystemTestPeer::SetProbePose(
      ecm, BackendSystemTestPeer::ProbeModel(system), 0.20);
  for (std::uint64_t iteration = 4; iteration <= 7; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(
        ecm, collision, collision, floor, false);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration,
        static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  ASSERT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitRemove);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 8, 80'000'000, 2'080'000'000);
  ASSERT_EQ(remove_calls, 1u);
  remove_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 9, 90'000'000, 2'090'000'000);

  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitRemoval);
  EXPECT_EQ(BackendSystemTestPeer::ProbeModelCount(ecm), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemControlReceiver, ProbeRemoveFailureAfterValidCoverageStaysInhibited)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  std::function<void(bool)> lift_completion;
  std::function<void(bool)> remove_completion;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        lift_completion = std::move(completion);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        remove_completion = std::move(completion);
      });
  BackendSystemTestPeer::SetCapabilityPrerequisites(system);
  ASSERT_EQ(BackendSystemTestPeer::Receive(
      system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  BackendSystemTestPeer::RequestSpawn(system);
  ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm));
  BackendSystemTestPeer::ProcessProbeResults(system);
  ASSERT_TRUE(BackendSystemTestPeer::ResolveProbeFixture(system, ecm));
  const auto collision = BackendSystemTestPeer::ProbeCollision(system);
  const auto floor = BackendSystemTestPeer::ProbeFloor(system);
  for (std::uint64_t iteration = 1; iteration <= 3; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(
        ecm, collision, collision, floor, true);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration,
        static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 4, 40'000'000, 2'040'000'000);
  ASSERT_TRUE(static_cast<bool>(lift_completion));
  lift_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  BackendSystemTestPeer::SetProbePose(
      ecm, BackendSystemTestPeer::ProbeModel(system), 0.20);
  for (std::uint64_t iteration = 4; iteration <= 7; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(
        ecm, collision, collision, floor, false);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration,
        static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  ASSERT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitRemove);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 8, 80'000'000, 2'080'000'000);
  ASSERT_TRUE(static_cast<bool>(remove_completion));
  remove_completion(false);
  BackendSystemTestPeer::ProcessProbeResults(system);
  BackendSystemTestPeer::AdvanceProbe(
      system, ecm, 9, 90'000'000, 2'090'000'000);

  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::Failed);
  EXPECT_EQ(BackendSystemTestPeer::ProbeModelCount(ecm), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemControlReceiver, ProbeNameConflictNeverRemovesUnownedFixture)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  gz::sim::Entity existing_model = ecm.CreateEntity();
  ecm.CreateComponent(existing_model,
      gz::sim::components::Name("b2_capability_probe"));
  ecm.CreateComponent(existing_model,
      gz::sim::components::Model());
  ecm.CreateComponent(existing_model, gz::sim::components::ParentEntity(
      BackendSystemTestPeer::ProbeWorld(system)));
  std::size_t spawn_calls = 0;
  std::size_t remove_calls = 0;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [&](const auto &, std::function<void(bool)>) { ++spawn_calls; },
      [](const auto &, std::function<void(bool)>) {},
      [&](const auto &, std::function<void(bool)>) { ++remove_calls; });
  BackendSystemTestPeer::SetCapabilityPrerequisites(system);

  ASSERT_EQ(BackendSystemTestPeer::Receive(
      system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);

  EXPECT_EQ(spawn_calls, 0u);
  EXPECT_EQ(remove_calls, 0u);
  EXPECT_EQ(BackendSystemTestPeer::ProbeModelCount(ecm), 1u);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemControlReceiver, ProbeRejectsMalformedAndDiscontinuousSamples)
{
  for (int failure = 0; failure < 3; ++failure)
  {
    BackendSystem system;
    gz::sim::EntityComponentManager ecm;
    BackendSystemTestPeer::SeedRunDescriptor(system);
    ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
    BackendSystemTestPeer::PrepareProbe(system);
    BackendSystemTestPeer::InjectProbeTransport(
        system,
        [](const auto &, std::function<void(bool)> completion) {
          completion(true);
        },
        [](const auto &, std::function<void(bool)> completion) {
          completion(true);
        },
        [](const auto &, std::function<void(bool)> completion) {
          completion(true);
        });
    BackendSystemTestPeer::SetCapabilityPrerequisites(system);
    ASSERT_EQ(BackendSystemTestPeer::Receive(
        system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
    BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
    BackendSystemTestPeer::RequestSpawn(system);
    ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm));
    BackendSystemTestPeer::ProcessProbeResults(system);
    ASSERT_TRUE(BackendSystemTestPeer::ResolveProbeFixture(system, ecm));
    const auto collision = BackendSystemTestPeer::ProbeCollision(system);
    const auto floor = BackendSystemTestPeer::ProbeFloor(system);
    if (failure == 0)
    {
      BackendSystemTestPeer::SetProbeContact(
          ecm, collision, collision, floor, true, false);
      BackendSystemTestPeer::ObserveProbe(system, ecm, 1, 10'000'000);
    }
    else
    {
      BackendSystemTestPeer::SetProbeContact(
          ecm, collision, collision, floor, true);
      BackendSystemTestPeer::ObserveProbe(
          system, ecm, 1, failure == 1 ? 10'000'000 : 20'000'000);
      BackendSystemTestPeer::SetProbeContact(
          ecm, collision, collision, floor, true);
      BackendSystemTestPeer::ObserveProbe(
          system, ecm, failure == 1 ? 3 : 2,
          failure == 1 ? 30'000'000 : 10'000'000);
    }
    EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
              ProbePhase::Failed);
    EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
    EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  }
}

TEST(BackendSystemControlReceiver, ProbeReadsCollisionEcmAndWaitsForOwnedTeardown)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  std::function<void(bool)> spawn_completion;
  std::function<void(bool)> lift_completion;
  std::function<void(bool)> remove_completion;
  std::size_t spawn_calls = 0;
  std::size_t lift_calls = 0;
  std::size_t remove_calls = 0;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [&](const auto &, std::function<void(bool)> completion) {
        ++spawn_calls;
        spawn_completion = std::move(completion);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        ++lift_calls;
        lift_completion = std::move(completion);
      },
      [&](const auto &, std::function<void(bool)> completion) {
        ++remove_calls;
        remove_completion = std::move(completion);
      });
  BackendSystemTestPeer::SetCapabilityPrerequisites(system);

  ASSERT_EQ(BackendSystemTestPeer::Receive(
      system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  ASSERT_EQ(spawn_calls, 0u);
  BackendSystemTestPeer::RequestSpawn(system);
  ASSERT_EQ(spawn_calls, 1u);
  spawn_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  ASSERT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitFixture);
  ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm));
  EXPECT_EQ(BackendSystemTestPeer::NamedProbeScope(ecm),
            "b2_training_arena::b2_capability_probe");
  EXPECT_EQ(BackendSystemTestPeer::ProbeModelCount(ecm), 1u);
  EXPECT_TRUE(BackendSystemTestPeer::IsProbeInBoundWorld(system, ecm));
  const auto collision_entities = ecm.EntitiesByComponents(
      gz::sim::components::Name("collision"),
      gz::sim::components::Collision());
  ASSERT_EQ(collision_entities.size(), 1u);
  EXPECT_EQ(gz::sim::scopedName(collision_entities.front(), ecm, "::", false),
      "b2_training_arena::b2_capability_probe::link::collision");
  const auto sensor_entity = BackendSystemTestPeer::ProbeSensor(system);
  const auto collision_entity = collision_entities.front();
  ASSERT_NE(ecm.Component<gz::sim::components::Name>(sensor_entity), nullptr);
  EXPECT_EQ(ecm.Component<gz::sim::components::Name>(sensor_entity)->Data(),
            "contact_sensor");
  ASSERT_NE(ecm.Component<gz::sim::components::ContactSensor>(sensor_entity),
            nullptr);
  ASSERT_NE(ecm.Component<gz::sim::components::Collision>(collision_entity),
            nullptr);
  EXPECT_EQ(ecm.Component<gz::sim::components::ParentEntity>(sensor_entity)->Data(),
            ecm.Component<gz::sim::components::ParentEntity>(collision_entity)->Data());
  EXPECT_EQ(ecm.Component<gz::sim::components::ContactSensorData>(sensor_entity),
            nullptr);
  ASSERT_NE(ecm.Component<gz::sim::components::ContactSensorData>(collision_entity),
            nullptr);
  EXPECT_EQ(gz::sim::scopedName(sensor_entity, ecm, "::", false),
      "b2_training_arena::b2_capability_probe::link::contact_sensor");
  ASSERT_TRUE(BackendSystemTestPeer::ResolveProbeFixture(system, ecm));
  ASSERT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitContact);
  const auto collision = BackendSystemTestPeer::ProbeCollision(system);
  const auto floor = BackendSystemTestPeer::ProbeFloor(system);
  for (std::uint64_t iteration = 1; iteration <= 3; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(ecm, collision, collision, floor, true);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration, static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitLift);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));

  BackendSystemTestPeer::AdvanceProbe(system, ecm, 4, 40'000'000,
                                      2'040'000'000);
  ASSERT_EQ(lift_calls, 1u);
  lift_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  BackendSystemTestPeer::SetProbePose(ecm, BackendSystemTestPeer::ProbeModel(system),
                                      0.20);
  for (std::uint64_t iteration = 4; iteration <= 7; ++iteration)
  {
    BackendSystemTestPeer::SetProbeContact(ecm, collision, collision, floor, false);
    BackendSystemTestPeer::ObserveProbe(
        system, ecm, iteration, static_cast<std::int64_t>(iteration) * 10'000'000);
  }
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::AwaitRemove);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));

  BackendSystemTestPeer::AdvanceProbe(system, ecm, 8, 80'000'000,
                                      2'080'000'000);
  ASSERT_EQ(remove_calls, 1u);
  remove_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  const auto model = BackendSystemTestPeer::ProbeModel(system);
  const auto sensor = BackendSystemTestPeer::ProbeSensor(system);
  const auto link = ecm.Component<gz::sim::components::ParentEntity>(
      collision)->Data();
  BackendSystemTestPeer::RemoveProbeEntities(
      ecm, model, link, collision, sensor);
  BackendSystemTestPeer::AdvanceProbe(system, ecm, 9, 90'000'000,
                                      2'090'000'000);
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::Verified);
  EXPECT_TRUE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemControlReceiver, SensorEntityDataCannotProveProbeContact)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  std::function<void(bool)> spawn_completion;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [&](const auto &, std::function<void(bool)> completion) {
        spawn_completion = std::move(completion);
      },
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      },
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      });
  BackendSystemTestPeer::SetCapabilityPrerequisites(system);
  ASSERT_EQ(BackendSystemTestPeer::Receive(
      system, ProbeStartRequest()).result, ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  BackendSystemTestPeer::RequestSpawn(system);
  ASSERT_TRUE(static_cast<bool>(spawn_completion));
  spawn_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm, true));
  ASSERT_TRUE(BackendSystemTestPeer::ResolveProbeFixture(system, ecm));

  const auto sensor = BackendSystemTestPeer::ProbeSensor(system);
  const auto collision = BackendSystemTestPeer::ProbeCollision(system);
  const auto floor = BackendSystemTestPeer::ProbeFloor(system);
  ASSERT_NE(ecm.Component<gz::sim::components::ContactSensorData>(sensor), nullptr);
  EXPECT_EQ(ecm.Component<gz::sim::components::ContactSensorData>(collision),
            nullptr);
  BackendSystemTestPeer::SetProbeContact(ecm, sensor, collision, floor, true);
  BackendSystemTestPeer::ObserveProbe(system, ecm, 1, 10'000'000);

  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system), ProbePhase::Failed);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
}

TEST(BackendSystemContactBinding, RegisteredCoverageReadsCollisionEntity)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::PrepareProbe(system);
  ASSERT_TRUE(BackendSystemTestPeer::SeedProbeEntities(system, ecm, true));
  const auto sensor = BackendSystemTestPeer::ProbeSensor(system);
  const auto collisions = ecm.EntitiesByComponents(
      gz::sim::components::Name("collision"),
      gz::sim::components::Collision());
  ASSERT_EQ(collisions.size(), 1u);
  const auto collision = collisions.front();
  ASSERT_NE(ecm.Component<gz::sim::components::ContactSensorData>(sensor), nullptr);
  EXPECT_EQ(ecm.Component<gz::sim::components::ContactSensorData>(collision),
            nullptr);

  const auto missing = BackendSystemTestPeer::BuildRegisteredCollisionSample(
      system, ecm, collision, 1);
  EXPECT_FALSE(missing.component_present);
  EXPECT_EQ(missing.observed_mask, 0u);

  ecm.CreateComponent(collision,
      gz::sim::components::ContactSensorData(gz::msgs::Contacts()));
  const auto covered_empty =
      BackendSystemTestPeer::BuildRegisteredCollisionSample(
          system, ecm, collision, 2);
  EXPECT_TRUE(covered_empty.component_present);
  EXPECT_EQ(covered_empty.observed_mask, 1u);
}

TEST(BackendSystemControlReceiver, ProbeQueryDoesNotExtendDeadlineAndLateSpawnCannotReviveAbort)
{
  BackendSystem system;
  gz::sim::EntityComponentManager ecm;
  BackendSystemTestPeer::SeedRunDescriptor(system);
  ASSERT_TRUE(BindThroughProductionReceiver(system, ecm));
  BackendSystemTestPeer::PrepareProbe(system);
  std::function<void(bool)> spawn_completion;
  std::size_t spawn_count = 0;
  BackendSystemTestPeer::InjectProbeTransport(
      system,
      [&](const auto &, std::function<void(bool)> completion) {
        ++spawn_count;
        spawn_completion = std::move(completion);
      },
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      },
      [](const auto &, std::function<void(bool)> completion) {
        completion(true);
      });

  const auto start = ProbeStartRequest();
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, start).result,
            ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 200, 20, 2'000'000'000);
  ASSERT_EQ(BackendSystemTestPeer::Cached(system, 2).result,
            ControlResponse::RESULT_APPLIED);
  BackendSystemTestPeer::RequestSpawn(system);
  ASSERT_EQ(spawn_count, 1u);
  const auto original_deadline = BackendSystemTestPeer::ProbeDeadline(system);

  auto query = BaseControlRequest(3);
  query.expected_binding_revision = 1;
  query.operation = ControlRequest::OP_VERIFY_CONTACT_CAPABILITY;
  query.probe_action = ControlRequest::PROBE_ACTION_QUERY;
  query.probe_start_request_sequence = 2;
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, query).result,
            ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 210, 21, 2'100'000'000);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 3).result,
            ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(BackendSystemTestPeer::ProbeDeadline(system), original_deadline);

  auto abort = BaseControlRequest(4);
  abort.expected_binding_revision = 1;
  abort.operation = ControlRequest::OP_VERIFY_CONTACT_CAPABILITY;
  abort.probe_action = ControlRequest::PROBE_ACTION_ABORT;
  abort.probe_start_request_sequence = 2;
  ASSERT_EQ(BackendSystemTestPeer::Receive(system, abort).result,
            ControlResponse::RESULT_QUEUED);
  BackendSystemTestPeer::Tick(system, ecm, 220, 22, 2'200'000'000);
  EXPECT_EQ(BackendSystemTestPeer::Cached(system, 4).result,
            ControlResponse::RESULT_APPLIED);
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::Cancelled);

  ASSERT_TRUE(static_cast<bool>(spawn_completion));
  spawn_completion(true);
  BackendSystemTestPeer::ProcessProbeResults(system);
  EXPECT_EQ(BackendSystemTestPeer::CurrentProbePhase(system),
            ProbePhase::Cancelled);
  EXPECT_FALSE(BackendSystemTestPeer::CapabilityVerified(system));
  EXPECT_FALSE(BackendSystemTestPeer::PolicyOpen(system));
  EXPECT_EQ(spawn_count, 1u);
  EXPECT_EQ(BackendSystemTestPeer::ProbeDeadline(system), original_deadline);
}
