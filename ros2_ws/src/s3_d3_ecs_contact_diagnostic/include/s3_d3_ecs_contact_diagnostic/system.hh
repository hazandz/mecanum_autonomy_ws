#ifndef S3_D3_ECS_CONTACT_DIAGNOSTIC_SYSTEM_HH_
#define S3_D3_ECS_CONTACT_DIAGNOSTIC_SYSTEM_HH_

#include <chrono>
#include <optional>

#include <gz/sim/System.hh>
#include <gz/transport/Node.hh>

#include "s3_d3_ecs_contact_diagnostic/core.hh"

namespace s3_d3::ecs_contact
{
class ContactSensorDiagnosticSystem final : public gz::sim::System,
    public gz::sim::ISystemConfigure, public gz::sim::ISystemPostUpdate {
  public: void Configure(const gz::sim::Entity &,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gz::sim::EntityComponentManager &,
      gz::sim::EventManager &) final;
  public: void PostUpdate(const gz::sim::UpdateInfo &,
      const gz::sim::EntityComponentManager &_ecm) final;
  private: bool configured_{};
  private: gz::sim::Entity world_entity_{};
  private: bool config_valid_{};
  private: DiagnosticConfig config_;
  private: gz::transport::Node node_;
  private: gz::transport::Node::Publisher publisher_;
  private: DeliveryGate gate_;
  private: std::optional<std::chrono::steady_clock::time_point> first_postupdate_;
  private: std::optional<std::chrono::steady_clock::time_point> delivery_start_;
  private: std::optional<std::chrono::nanoseconds> first_sim_time_;
};
}  // namespace s3_d3::ecs_contact

#endif
