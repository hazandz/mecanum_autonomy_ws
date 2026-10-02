#include "s3_d3_ecs_contact_diagnostic/core.hh"

#include <array>
#include <cerrno>
#include <cctype>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <google/protobuf/io/coded_stream.h>
#include <google/protobuf/io/zero_copy_stream_impl_lite.h>
#include <linux/fs.h>
#include <openssl/evp.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

namespace s3_d3::ecs_contact
{
namespace
{
bool ValidOpaque(const std::string &_value)
{
  if (_value.empty() || _value.find("..") != std::string::npos) return false;
  for (const unsigned char c : _value) {
    if (!(std::isalnum(c) || c == '_' || c == '-')) return false;
  }
  return true;
}

bool ValidTopic(const std::string &_value)
{
  if (_value.size() < 2 || _value.front() != '/' || _value.find("//") != std::string::npos ||
      _value.find("..") != std::string::npos) return false;
  for (const unsigned char c : _value) {
    if (std::iscntrl(c) || !(std::isalnum(c) || c == '/' || c == '_' || c == '-')) return false;
  }
  return true;
}

bool ValidSha(const std::string &_value)
{
  if (_value.size() != 64) return false;
  for (const char c : _value) {
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  }
  return true;
}

bool SafeDirectory(const std::filesystem::path &_directory)
{
  if (_directory.empty()) return false;
  std::error_code error;
  const auto absolute = std::filesystem::absolute(_directory, error);
  if (error || !std::filesystem::is_directory(absolute, error) || error) return false;
  auto current = absolute.root_path();
  for (const auto &part : absolute.relative_path()) {
    current /= part;
    if (std::filesystem::is_symlink(current, error) || error) return false;
  }
  return true;
}

bool CloseExactlyOnce(int *_fd, bool _forced_failure)
{
  if (*_fd < 0) return false;
  const int descriptor = *_fd;
  *_fd = -1;
  const int result = close(descriptor);
  // close(2) must not be retried on EINTR because descriptor reuse is possible.
  return !_forced_failure && result == 0;
}

bool WriteAll(int _fd, const std::string &_data, bool _forced_failure, bool _simulate_eintr = false)
{
  std::size_t written = 0;
  bool interrupted = false;
  while (written < _data.size()) {
    if (_simulate_eintr && !interrupted) { errno = EINTR; interrupted = true; continue; }
    const ssize_t result = write(_fd, _data.data() + written, _data.size() - written);
    if (result < 0 && errno == EINTR) continue;
    if (result <= 0 || _forced_failure) return false;
    written += static_cast<std::size_t>(result);
  }
  return true;
}

bool WriteStageFile(const std::filesystem::path &_staging, const std::string &_name,
    const std::string &_data, DurableReceiptStore::FailurePoint _point,
    DurableReceiptStore::FailurePoint _write_point, std::string *_reason)
{
  const auto path = _staging / _name;
  int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  if (fd < 0) { if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE"; return false; }
  const bool wrote = WriteAll(fd, _data, _point == _write_point, _point == DurableReceiptStore::FailurePoint::kWriteEintrOnce);
  const bool synced = wrote && _point != DurableReceiptStore::FailurePoint::kFileFsync && fsync(fd) == 0;
  const bool closed = CloseExactlyOnce(&fd, _point == DurableReceiptStore::FailurePoint::kFileClose);
  if (!wrote || !synced || !closed) {
    unlink(path.c_str());
    if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE";
    return false;
  }
  return true;
}

bool FsyncDirectory(const std::filesystem::path &_path)
{
  int fd = open(_path.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
  if (fd < 0) return false;
  const bool synced = fsync(fd) == 0;
  const bool closed = CloseExactlyOnce(&fd, false);
  return synced && closed;
}

bool RenameNoReplace(const std::filesystem::path &_from, const std::filesystem::path &_to)
{
#ifdef SYS_renameat2
  return syscall(SYS_renameat2, AT_FDCWD, _from.c_str(), AT_FDCWD, _to.c_str(), RENAME_NOREPLACE) == 0;
#else
  static_cast<void>(_from); static_cast<void>(_to);
  errno = ENOSYS;
  return false;
#endif
}

std::string JsonEscape(const std::string &_value)
{
  static constexpr char kHex[] = "0123456789abcdef";
  std::string output;
  for (const unsigned char c : _value) {
    switch (c) {
      case '"': output += "\\\""; break;
      case '\\': output += "\\\\"; break;
      case '\b': output += "\\b"; break;
      case '\f': output += "\\f"; break;
      case '\n': output += "\\n"; break;
      case '\r': output += "\\r"; break;
      case '\t': output += "\\t"; break;
      default:
        if (c < 0x20U) { output += "\\u00"; output += kHex[c >> 4U]; output += kHex[c & 0x0fU]; }
        else output += static_cast<char>(c);
    }
  }
  return output;
}

bool IdsMatchCounts(const EcsContactSensorDiagnosticReceipt &_r)
{
  if (!_r.world_id_present() || _r.world_id() == 0U) return false;
  if ((_r.model_exact_count() == 1U) != _r.model_id_present()) return false;
  if (!_r.model_id_present() && (_r.link_exact_count() != 0U || _r.sensor_exact_count() != 0U || _r.collision_exact_count() != 0U)) return false;
  if ((_r.link_exact_count() == 1U && _r.model_id_present()) != _r.link_id_present()) return false;
  if (!_r.link_id_present() && (_r.sensor_exact_count() != 0U || _r.collision_exact_count() != 0U)) return false;
  if ((_r.sensor_exact_count() == 1U && _r.link_id_present()) != _r.sensor_id_present()) return false;
  if ((_r.collision_exact_count() == 1U && !_r.configured_collision_target().empty()) != _r.collision_id_present()) return false;
  if (_r.model_id_present() && _r.model_id() == 0U) return false;
  if (_r.link_id_present() && (_r.link_id() == 0U || !_r.link_parent_id_present() || _r.link_parent_id() == 0U)) return false;
  if (_r.sensor_id_present() && (_r.sensor_id() == 0U || !_r.sensor_parent_id_present() || _r.sensor_parent_id() == 0U)) return false;
  if (_r.collision_id_present() && (_r.collision_id() == 0U || !_r.collision_parent_id_present() || _r.collision_parent_id() == 0U)) return false;
  if (_r.link_id_present() != _r.link_parent_id_present()) return false;
  if (_r.sensor_id_present() != _r.sensor_parent_id_present()) return false;
  if (_r.collision_id_present() != _r.collision_parent_id_present()) return false;
  return true;
}
}  // namespace

bool ValidateConfig(const DiagnosticConfig &_config, std::string *_reason)
{
  const bool valid = ValidTopic(_config.receipt_topic) && ValidOpaque(_config.run_id) &&
      ValidOpaque(_config.world_name) && ValidOpaque(_config.model_name) &&
      ValidOpaque(_config.link_name) && ValidOpaque(_config.sensor_name) &&
      ValidSha(_config.plugin_source_sha256) && ValidSha(_config.plugin_binary_sha256) &&
      ValidSha(_config.collector_source_sha256) && ValidSha(_config.collector_binary_sha256) &&
      ValidSha(_config.base_world_template_sha256) && ValidSha(_config.native_model_sha256) &&
      _config.system_wait_timeout_sim_time_ns > 0 &&
      _config.system_delivery_wait_timeout_steady_ns > 0 &&
      _config.collector_receipt_wait_timeout_steady_ns > 0 &&
      _config.collector_persist_timeout_steady_ns > 0;
  if (!valid && _reason) *_reason = "INVALID_IMMUTABLE_DIAGNOSTIC_CONFIG";
  return valid;
}

bool IsAllowedTerminalStatus(EcsContactSensorDiagnosticReceipt::TerminalStatus _status)
{
  switch (_status) {
    case EcsContactSensorDiagnosticReceipt::ECS_MODEL_UNCONFIRMED:
    case EcsContactSensorDiagnosticReceipt::ECS_LINK_UNCONFIRMED:
    case EcsContactSensorDiagnosticReceipt::ECS_SENSOR_UNCONFIRMED:
    case EcsContactSensorDiagnosticReceipt::ECS_CONTACT_COMPONENT_MISSING:
    case EcsContactSensorDiagnosticReceipt::ECS_CONTACT_CONFIGURATION_INCOMPLETE:
    case EcsContactSensorDiagnosticReceipt::ECS_TARGET_COLLISION_CHILD_UNCONFIRMED:
    case EcsContactSensorDiagnosticReceipt::ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED:
      return true;
    default: return false;
  }
}

EcsContactSensorDiagnosticReceipt::ReasonCode ExpectedReasonCode(
    EcsContactSensorDiagnosticReceipt::TerminalStatus _status)
{
  switch (_status) {
    case EcsContactSensorDiagnosticReceipt::ECS_MODEL_UNCONFIRMED: return EcsContactSensorDiagnosticReceipt::MODEL_EXACT_COUNT_NOT_ONE;
    case EcsContactSensorDiagnosticReceipt::ECS_LINK_UNCONFIRMED: return EcsContactSensorDiagnosticReceipt::LINK_EXACT_COUNT_OR_PARENT_INVALID;
    case EcsContactSensorDiagnosticReceipt::ECS_SENSOR_UNCONFIRMED: return EcsContactSensorDiagnosticReceipt::SENSOR_EXACT_COUNT_OR_PARENT_INVALID;
    case EcsContactSensorDiagnosticReceipt::ECS_CONTACT_COMPONENT_MISSING: return EcsContactSensorDiagnosticReceipt::CONTACT_COMPONENT_NOT_PRESENT;
    case EcsContactSensorDiagnosticReceipt::ECS_CONTACT_CONFIGURATION_INCOMPLETE: return EcsContactSensorDiagnosticReceipt::CONTACT_ELEMENT_OR_COLLISION_INVALID;
    case EcsContactSensorDiagnosticReceipt::ECS_TARGET_COLLISION_CHILD_UNCONFIRMED: return EcsContactSensorDiagnosticReceipt::COLLISION_EXACT_COUNT_OR_PARENT_INVALID;
    case EcsContactSensorDiagnosticReceipt::ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED: return EcsContactSensorDiagnosticReceipt::EXACT_CHAIN_OBSERVED;
    default: return EcsContactSensorDiagnosticReceipt::REASON_CODE_UNSPECIFIED;
  }
}

EcsContactSensorDiagnosticReceipt EvaluateHierarchy(
    const DiagnosticConfig &_config, const HierarchyObservation &_o)
{
  EcsContactSensorDiagnosticReceipt receipt;
  receipt.set_schema_version(kReceiptSchemaVersion);
  receipt.set_run_id(_config.run_id); receipt.set_world_name(_config.world_name);
  receipt.set_model_name(_config.model_name); receipt.set_link_name(_config.link_name);
  receipt.set_sensor_name(_config.sensor_name); receipt.set_model_exact_count(_o.model_exact_count);
  receipt.set_link_exact_count(_o.link_exact_count); receipt.set_sensor_exact_count(_o.sensor_exact_count);
  receipt.set_collision_exact_count(_o.collision_exact_count);
  receipt.set_world_id(_o.world_id); receipt.set_world_id_present(_o.world_id_present);
  receipt.set_model_id(_o.model_id); receipt.set_model_id_present(_o.model_id_present);
  receipt.set_link_id(_o.link_id); receipt.set_link_id_present(_o.link_id_present);
  receipt.set_sensor_id(_o.sensor_id); receipt.set_sensor_id_present(_o.sensor_id_present);
  receipt.set_collision_id(_o.collision_id); receipt.set_collision_id_present(_o.collision_id_present);
  receipt.set_link_parent_id(_o.link_parent_id); receipt.set_link_parent_id_present(_o.link_parent_id_present);
  receipt.set_sensor_parent_id(_o.sensor_parent_id); receipt.set_sensor_parent_id_present(_o.sensor_parent_id_present);
  receipt.set_collision_parent_id(_o.collision_parent_id); receipt.set_collision_parent_id_present(_o.collision_parent_id_present);
  receipt.set_collision_name(_o.collision_name);
  receipt.set_configured_collision_target(_o.configured_collision_target);
  receipt.set_hook_name("PostUpdate"); receipt.set_system_wait_timeout_sim_time_ns(_config.system_wait_timeout_sim_time_ns);
  receipt.set_system_delivery_wait_timeout_steady_ns(_config.system_delivery_wait_timeout_steady_ns);
  receipt.set_collector_receipt_wait_timeout_steady_ns(_config.collector_receipt_wait_timeout_steady_ns);
  receipt.set_collector_persist_timeout_steady_ns(_config.collector_persist_timeout_steady_ns);
  receipt.set_plugin_source_sha256(_config.plugin_source_sha256); receipt.set_plugin_binary_sha256(_config.plugin_binary_sha256);
  receipt.set_collector_source_sha256(_config.collector_source_sha256); receipt.set_collector_binary_sha256(_config.collector_binary_sha256);
  receipt.set_base_world_template_sha256(_config.base_world_template_sha256); receipt.set_native_model_sha256(_config.native_model_sha256);
  receipt.set_sealed_once(true);
  if (_o.model_exact_count != 1U) receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_MODEL_UNCONFIRMED);
  else if (_o.link_exact_count != 1U || !_o.link_parent_matches) receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_LINK_UNCONFIRMED);
  else if (_o.sensor_exact_count != 1U || !_o.sensor_parent_matches) receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_SENSOR_UNCONFIRMED);
  else if (!_o.contact_component_present) receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_CONTACT_COMPONENT_MISSING);
  else if (!_o.contact_element_present || !_o.collision_element_present || !ValidOpaque(_o.configured_collision_target)) receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_CONTACT_CONFIGURATION_INCOMPLETE);
  else if (_o.collision_exact_count != 1U || !_o.collision_parent_matches) receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_TARGET_COLLISION_CHILD_UNCONFIRMED);
  else receipt.set_terminal_status(EcsContactSensorDiagnosticReceipt::ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED);
  receipt.set_reason_code(ExpectedReasonCode(receipt.terminal_status()));
  return receipt;
}

