#include "s3_d3_ecs_contact_diagnostic/system.hh"

#include <chrono>
#include <string>
#include <limits>

#include <gz/plugin/Register.hh>
#include <gz/sim/components/Collision.hh>
#include <gz/sim/components/ContactSensor.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Sensor.hh>

namespace s3_d3::ecs_contact
{
namespace
{
bool ReadString(const sdf::ElementPtr &_sdf, const std::string &_key, std::string *_value)
{
  if (!_sdf || !_sdf->HasElement(_key)) return false;
  const auto element = _sdf->GetElement(_key);
  if (!element) return false;
  *_value = element->Get<std::string>();
  return !_value->empty();
}
bool ReadInt64(const sdf::ElementPtr &_sdf, const std::string &_key, std::int64_t *_value)
{
  if (!_sdf || !_sdf->HasElement(_key)) return false;
  const auto element = _sdf->GetElement(_key);
  if (!element) return false;
  const auto value = element->Get<std::uint64_t>();
  if (value == 0 || value > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return false;
  *_value = static_cast<std::int64_t>(value);
  return true;
}
bool ParseConfig(const sdf::ElementPtr &_sdf, DiagnosticConfig *_config)
{
  return ReadString(_sdf, "receipt_topic", &_config->receipt_topic) &&
      ReadString(_sdf, "run_id", &_config->run_id) &&
      ReadString(_sdf, "world_name", &_config->world_name) &&
      ReadString(_sdf, "model_name", &_config->model_name) &&
      ReadString(_sdf, "link_name", &_config->link_name) &&
      ReadString(_sdf, "sensor_name", &_config->sensor_name) &&
      ReadString(_sdf, "plugin_source_sha256", &_config->plugin_source_sha256) &&
      ReadString(_sdf, "plugin_binary_sha256", &_config->plugin_binary_sha256) &&
      ReadString(_sdf, "collector_source_sha256", &_config->collector_source_sha256) &&
      ReadString(_sdf, "collector_binary_sha256", &_config->collector_binary_sha256) &&
      ReadString(_sdf, "base_world_template_sha256", &_config->base_world_template_sha256) &&
      ReadString(_sdf, "native_model_sha256", &_config->native_model_sha256) &&
      ReadInt64(_sdf, "system_wait_timeout_sim_time_ns", &_config->system_wait_timeout_sim_time_ns) &&
      ReadInt64(_sdf, "system_delivery_wait_timeout_steady_ns", &_config->system_delivery_wait_timeout_steady_ns) &&
      ReadInt64(_sdf, "collector_receipt_wait_timeout_steady_ns", &_config->collector_receipt_wait_timeout_steady_ns) &&
      ReadInt64(_sdf, "collector_persist_timeout_steady_ns", &_config->collector_persist_timeout_steady_ns);
}
bool ParentMatches(const gz::sim::EntityComponentManager &_ecm, gz::sim::Entity _child,
                   gz::sim::Entity _parent)
{
  const auto component = _ecm.Component<gz::sim::components::ParentEntity>(_child);
  return component && component->Data() == _parent;
}
}  // namespace

void ContactSensorDiagnosticSystem::Configure(const gz::sim::Entity &_entity,
    const std::shared_ptr<const sdf::Element> &_sdf,
    gz::sim::EntityComponentManager &,
    gz::sim::EventManager &)
{
  configured_ = true;
  world_entity_ = _entity;
  const auto inspectable_sdf = std::const_pointer_cast<sdf::Element>(_sdf);
  config_valid_ = ParseConfig(inspectable_sdf, &config_) && ValidateConfig(config_, nullptr);
  if (config_valid_) publisher_ = node_.Advertise<EcsContactSensorDiagnosticReceipt>(config_.receipt_topic);
}

void ContactSensorDiagnosticSystem::PostUpdate(const gz::sim::UpdateInfo &_info,
    const gz::sim::EntityComponentManager &_ecm)
{
  if (!configured_ || !config_valid_ || gate_.State() == DeliveryState::kDeliverySealed) return;
  const auto now = std::chrono::steady_clock::now();
  const auto sim_now = std::chrono::duration_cast<std::chrono::nanoseconds>(_info.simTime);
  if (!first_postupdate_) { first_postupdate_ = now; first_sim_time_ = sim_now; }
  if (gate_.State() == DeliveryState::kSnapshotSealed) {
    if (!delivery_start_) delivery_start_ = now;
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(now - *delivery_start_).count();
    if (gate_.CanPublish(publisher_.HasConnections())) {
      static_cast<void>(gate_.CompletePublish(publisher_.Publish(*gate_.Snapshot())));
    } else if (elapsed >= config_.system_delivery_wait_timeout_steady_ns) {
      gate_.SealDeliveryWithoutPublish();
    }
    return;
  }

  HierarchyObservation observation;
  observation.world_id = static_cast<std::uint64_t>(world_entity_);
  observation.world_id_present = true;
  const auto models = _ecm.EntitiesByComponents(gz::sim::components::Model(),
      gz::sim::components::Name(config_.model_name));
  observation.model_exact_count = static_cast<std::uint32_t>(models.size());
  gz::sim::Entity model{};
  gz::sim::Entity link{};
  gz::sim::Entity sensor{};
  if (models.size() == 1) {
    model = models.front();
    observation.model_id = static_cast<std::uint64_t>(model);
    observation.model_id_present = true;
    const auto links = _ecm.ChildrenByComponents(model, gz::sim::components::Link(),
        gz::sim::components::Name(config_.link_name));
    observation.link_exact_count = static_cast<std::uint32_t>(links.size());
    if (links.size() == 1) {
      link = links.front();
      observation.link_id = static_cast<std::uint64_t>(link);
      observation.link_id_present = true;
      observation.link_parent_id = static_cast<std::uint64_t>(model);
      observation.link_parent_id_present = true;
      observation.link_parent_matches = ParentMatches(_ecm, link, model);
      const auto sensors = _ecm.ChildrenByComponents(link, gz::sim::components::Sensor(),
          gz::sim::components::Name(config_.sensor_name));
      observation.sensor_exact_count = static_cast<std::uint32_t>(sensors.size());
      if (sensors.size() == 1) {
        sensor = sensors.front();
        observation.sensor_id = static_cast<std::uint64_t>(sensor);
        observation.sensor_id_present = true;
        observation.sensor_parent_id = static_cast<std::uint64_t>(link);
        observation.sensor_parent_id_present = true;
        observation.sensor_parent_matches = ParentMatches(_ecm, sensor, link);
        const auto contact = _ecm.Component<gz::sim::components::ContactSensor>(sensor);
        observation.contact_component_present = contact != nullptr;
        const auto sensor_element = contact ? contact->Data() : sdf::ElementPtr{};
        observation.contact_element_present = sensor_element && sensor_element->HasElement("contact");
        const auto contact_element = observation.contact_element_present ? sensor_element->GetElement("contact") : sdf::ElementPtr{};
        observation.collision_element_present = contact_element && contact_element->HasElement("collision");
        if (observation.collision_element_present) observation.configured_collision_target = contact_element->GetElement("collision")->Get<std::string>();
        if (!observation.configured_collision_target.empty()) {
          const auto collisions = _ecm.ChildrenByComponents(link, gz::sim::components::Collision(),
              gz::sim::components::Name(observation.configured_collision_target));
          observation.collision_exact_count = static_cast<std::uint32_t>(collisions.size());
          if (collisions.size() == 1) {
            const auto collision = collisions.front();
            observation.collision_id = static_cast<std::uint64_t>(collision);
            observation.collision_id_present = true;
            observation.collision_parent_id = static_cast<std::uint64_t>(link);
            observation.collision_parent_id_present = true;
            observation.collision_name = observation.configured_collision_target;
            observation.collision_parent_matches = ParentMatches(_ecm, collision, link);
          }
        }
      }
    }
  }
  const auto elapsed_sim = sim_now - *first_sim_time_;
  const bool waiting_timeout = elapsed_sim.count() >= config_.system_wait_timeout_sim_time_ns;
  const bool fully_observed = observation.model_exact_count == 1 &&
      observation.link_exact_count == 1 && observation.link_parent_matches &&
      observation.sensor_exact_count == 1 && observation.sensor_parent_matches &&
      observation.contact_component_present && observation.contact_element_present &&
      observation.collision_element_present && !observation.configured_collision_target.empty() &&
      observation.collision_exact_count == 1 && observation.collision_parent_matches;
  if (waiting_timeout || fully_observed) {
    auto receipt = EvaluateHierarchy(config_, observation);
    receipt.set_first_postupdate_sim_time_ns(first_sim_time_->count());
    receipt.set_first_postupdate_sim_time_present(true);
    receipt.set_terminal_sim_time_ns(sim_now.count());
    receipt.set_terminal_sim_time_present(true);
    receipt.set_first_postupdate_steady_time_ns(std::chrono::duration_cast<std::chrono::nanoseconds>(first_postupdate_->time_since_epoch()).count());
    receipt.set_first_postupdate_steady_time_present(true);
    receipt.set_terminal_steady_time_ns(std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count());
    receipt.set_terminal_steady_time_present(true);
    gate_.SealSnapshot(receipt);
  }
}
}  // namespace s3_d3::ecs_contact

GZ_ADD_PLUGIN(s3_d3::ecs_contact::ContactSensorDiagnosticSystem, gz::sim::System,
    s3_d3::ecs_contact::ContactSensorDiagnosticSystem::ISystemConfigure,
    s3_d3::ecs_contact::ContactSensorDiagnosticSystem::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(s3_d3::ecs_contact::ContactSensorDiagnosticSystem,
    "s3_d3::ecs_contact::ContactSensorDiagnosticSystem")
