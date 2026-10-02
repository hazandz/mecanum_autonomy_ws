#include "s3_d3_ecs_contact_diagnostic/run_spec.hh"

#include <array>
#include <charconv>
#include <cctype>
#include <set>
#include <map>
#include <string_view>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <openssl/evp.h>
#include <sys/stat.h>
#include <unistd.h>

#include <vector>

namespace s3_d3::ecs_contact
{
namespace
{
constexpr std::array<const char *, 17> kTokens = {
  "{{S3D3_RECEIPT_TOPIC}}", "{{S3D3_RUN_ID}}", "{{S3D3_WORLD_NAME}}",
  "{{S3D3_MODEL_NAME}}", "{{S3D3_LINK_NAME}}", "{{S3D3_SENSOR_NAME}}",
  "{{S3D3_PLUGIN_SOURCE_SHA256}}", "{{S3D3_PLUGIN_BINARY_SHA256}}",
  "{{S3D3_COLLECTOR_SOURCE_SHA256}}", "{{S3D3_COLLECTOR_BINARY_SHA256}}",
  "{{S3D3_BASE_WORLD_TEMPLATE_SHA256}}", "{{S3D3_NATIVE_MODEL_SHA256}}",
  "{{S3D3_SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS}}",
  "{{S3D3_SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS}}",
  "{{S3D3_COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS}}",
  "{{S3D3_COLLECTOR_PERSIST_TIMEOUT_STEADY_NS}}",
  "{{S3D3_PLUGIN_ALIAS}}"};

bool IsSafeTree(const std::filesystem::path &_path, bool _allow_missing_last)
{
  if (_path.empty() || !_path.is_absolute()) return false;
  std::error_code error;
  auto current = _path.root_path();
  const auto parts = _path.relative_path();
  std::size_t index = 0;
  const auto total = static_cast<std::size_t>(std::distance(parts.begin(), parts.end()));
  for (const auto &part : parts) {
    if (part == "..") return false;
    ++index;
    current /= part;
    const auto state = std::filesystem::symlink_status(current, error);
    if (error) return false;
    if (state.type() == std::filesystem::file_type::not_found) {
      return _allow_missing_last && index == total;
    }
    if (std::filesystem::is_symlink(state)) return false;
  }
  return true;
}

bool ReadRegular(const std::filesystem::path &_path, std::string *_data)
{
  std::error_code error;
  const auto absolute = std::filesystem::absolute(_path, error);
  if (error || !IsSafeTree(absolute, false) ||
      !std::filesystem::is_regular_file(absolute, error) || error) return false;
  const int fd = open(absolute.c_str(), O_RDONLY | O_NOFOLLOW);
  if (fd < 0) return false;
  _data->clear();
  std::array<char, 4096> buffer{};
  for (;;) {
    const ssize_t count = read(fd, buffer.data(), buffer.size());
    if (count < 0 && errno == EINTR) continue;
    if (count < 0) { close(fd); return false; }
    if (count == 0) break;
    _data->append(buffer.data(), static_cast<std::size_t>(count));
  }
  return close(fd) == 0;
}

std::string Hash(const std::string &_data)
{
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int length{};
  if (EVP_Digest(_data.data(), _data.size(), digest.data(), &length, EVP_sha256(), nullptr) != 1) return {};
  static constexpr char kHex[] = "0123456789abcdef";
  std::string result;
  result.reserve(length * 2U);
  for (unsigned int i = 0; i < length; ++i) {
    result += kHex[digest[i] >> 4U]; result += kHex[digest[i] & 0x0fU];
  }
  return result;
}

bool WriteAll(int _fd, const std::string &_data)
{
  std::size_t offset{};
  while (offset < _data.size()) {
    const auto result = write(_fd, _data.data() + offset, _data.size() - offset);
    if (result < 0 && errno == EINTR) continue;
    if (result <= 0) return false;
    offset += static_cast<std::size_t>(result);
  }
  return true;
}

bool IsSafeRunId(const std::string &_value)
{
  if (_value.size() < 8U || _value.size() > 128U) return false;
  for (const unsigned char c : _value) {
    if (!(std::isalnum(c) || c == '_' || c == '-')) return false;
  }
  return std::isalnum(static_cast<unsigned char>(_value.front())) != 0;
}

bool IsSha256(const std::string &_value)
{
  if (_value.size() != 64U) return false;
  for (const unsigned char c : _value) {
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  }
  return true;
}

bool ParsePositiveInt64(const std::string &_text, std::int64_t *_value)
{
  if (_text.empty() || _text.front() == '+' || _text.front() == '-') return false;
  const auto parsed = std::from_chars(_text.data(), _text.data() + _text.size(), *_value);
  return parsed.ec == std::errc{} && parsed.ptr == _text.data() + _text.size() && *_value > 0;
}

std::string EscapeJson(const std::string &_value)
{
  static constexpr char kHex[] = "0123456789abcdef";
  std::string result;
  for (const unsigned char c : _value) {
    switch (c) {
      case '"': result += "\\\""; break;
      case '\\': result += "\\\\"; break;
      case '\b': result += "\\b"; break;
      case '\f': result += "\\f"; break;
      case '\n': result += "\\n"; break;
      case '\r': result += "\\r"; break;
      case '\t': result += "\\t"; break;
      default:
        if (c < 0x20U) { result += "\\u00"; result += kHex[c >> 4U]; result += kHex[c & 0x0fU]; }
        else result += static_cast<char>(c);
    }
  }
  return result;
}

bool WriteNoReplace(const std::filesystem::path &_output, const std::string &_data)
{
  std::error_code error;
  if (!IsSafeTree(_output.parent_path(), false) ||
      !std::filesystem::is_directory(_output.parent_path(), error) || error ||
      std::filesystem::exists(_output, error) || error) return false;
  std::string temporary = (_output.parent_path() / ".s3d3-receipt-XXXXXX").string();
  std::vector<char> mutable_name(temporary.begin(), temporary.end());
  mutable_name.push_back('\0');
  const int fd = mkstemp(mutable_name.data());
  if (fd < 0) return false;
  const std::filesystem::path staging(mutable_name.data());
  const bool wrote = WriteAll(fd, _data);
  const bool synced = wrote && fsync(fd) == 0;
  const bool closed = close(fd) == 0;
  if (!wrote || !synced || !closed || link(staging.c_str(), _output.c_str()) != 0) {
    unlink(staging.c_str());
    return false;
  }
  unlink(staging.c_str());
  const int directory_fd = open(_output.parent_path().c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW);
  const bool directory_synced = directory_fd >= 0 && fsync(directory_fd) == 0 && close(directory_fd) == 0;
  return directory_synced;
}

bool ReplaceExactlyOnce(std::string *_text, const std::string &_token,
                        const std::string &_value)
{
  const auto first = _text->find(_token);
  if (first == std::string::npos || _text->find(_token, first + _token.size()) != std::string::npos) return false;
  _text->replace(first, _token.size(), _value);
  return true;
}
}  // namespace

bool ParseWorldRendererCommandLine(int _argc, char **_argv,
                                   DiagnosticRunSpec *_spec, std::string *_reason)
{
  if (!_spec || _argc < 2 || std::string_view(_argv[1]) != "--render-diagnostic-world") {
    if (_reason) *_reason = "INVALID_RENDERER_COMMAND_LINE";
    return false;
  }
  static const std::set<std::string> allowed = {
    "--template", "--output", "--result", "--receipt-topic", "--run-id", "--world-name",
    "--model-name", "--link-name", "--sensor-name", "--plugin-source-sha256",
    "--plugin-binary-sha256", "--collector-source-sha256", "--collector-binary-sha256",
    "--base-world-template-sha256", "--native-model-sha256", "--system-wait-timeout-sim-time-ns",
    "--system-delivery-wait-timeout-steady-ns", "--collector-receipt-wait-timeout-steady-ns",
    "--collector-persist-timeout-steady-ns"};
  std::map<std::string, std::string> args;
  for (int index = 2; index < _argc; index += 2) {
    if (index + 1 >= _argc || allowed.find(_argv[index]) == allowed.end() ||
        !args.emplace(_argv[index], _argv[index + 1]).second || args.at(_argv[index]).empty()) {
      if (_reason) *_reason = "INVALID_RENDERER_COMMAND_LINE";
      return false;
    }
  }
  if (args.size() != allowed.size()) { if (_reason) *_reason = "INVALID_RENDERER_COMMAND_LINE"; return false; }
  auto required = [&args](const char *_key) -> const std::string & { return args.at(_key); };
  DiagnosticRunSpec spec;
  spec.base_world_template = required("--template");
  spec.rendered_world = required("--output");
  spec.result_receipt = required("--result");
  auto &config = spec.config;
  config.receipt_topic = required("--receipt-topic"); config.run_id = required("--run-id");
  config.world_name = required("--world-name"); config.model_name = required("--model-name");
  config.link_name = required("--link-name"); config.sensor_name = required("--sensor-name");
  config.plugin_source_sha256 = required("--plugin-source-sha256"); config.plugin_binary_sha256 = required("--plugin-binary-sha256");
  config.collector_source_sha256 = required("--collector-source-sha256"); config.collector_binary_sha256 = required("--collector-binary-sha256");
  config.base_world_template_sha256 = required("--base-world-template-sha256"); config.native_model_sha256 = required("--native-model-sha256");
  const bool timeouts = ParsePositiveInt64(required("--system-wait-timeout-sim-time-ns"), &config.system_wait_timeout_sim_time_ns) &&
      ParsePositiveInt64(required("--system-delivery-wait-timeout-steady-ns"), &config.system_delivery_wait_timeout_steady_ns) &&
      ParsePositiveInt64(required("--collector-receipt-wait-timeout-steady-ns"), &config.collector_receipt_wait_timeout_steady_ns) &&
      ParsePositiveInt64(required("--collector-persist-timeout-steady-ns"), &config.collector_persist_timeout_steady_ns);
  if (!timeouts || !IsSafeRunId(config.run_id) || !IsSha256(config.base_world_template_sha256) ||
      !IsSha256(config.native_model_sha256) || !IsSha256(config.plugin_source_sha256) ||
      !IsSha256(config.plugin_binary_sha256) || !IsSha256(config.collector_source_sha256) ||
      !IsSha256(config.collector_binary_sha256) || !spec.base_world_template.is_absolute() ||
      !spec.rendered_world.is_absolute() || !spec.result_receipt.is_absolute() ||
      !ValidateDiagnosticRunSpec(spec, _reason)) {
    if (_reason && _reason->empty()) *_reason = "INVALID_RENDERER_COMMAND_LINE";
    return false;
  }
  *_spec = std::move(spec);
  return true;
}

bool ValidateDiagnosticRunSpec(const DiagnosticRunSpec &_spec, std::string *_reason)
{
  std::error_code error;
  const auto template_path = std::filesystem::absolute(_spec.base_world_template, error);
  const auto output_path = std::filesystem::absolute(_spec.rendered_world, error);
  const auto receipt_path = std::filesystem::absolute(_spec.result_receipt, error);
  const bool valid = !error && ValidateConfig(_spec.config, nullptr) && IsSafeRunId(_spec.config.run_id) &&
      _spec.config.world_name == "world_demo" && IsSafeTree(template_path, false) &&
      std::filesystem::is_regular_file(template_path, error) && !error &&
      IsSafeTree(output_path.parent_path(), false) && IsSafeTree(receipt_path.parent_path(), false) &&
      output_path.parent_path() == receipt_path.parent_path() &&
      std::filesystem::is_directory(output_path.parent_path(), error) && !error &&
      !std::filesystem::exists(output_path, error) && !error && !std::filesystem::exists(receipt_path, error) && !error &&
      output_path.filename() == "native_sdf_contact_diagnostic.rendered.sdf" &&
      receipt_path.filename() == "renderer_result.json";
  if (!valid && _reason) *_reason = "INVALID_IMMUTABLE_DIAGNOSTIC_RUN_SPEC";
  return valid;
}

bool RenderDiagnosticWorld(const DiagnosticRunSpec &_spec, RenderedDiagnosticWorld *_result,
                           std::string *_reason)
{
  if (!_result || !ValidateDiagnosticRunSpec(_spec, _reason)) return false;
  std::string text;
  if (!ReadRegular(_spec.base_world_template, &text)) { if (_reason) *_reason = "INVALID_BASE_WORLD_TEMPLATE"; return false; }
  const std::string base_hash = Hash(text);
  if (base_hash.empty() || base_hash != _spec.config.base_world_template_sha256 || text.find("${") != std::string::npos || text.find("$(") != std::string::npos) {
    if (_reason) *_reason = "INVALID_BASE_WORLD_TEMPLATE_AUTHORITY";
    return false;
  }
  const std::array<std::string, 17> values = {
    _spec.config.receipt_topic, _spec.config.run_id, _spec.config.world_name, _spec.config.model_name,
    _spec.config.link_name, _spec.config.sensor_name, _spec.config.plugin_source_sha256,
    _spec.config.plugin_binary_sha256, _spec.config.collector_source_sha256, _spec.config.collector_binary_sha256,
    _spec.config.base_world_template_sha256, _spec.config.native_model_sha256,
    std::to_string(_spec.config.system_wait_timeout_sim_time_ns), std::to_string(_spec.config.system_delivery_wait_timeout_steady_ns),
    std::to_string(_spec.config.collector_receipt_wait_timeout_steady_ns), std::to_string(_spec.config.collector_persist_timeout_steady_ns),
    "s3_d3::ecs_contact::ContactSensorDiagnosticSystem"};
  for (std::size_t i = 0; i < kTokens.size(); ++i) {
    if (!ReplaceExactlyOnce(&text, kTokens[i], values[i])) { if (_reason) *_reason = "INVALID_WORLD_TEMPLATE_TOKEN_CARDINALITY"; return false; }
  }
  if (text.find("{{S3D3_") != std::string::npos) { if (_reason) *_reason = "INVALID_WORLD_TEMPLATE_UNKNOWN_TOKEN"; return false; }
  const auto output = std::filesystem::absolute(_spec.rendered_world);
  if (!WriteNoReplace(output, text)) { if (_reason) *_reason = "INVALID_RENDERED_WORLD_PERSISTENCE"; return false; }
  const auto template_canonical = std::filesystem::canonical(_spec.base_world_template).string();
  const auto output_canonical = (std::filesystem::canonical(output.parent_path()) / output.filename()).string();
  const std::string rendered_hash = Hash(text);
  if (rendered_hash.empty()) { if (_reason) *_reason = "INVALID_RENDERED_WORLD_HASH"; return false; }
  const std::string receipt = "{\n  \"schema_version\": \"s3_d3_renderer_result/v1\",\n  \"run_id\": \"" + EscapeJson(_spec.config.run_id) +
      "\",\n  \"template_path\": \"" + EscapeJson(template_canonical) + "\",\n  \"rendered_world_path\": \"" + EscapeJson(output_canonical) +
      "\",\n  \"base_world_template_sha256\": \"" + base_hash + "\",\n  \"rendered_world_sha256\": \"" + rendered_hash + "\"\n}\n";
  if (!WriteNoReplace(std::filesystem::absolute(_spec.result_receipt), receipt)) { if (_reason) *_reason = "INVALID_RENDER_RESULT_RECEIPT_PERSISTENCE"; return false; }
  _result->base_world_template_sha256 = base_hash;
  _result->rendered_world_sha256 = rendered_hash;
  return true;
}
}  // namespace s3_d3::ecs_contact