bool ValidateReceipt(const EcsContactSensorDiagnosticReceipt &_receipt,
                     const DiagnosticConfig &_config, std::string *_reason)
{
  const bool valid = ValidateConfig(_config, nullptr) && _receipt.schema_version() == kReceiptSchemaVersion &&
      ValidOpaque(_receipt.run_id()) && _receipt.run_id() == _config.run_id &&
      IsAllowedTerminalStatus(_receipt.terminal_status()) &&
      _receipt.reason_code() == ExpectedReasonCode(_receipt.terminal_status()) &&
      _receipt.world_name() == _config.world_name && _receipt.model_name() == _config.model_name &&
      _receipt.link_name() == _config.link_name && _receipt.sensor_name() == _config.sensor_name &&
      _receipt.hook_name() == "PostUpdate" && _receipt.sealed_once() &&
      _receipt.plugin_source_sha256() == _config.plugin_source_sha256 &&
      _receipt.plugin_binary_sha256() == _config.plugin_binary_sha256 &&
      _receipt.collector_source_sha256() == _config.collector_source_sha256 &&
      _receipt.collector_binary_sha256() == _config.collector_binary_sha256 &&
      _receipt.base_world_template_sha256() == _config.base_world_template_sha256 && _receipt.native_model_sha256() == _config.native_model_sha256 &&
      _receipt.system_wait_timeout_sim_time_ns() == _config.system_wait_timeout_sim_time_ns &&
      _receipt.system_delivery_wait_timeout_steady_ns() == _config.system_delivery_wait_timeout_steady_ns &&
      _receipt.collector_receipt_wait_timeout_steady_ns() == _config.collector_receipt_wait_timeout_steady_ns &&
      _receipt.collector_persist_timeout_steady_ns() == _config.collector_persist_timeout_steady_ns &&
      _receipt.first_postupdate_sim_time_present() && _receipt.terminal_sim_time_present() &&
      _receipt.first_postupdate_steady_time_present() && _receipt.terminal_steady_time_present() &&
      _receipt.first_postupdate_sim_time_ns() >= 0 && _receipt.terminal_sim_time_ns() >= _receipt.first_postupdate_sim_time_ns() &&
      _receipt.first_postupdate_steady_time_ns() >= 0 && _receipt.terminal_steady_time_ns() >= _receipt.first_postupdate_steady_time_ns() &&
      IdsMatchCounts(_receipt);
  if (!valid && _reason) *_reason = "INVALID_RECEIPT_SCHEMA_OR_PROVENANCE";
  return valid;
}

