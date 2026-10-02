#ifndef S3_D3_ECS_CONTACT_DIAGNOSTIC_CORE_HH_
#define S3_D3_ECS_CONTACT_DIAGNOSTIC_CORE_HH_

#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>

#include "ecs_contact_sensor_diagnostic_receipt.pb.h"

namespace s3_d3::ecs_contact
{
constexpr std::uint32_t kReceiptSchemaVersion = 1;

struct DiagnosticConfig {
  std::string receipt_topic;
  std::string run_id;
  std::string world_name;
  std::string model_name;
  std::string link_name;
  std::string sensor_name;
  std::string plugin_source_sha256;
  std::string plugin_binary_sha256;
  std::string collector_source_sha256;
  std::string collector_binary_sha256;
  // SHA-256 of the immutable pre-render base-world template. It is never a
  // digest of the generated per-run world, avoiding a self-reference.
  std::string base_world_template_sha256;
  std::string native_model_sha256;
  std::int64_t system_wait_timeout_sim_time_ns{};
  std::int64_t system_delivery_wait_timeout_steady_ns{};
  std::int64_t collector_receipt_wait_timeout_steady_ns{};
  std::int64_t collector_persist_timeout_steady_ns{};
};

bool ValidateConfig(const DiagnosticConfig &_config, std::string *_reason);

struct HierarchyObservation {
  std::uint32_t model_exact_count{};
  std::uint32_t link_exact_count{};
  std::uint32_t sensor_exact_count{};
  std::uint32_t collision_exact_count{};
  std::uint64_t world_id{};
  std::uint64_t model_id{};
  std::uint64_t link_id{};
  std::uint64_t sensor_id{};
  std::uint64_t collision_id{};
  std::uint64_t link_parent_id{};
  std::uint64_t sensor_parent_id{};
  std::uint64_t collision_parent_id{};
  bool world_id_present{};
  bool model_id_present{};
  bool link_id_present{};
  bool sensor_id_present{};
  bool collision_id_present{};
  bool link_parent_id_present{};
  bool sensor_parent_id_present{};
  bool collision_parent_id_present{};
  std::string collision_name;
  bool link_parent_matches{};
  bool sensor_parent_matches{};
  bool collision_parent_matches{};
  bool contact_component_present{};
  bool contact_element_present{};
  bool collision_element_present{};
  std::string configured_collision_target;
};

EcsContactSensorDiagnosticReceipt EvaluateHierarchy(
    const DiagnosticConfig &_config, const HierarchyObservation &_observation);

bool IsAllowedTerminalStatus(EcsContactSensorDiagnosticReceipt::TerminalStatus _status);
EcsContactSensorDiagnosticReceipt::ReasonCode ExpectedReasonCode(
    EcsContactSensorDiagnosticReceipt::TerminalStatus _status);
bool ValidateReceipt(const EcsContactSensorDiagnosticReceipt &_receipt,
                     const DiagnosticConfig &_config, std::string *_reason);
bool SerializeDeterministic(const EcsContactSensorDiagnosticReceipt &_receipt,
                            std::string *_bytes);
std::string Sha256Hex(const std::string &_bytes);

enum class DeliveryState { kWaitingForTarget, kSnapshotSealed, kDeliverySealed };
enum class DeliveryOutcome { kNone, kPublished, kPublishFailed, kConnectionDeadlineExpired };
class DeliveryGate {
  public: bool SealSnapshot(const EcsContactSensorDiagnosticReceipt &_receipt);
  public: bool CanPublish(bool _has_connections) const;
  public: bool CompletePublish(bool _publish_succeeded);
  public: void SealDeliveryWithoutPublish();
  public: DeliveryState State() const;
  public: std::uint32_t PublishAttempts() const;
  public: DeliveryOutcome Outcome() const;
  public: const std::optional<EcsContactSensorDiagnosticReceipt> &Snapshot() const;
  private: DeliveryState state_{DeliveryState::kWaitingForTarget};
  private: std::uint32_t publish_attempts_{};
  private: DeliveryOutcome outcome_{DeliveryOutcome::kNone};
  private: std::optional<EcsContactSensorDiagnosticReceipt> snapshot_;
};

class DurableReceiptStore {
  public: enum class FailurePoint {
    kNone, kWriteEintrOnce, kRawWrite, kRawHashWrite, kNormalizedWrite, kJsonWrite, kMetadataWrite,
    kFileFsync, kFileClose, kStagingDirectoryFsync, kCommit};
  public: static bool PersistAccepted(const std::filesystem::path &_directory,
      const DiagnosticConfig &_config, const EcsContactSensorDiagnosticReceipt &_receipt,
      const std::string &_raw_bytes, std::string *_reason,
      FailurePoint _failure = FailurePoint::kNone,
      const std::function<std::int64_t()> &_now_steady_ns = {}, std::int64_t _deadline_steady_ns = 0);
  public: static bool PersistFailure(const std::filesystem::path &_directory,
      const DiagnosticConfig &_config, const std::string &_reason, std::string *_error);
};
}  // namespace s3_d3::ecs_contact

#endif
