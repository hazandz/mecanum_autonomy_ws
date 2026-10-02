#include "s3_d3_ecs_contact_diagnostic/collector.hh"

#include <charconv>
#include <chrono>
#include <map>
#include <string_view>

namespace s3_d3::ecs_contact
{
namespace
{
std::int64_t SteadyNowNs()
{
  return std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count();
}

bool ParsePositiveInt64(const std::string &_text, std::int64_t *_value)
{
  std::int64_t parsed = 0;
  const auto result = std::from_chars(_text.data(), _text.data() + _text.size(), parsed);
  if (result.ec != std::errc{} || result.ptr != _text.data() + _text.size() || parsed <= 0) return false;
  *_value = parsed;
  return true;
}

bool AddArgument(std::map<std::string, std::string> *_arguments, const std::string &_key,
    const std::string &_value)
{ return _arguments->emplace(_key, _value).second; }

bool Required(const std::map<std::string, std::string> &_arguments, const std::string &_key,
    std::string *_value)
{
  const auto iterator = _arguments.find(_key);
  if (iterator == _arguments.end() || iterator->second.empty()) return false;
  *_value = iterator->second;
  return true;
}
}  // namespace

CollectorLifecycle::CollectorLifecycle(DiagnosticConfig _config,
    std::filesystem::path _output_directory, NowSteadyNs _now_steady_ns)
    : config_(std::move(_config)), output_directory_(std::move(_output_directory)),
      now_steady_ns_(std::move(_now_steady_ns))
{
  receipt_deadline_steady_ns_ = now_steady_ns_() + config_.collector_receipt_wait_timeout_steady_ns;
}

bool CollectorLifecycle::SealOuterFailure(CollectorOutcome _outcome, const std::string &_reason)
{
  if (outcome_ != CollectorOutcome::kWaiting) return false;
  outcome_ = _outcome;
  static_cast<void>(DurableReceiptStore::PersistFailure(output_directory_, config_, _reason, nullptr));
  return false;
}

bool CollectorLifecycle::HandleRaw(const char *_data, std::size_t _size, const std::string &_topic,
    const std::string &_type)
{
  if (outcome_ != CollectorOutcome::kWaiting) return false;
  const auto expected_type = EcsContactSensorDiagnosticReceipt::descriptor()->full_name();
  if (!_data || _size == 0U || _topic != config_.receipt_topic || _type != expected_type)
    return SealOuterFailure(CollectorOutcome::kInvalidReceipt, "INVALID_RECEIPT_TYPE_OR_TOPIC");
  const std::string raw(_data, _size);
  EcsContactSensorDiagnosticReceipt receipt;
  if (!receipt.ParseFromArray(raw.data(), static_cast<int>(raw.size())) ||
      !ValidateReceipt(receipt, config_, nullptr))
    return SealOuterFailure(CollectorOutcome::kInvalidReceipt, "INVALID_RECEIPT_SCHEMA_OR_PROVENANCE");
  const auto persist_deadline = now_steady_ns_() + config_.collector_persist_timeout_steady_ns;
  if (!DurableReceiptStore::PersistAccepted(output_directory_, config_, receipt, raw, nullptr,
      DurableReceiptStore::FailurePoint::kNone, now_steady_ns_, persist_deadline))
    return SealOuterFailure(CollectorOutcome::kPersistenceFailure, "INVALID_EVIDENCE_PERSISTENCE_FAILURE");
  outcome_ = CollectorOutcome::kPersisted;
  return true;
}

void CollectorLifecycle::ExpireIfNeeded()
{
  if (outcome_ == CollectorOutcome::kWaiting && now_steady_ns_() >= receipt_deadline_steady_ns_)
    static_cast<void>(SealOuterFailure(CollectorOutcome::kReceiptUnconfirmed, "ECS_RECEIPT_UNCONFIRMED"));
}
CollectorOutcome CollectorLifecycle::Outcome() const { return outcome_; }
bool CollectorLifecycle::IsTerminal() const { return outcome_ != CollectorOutcome::kWaiting; }

bool ParseCollectorCommandLine(int _argc, char **_argv, CollectorCommandLine *_command_line,
    std::string *_reason)
{
  if (!_command_line || _argc < 2 || std::string_view(_argv[1]) != "--runtime-collector") {
    if (_reason) *_reason = "INVALID_COLLECTOR_RUNTIME_CONFIG";
    return false;
  }
  std::map<std::string, std::string> arguments;
  for (int index = 2; index < _argc; index += 2) {
    if (index + 1 >= _argc || std::string_view(_argv[index]).rfind("--", 0) != 0 ||
        !AddArgument(&arguments, _argv[index], _argv[index + 1])) {
      if (_reason) *_reason = "INVALID_COLLECTOR_RUNTIME_CONFIG";
      return false;
    }
  }
  auto &config = _command_line->config;
  std::string value;
  const bool strings = Required(arguments, "--receipt-topic", &config.receipt_topic) &&
      Required(arguments, "--run-id", &config.run_id) && Required(arguments, "--world-name", &config.world_name) &&
      Required(arguments, "--model-name", &config.model_name) && Required(arguments, "--link-name", &config.link_name) &&
      Required(arguments, "--sensor-name", &config.sensor_name) &&
      Required(arguments, "--plugin-source-sha256", &config.plugin_source_sha256) &&
      Required(arguments, "--plugin-binary-sha256", &config.plugin_binary_sha256) &&
      Required(arguments, "--collector-source-sha256", &config.collector_source_sha256) &&
      Required(arguments, "--collector-binary-sha256", &config.collector_binary_sha256) &&
      Required(arguments, "--base-world-template-sha256", &config.base_world_template_sha256) && Required(arguments, "--native-model-sha256", &config.native_model_sha256) &&
      Required(arguments, "--output-dir", &value);
  _command_line->output_directory = value;
  const bool timeouts = strings && Required(arguments, "--system-wait-timeout-sim-time-ns", &value) && ParsePositiveInt64(value, &config.system_wait_timeout_sim_time_ns) &&
      Required(arguments, "--system-delivery-wait-timeout-steady-ns", &value) && ParsePositiveInt64(value, &config.system_delivery_wait_timeout_steady_ns) &&
      Required(arguments, "--collector-receipt-wait-timeout-steady-ns", &value) && ParsePositiveInt64(value, &config.collector_receipt_wait_timeout_steady_ns) &&
      Required(arguments, "--collector-persist-timeout-steady-ns", &value) && ParsePositiveInt64(value, &config.collector_persist_timeout_steady_ns);
  if (!timeouts || !_command_line->output_directory.is_absolute() || !ValidateConfig(config, _reason)) {
    if (_reason && _reason->empty()) *_reason = "INVALID_COLLECTOR_RUNTIME_CONFIG";
    return false;
  }
  return true;
}

ReceiptCollector::ReceiptCollector(DiagnosticConfig _config, std::filesystem::path _output_directory)
    : config_(std::move(_config)), lifecycle_(config_, std::move(_output_directory), SteadyNowNs) {}

bool ReceiptCollector::Subscribe()
{
  const auto exact_type = EcsContactSensorDiagnosticReceipt::descriptor()->full_name();
  return ValidateConfig(config_, nullptr) && node_.SubscribeRaw(config_.receipt_topic,
      [this](const char *_data, std::size_t _size, const gz::transport::MessageInfo &_info) {
        HandleRaw(_data, _size, _info);
      }, exact_type);
}

void ReceiptCollector::HandleRaw(const char *_data, std::size_t _size, const gz::transport::MessageInfo &_info)
{
  std::lock_guard<std::mutex> lock(mutex_);
  static_cast<void>(lifecycle_.HandleRaw(_data, _size, _info.Topic(), _info.Type()));
  terminal_cv_.notify_all();
}

int ReceiptCollector::WaitForTerminal()
{
  std::unique_lock<std::mutex> lock(mutex_);
  while (!lifecycle_.IsTerminal()) {
    terminal_cv_.wait_for(lock, std::chrono::milliseconds(10));
    lifecycle_.ExpireIfNeeded();
  }
  return lifecycle_.Outcome() == CollectorOutcome::kPersisted ? 0 : 3;
}

bool ReceiptCollector::Accepted() const
{
  std::lock_guard<std::mutex> lock(mutex_);
  return lifecycle_.Outcome() == CollectorOutcome::kPersisted;
}
}  // namespace s3_d3::ecs_contact