bool SerializeDeterministic(const EcsContactSensorDiagnosticReceipt &_receipt, std::string *_bytes)
{
  if (!_bytes) return false;
  _bytes->assign(_receipt.ByteSizeLong(), '\0');
  google::protobuf::io::ArrayOutputStream output(_bytes->data(), static_cast<int>(_bytes->size()));
  google::protobuf::io::CodedOutputStream coded(&output); coded.SetSerializationDeterministic(true);
  return _receipt.SerializeToCodedStream(&coded);
}

std::string Sha256Hex(const std::string &_bytes)
{
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{}; unsigned int size = 0;
  EVP_MD_CTX *context = EVP_MD_CTX_new();
  if (!context || EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1 ||
      EVP_DigestUpdate(context, _bytes.data(), _bytes.size()) != 1 ||
      EVP_DigestFinal_ex(context, digest.data(), &size) != 1) { EVP_MD_CTX_free(context); return {}; }
  EVP_MD_CTX_free(context); static constexpr char hex[] = "0123456789abcdef"; std::string result;
  for (unsigned int i = 0; i < size; ++i) { result += hex[digest[i] >> 4U]; result += hex[digest[i] & 0x0fU]; }
  return result;
}

bool DeliveryGate::SealSnapshot(const EcsContactSensorDiagnosticReceipt &_receipt)
{
  if (state_ != DeliveryState::kWaitingForTarget || !IsAllowedTerminalStatus(_receipt.terminal_status())) return false;
  snapshot_ = _receipt; state_ = DeliveryState::kSnapshotSealed; return true;
}
bool DeliveryGate::CanPublish(bool _has_connections) const
{ return state_ == DeliveryState::kSnapshotSealed && _has_connections && publish_attempts_ == 0U; }
bool DeliveryGate::CompletePublish(bool _publish_succeeded)
{
  if (state_ != DeliveryState::kSnapshotSealed || publish_attempts_ != 0U) return false;
  ++publish_attempts_; outcome_ = _publish_succeeded ? DeliveryOutcome::kPublished : DeliveryOutcome::kPublishFailed;
  state_ = DeliveryState::kDeliverySealed; return _publish_succeeded;
}
void DeliveryGate::SealDeliveryWithoutPublish()
{ if (state_ == DeliveryState::kSnapshotSealed) { outcome_ = DeliveryOutcome::kConnectionDeadlineExpired; state_ = DeliveryState::kDeliverySealed; } }
DeliveryState DeliveryGate::State() const { return state_; }
std::uint32_t DeliveryGate::PublishAttempts() const { return publish_attempts_; }
DeliveryOutcome DeliveryGate::Outcome() const { return outcome_; }
const std::optional<EcsContactSensorDiagnosticReceipt> &DeliveryGate::Snapshot() const { return snapshot_; }

bool DurableReceiptStore::PersistAccepted(const std::filesystem::path &_directory,
    const DiagnosticConfig &_config, const EcsContactSensorDiagnosticReceipt &_receipt,
    const std::string &_raw, std::string *_reason, FailurePoint _failure,
    const std::function<std::int64_t()> &_now_steady_ns, std::int64_t _deadline_steady_ns)
{
  const auto timed_out = [&]() { return _now_steady_ns && _deadline_steady_ns > 0 && _now_steady_ns() > _deadline_steady_ns; };
  if (!SafeDirectory(_directory) || _raw.empty() || !ValidateReceipt(_receipt, _config, nullptr) || timed_out()) {
    if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE";
    return false;
  }
  std::string normalized;
  if (!SerializeDeterministic(_receipt, &normalized)) { if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE"; return false; }
  const std::string raw_hash = Sha256Hex(_raw);
  if (!ValidSha(raw_hash)) { if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE"; return false; }
  const auto staging = _directory / (".ecs-contact-stage-" + _receipt.run_id() + "-" + std::to_string(getpid()) + "-" +
      std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  if (mkdir(staging.c_str(), 0700) != 0) {
    if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE";
    return false;
  }
  const std::string json = "{\"schema_version\":1,\"run_id\":\"" + JsonEscape(_receipt.run_id()) + "\",\"terminal_status\":\"" +
      EcsContactSensorDiagnosticReceipt::TerminalStatus_Name(_receipt.terminal_status()) + "\"}\n";
  const std::string metadata = "{\"schema_version\":1,\"expected_topic\":\"" + JsonEscape(_config.receipt_topic) +
      "\",\"expected_run_id\":\"" + JsonEscape(_config.run_id) + "\",\"plugin_source_sha256\":\"" +
      _config.plugin_source_sha256 + "\",\"plugin_binary_sha256\":\"" + _config.plugin_binary_sha256 +
      "\",\"collector_source_sha256\":\"" + _config.collector_source_sha256 + "\",\"collector_binary_sha256\":\"" +
      _config.collector_binary_sha256 + "\",\"base_world_template_sha256\":\"" + _config.base_world_template_sha256 + "\",\"native_model_sha256\":\"" +
      _config.native_model_sha256 + "\",\"receive_steady_ns\":" + std::to_string(_now_steady_ns ? _now_steady_ns() : 0) +
      ",\"collector_receipt_wait_timeout_steady_ns\":" + std::to_string(_config.collector_receipt_wait_timeout_steady_ns) +
      ",\"collector_persist_timeout_steady_ns\":" + std::to_string(_config.collector_persist_timeout_steady_ns) +
      ",\"raw_transport_payload_sha256\":\"" + raw_hash + "\",\"outer_persistence_status\":\"PERSISTED\"}\n";
  const bool files = !timed_out() && WriteStageFile(staging, "ecs_contact_receipt.raw.pb", _raw, _failure, FailurePoint::kRawWrite, _reason) &&
      !timed_out() && WriteStageFile(staging, "ecs_contact_receipt.raw.sha256", raw_hash + "\n", _failure, FailurePoint::kRawHashWrite, _reason) &&
      !timed_out() && WriteStageFile(staging, "ecs_contact_receipt.normalized.pb", normalized, _failure, FailurePoint::kNormalizedWrite, _reason) &&
      !timed_out() && WriteStageFile(staging, "ecs_contact_receipt.json", json, _failure, FailurePoint::kJsonWrite, _reason) &&
      !timed_out() && WriteStageFile(staging, "ecs_contact_receipt_collector_metadata.json", metadata, _failure, FailurePoint::kMetadataWrite, _reason);
  const bool staged = files && !timed_out() && _failure != FailurePoint::kStagingDirectoryFsync && FsyncDirectory(staging);
  const auto final = _directory / "ecs_contact_receipt_bundle";
  const bool committed = staged && !timed_out() && _failure != FailurePoint::kCommit && RenameNoReplace(staging, final) && FsyncDirectory(_directory);
  if (!committed) {
    std::error_code ignored; std::filesystem::remove_all(staging, ignored);
    if (_reason) *_reason = "INVALID_EVIDENCE_PERSISTENCE_FAILURE";
    return false;
  }
  return true;
}

bool DurableReceiptStore::PersistFailure(const std::filesystem::path &_directory,
    const DiagnosticConfig &_config, const std::string &_reason, std::string *_error)
{
  if (!SafeDirectory(_directory) || !ValidateConfig(_config, nullptr)) { if (_error) *_error = "INVALID_EVIDENCE_PERSISTENCE_FAILURE"; return false; }
  const auto path = _directory / "ecs_contact_receipt_failure.json";
  int fd = open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
  const std::string body = "{\"run_id\":\"" + JsonEscape(_config.run_id) + "\",\"expected_topic\":\"" +
      JsonEscape(_config.receipt_topic) + "\",\"outer_reason\":\"" + JsonEscape(_reason) + "\"}\n";
  const bool ok = fd >= 0 && WriteAll(fd, body, false) && fsync(fd) == 0 && CloseExactlyOnce(&fd, false) && FsyncDirectory(_directory);
  if (fd >= 0) CloseExactlyOnce(&fd, false);
  if (!ok && _error) *_error = "INVALID_EVIDENCE_PERSISTENCE_FAILURE";
  return ok;
}
}  // namespace s3_d3::ecs_contact
