// Temporary S3 D3 diagnostic helper. It is not production code.
// Offline modes never construct a Gazebo Transport node or send a request.

#include <array>
#include <atomic>
#include <cerrno>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <sys/syscall.h>
#include <unistd.h>
#include <vector>

#include <openssl/sha.h>

#include <gz/msgs/empty.pb.h>
#include <gz/msgs/scene.pb.h>
#include <gz/transport/Node.hh>

namespace
{
namespace fs = std::filesystem;
constexpr const char *kService = "/world/world_demo/scene/info";
constexpr const char *kModel = "ROBOT_URDF_final";
constexpr const char *kLink = "base_link";
constexpr const char *kSensor = "s3_d3_base_contact_sensor";
constexpr const char *kCollision = "s3_d3_base_contact_collision";
constexpr const char *kPersistenceFailure = "INVALID_EVIDENCE_PERSISTENCE_FAILURE";

// These are the only Scene terminal statuses locked by the approval packet.
enum class Status
{
  kSceneServiceUnavailable,
  kSceneRequestIncomplete,
  kSceneResponseUndecodable,
  kSceneModelNotObservedAfterDelay,
  kSceneLinkNotObservedAfterDelay,
  kSceneSensorNotObservedAfterDelay,
  kSceneSensorPresentIdentityOnly,
  kSceneSensorPresent,
};

const char *StatusName(Status status)
{
  switch (status)
  {
    case Status::kSceneServiceUnavailable: return "SCENE_SERVICE_UNAVAILABLE";
    case Status::kSceneRequestIncomplete: return "SCENE_REQUEST_INCOMPLETE";
    case Status::kSceneResponseUndecodable: return "SCENE_RESPONSE_UNDECODABLE";
    case Status::kSceneModelNotObservedAfterDelay: return "SCENE_MODEL_NOT_OBSERVED_AFTER_DELAY";
    case Status::kSceneLinkNotObservedAfterDelay: return "SCENE_LINK_NOT_OBSERVED_AFTER_DELAY";
    case Status::kSceneSensorNotObservedAfterDelay: return "SCENE_SENSOR_NOT_OBSERVED_AFTER_DELAY";
    case Status::kSceneSensorPresentIdentityOnly: return "SCENE_SENSOR_PRESENT_IDENTITY_ONLY";
    case Status::kSceneSensorPresent: return "SCENE_SENSOR_PRESENT";
  }
  return "SCENE_RESPONSE_UNDECODABLE";
}

struct Evaluation
{
  Status status{Status::kSceneResponseUndecodable};
  std::string reason{"SCENE_PARSE_FAILED"};
  int model_count{0};
  int link_count{0};
  int sensor_count{0};
  int collision_count{0};
  bool has_model{false};
  bool has_link{false};
  bool has_sensor{false};
  uint32_t model_id{0};
  uint32_t link_id{0};
  uint32_t sensor_id{0};
};

struct RuntimeArguments
{
  std::string run_id;
  unsigned int preflight_wait_ms{0};
  unsigned int request_timeout_ms{0};
  unsigned int polling_ms{0};
  fs::path output_dir;
};

bool ValidRunId(const std::string &run_id)
{
  constexpr const char *prefix = "run-typed-scene-";
  if (run_id.size() <= std::char_traits<char>::length(prefix) ||
      run_id.rfind(prefix, 0) != 0 || run_id.size() > 160) return false;
  for (const unsigned char value : run_id)
  {
    if (!(std::isalnum(value) || value == '-' || value == '_')) return false;
  }
  return true;
}

bool HasExactSceneService(const std::vector<std::string> &services)
{
  int count = 0;
  for (const auto &service : services)
    if (service == kService) ++count;
  return count == 1;
}

bool ParsePositiveMilliseconds(const std::string &value, unsigned int *result)
{
  try
  {
    const unsigned long parsed = std::stoul(value);
    if (parsed == 0 || parsed > 0xffffffffUL) return false;
    *result = static_cast<unsigned int>(parsed);
    return true;
  }
  catch (const std::exception &) { return false; }
}

bool ParseRuntimeArguments(const std::vector<std::string> &arguments,
                           RuntimeArguments *result)
{
  if (arguments.size() != 11 || arguments[0] != "--runtime-once" ||
      arguments[1] != "--run-id" || !ValidRunId(arguments[2]) ||
      arguments[3] != "--preflight-wait-ms" || arguments[5] != "--request-timeout-ms" ||
      arguments[7] != "--polling-ms" || arguments[9] != "--output-dir" ||
      arguments[10].empty() || !fs::path(arguments[10]).is_absolute()) return false;
  result->run_id = arguments[2];
  return ParsePositiveMilliseconds(arguments[4], &result->preflight_wait_ms) &&
         ParsePositiveMilliseconds(arguments[6], &result->request_timeout_ms) &&
         ParsePositiveMilliseconds(arguments[8], &result->polling_ms) &&
         !(result->output_dir = arguments[10]).empty();
}

template<typename CollectionT, typename PredicateT>
int ExactCount(const CollectionT &items, PredicateT predicate)
{
  int count = 0;
  for (const auto &item : items)
    if (predicate(item)) ++count;
  return count;
}

Evaluation EvaluateScene(const gz::msgs::Scene &scene)
{
  Evaluation e;
  e.model_count = ExactCount(scene.model(), [](const auto &v) { return v.name() == kModel; });
  if (e.model_count == 0)
    return {Status::kSceneModelNotObservedAfterDelay, "EXACT_MODEL_NOT_FOUND", 0};
  if (e.model_count != 1)
    return {Status::kSceneResponseUndecodable, "AMBIGUOUS_EXACT_MODEL", e.model_count};

  const gz::msgs::Model *model = nullptr;
  for (const auto &v : scene.model()) if (v.name() == kModel) { model = &v; break; }
  e.has_model = true;
  e.model_id = model->id();
  e.link_count = ExactCount(model->link(), [](const auto &v) { return v.name() == kLink; });
  if (e.link_count == 0) { e.status = Status::kSceneLinkNotObservedAfterDelay; e.reason = "EXACT_LINK_NOT_FOUND"; return e; }
  if (e.link_count != 1) { e.status = Status::kSceneResponseUndecodable; e.reason = "AMBIGUOUS_EXACT_LINK"; return e; }

  const gz::msgs::Link *link = nullptr;
  for (const auto &v : model->link()) if (v.name() == kLink) { link = &v; break; }
  e.has_link = true;
  e.link_id = link->id();
  e.sensor_count = ExactCount(link->sensor(), [](const auto &v) { return v.name() == kSensor; });
  if (e.sensor_count == 0) { e.status = Status::kSceneSensorNotObservedAfterDelay; e.reason = "EXACT_SENSOR_NOT_FOUND"; return e; }
  if (e.sensor_count != 1) { e.status = Status::kSceneResponseUndecodable; e.reason = "AMBIGUOUS_EXACT_SENSOR"; return e; }

  const gz::msgs::Sensor *sensor = nullptr;
  for (const auto &v : link->sensor()) if (v.name() == kSensor) { sensor = &v; break; }
  e.has_sensor = true;
  e.sensor_id = sensor->id();
  // gz-msgs10 exposes no Contact enum. Do not inspect the protobuf enum field.
  if (!sensor->has_contact())
  {
    e.status = Status::kSceneSensorPresentIdentityOnly;
    e.reason = "DIAGNOSTIC_INCOMPLETE_CONTACT_TYPE_ENUM;DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY";
    return e;
  }
  const auto &collision_name = sensor->contact().collision_name();
  if (collision_name.empty() || collision_name != kCollision)
  {
    e.status = Status::kSceneSensorPresentIdentityOnly;
    e.reason = "DIAGNOSTIC_INCOMPLETE_CONTACT_TYPE_ENUM;DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY";
    return e;
  }
  e.collision_count = ExactCount(link->collision(), [](const auto &v) { return v.name() == kCollision; });
  if (e.collision_count > 1)
  {
    e.status = Status::kSceneResponseUndecodable;
    e.reason = "AMBIGUOUS_EXACT_COLLISION";
    return e;
  }
  if (e.collision_count == 0)
  {
    e.status = Status::kSceneSensorPresentIdentityOnly;
    e.reason = "DIAGNOSTIC_INCOMPLETE_CONTACT_TYPE_ENUM;DIAGNOSTIC_INCOMPLETE_COLLISION_IDENTITY";
    return e;
  }
  // Full SCENE_SENSOR_PRESENT is deliberately unreachable without a verified enum.
  e.status = Status::kSceneSensorPresentIdentityOnly;
  e.reason = "DIAGNOSTIC_INCOMPLETE_CONTACT_TYPE_ENUM";
  return e;
}

Evaluation EvaluateBytes(const std::string &raw)
{
  gz::msgs::Scene scene;
  if (!scene.ParseFromString(raw))
    return {Status::kSceneResponseUndecodable, "SCENE_PARSE_FAILED"};
  return EvaluateScene(scene);
}

gz::msgs::Scene ExactFixture()
{
  gz::msgs::Scene scene;
  auto *model = scene.add_model(); model->set_name(kModel); model->set_id(11);
  auto *link = model->add_link(); link->set_name(kLink); link->set_id(12);
  auto *sensor = link->add_sensor(); sensor->set_name(kSensor); sensor->set_id(13);
  sensor->mutable_contact()->set_collision_name(kCollision);
  auto *collision = link->add_collision(); collision->set_name(kCollision); collision->set_id(14);
  return scene;
}

std::string Sha256(const std::string &bytes)
{
  std::array<unsigned char, SHA256_DIGEST_LENGTH> digest{};
  SHA256(reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size(), digest.data());
  std::ostringstream out;
  for (const auto value : digest) out << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(value);
  return out.str();
}

std::string JsonEscape(const std::string &value)
{
  std::ostringstream out;
  for (const unsigned char ch : value)
  {
    switch (ch)
    {
      case '"': out << "\\\""; break;
      case '\\': out << "\\\\"; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (ch < 0x20) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(ch);
        else out << ch;
    }
  }
  return out.str();
}

std::string SummaryJson(const Evaluation &e, const std::string &sha,
                        const std::string &run_id,
                        uint64_t preflight_start_ns, uint64_t preflight_end_ns,
                        uint64_t request_start_ns, uint64_t request_end_ns)
{
  std::ostringstream out;
  out << "{\"collision_exact_count\":" << e.collision_count
      << ",\"fixed_literals\":{\"collision\":\"" << kCollision
      << "\",\"link\":\"" << kLink << "\",\"model\":\"" << kModel
      << "\",\"sensor\":\"" << kSensor << "\",\"service\":\"" << kService << "\"}"
      << ",\"link\":" << (e.has_link ? ("{\"id\":" + std::to_string(e.link_id) + ",\"name\":\"" + kLink + "\"}") : "null")
      << ",\"link_exact_count\":" << e.link_count
      << ",\"model\":" << (e.has_model ? ("{\"id\":" + std::to_string(e.model_id) + ",\"name\":\"" + kModel + "\"}") : "null")
      << ",\"model_exact_count\":" << e.model_count
      << ",\"preflight_end_steady_ns\":" << preflight_end_ns
      << ",\"preflight_start_steady_ns\":" << preflight_start_ns
      << ",\"raw_response_sha256\":\"" << sha << "\""
      << ",\"reason\":\"" << JsonEscape(e.reason) << "\""
      << ",\"request_end_steady_ns\":" << request_end_ns
      << ",\"request_raw_called\":true"
      << ",\"request_start_steady_ns\":" << request_start_ns
      << ",\"run_id\":\"" << JsonEscape(run_id) << "\""
      << ",\"schema_version\":\"s3_d3_typed_scene_summary/v4\""
      << ",\"sensor\":" << (e.has_sensor ? ("{\"id\":" + std::to_string(e.sensor_id) + ",\"name\":\"" + kSensor + "\"}") : "null")
      << ",\"sensor_exact_count\":" << e.sensor_count
      << ",\"status\":\"" << StatusName(e.status) << "\"}";
  return out.str();
}

std::string NullableNs(const std::optional<uint64_t> value)
{
  return value ? std::to_string(*value) : "null";
}

std::string MetadataJson(const std::string &outer_status, const std::string &detail,
                         const std::string &run_id, const Evaluation *evaluation,
                         std::optional<uint64_t> preflight_start_ns,
                         std::optional<uint64_t> preflight_end_ns,
                         std::optional<uint64_t> request_start_ns,
                         std::optional<uint64_t> request_end_ns,
                         const bool request_raw_called)
{
  std::ostringstream out;
  out << "{\"detail\":\"" << JsonEscape(detail) << "\""
      << ",\"outer_status\":\"" << outer_status << "\""
      << ",\"preflight_end_steady_ns\":" << NullableNs(preflight_end_ns)
      << ",\"preflight_start_steady_ns\":" << NullableNs(preflight_start_ns)
      << ",\"request_end_steady_ns\":" << NullableNs(request_end_ns)
      << ",\"request_raw_called\":" << (request_raw_called ? "true" : "false")
      << ",\"request_start_steady_ns\":" << NullableNs(request_start_ns)
      << ",\"run_id\":\"" << JsonEscape(run_id) << "\""
      << ",\"scene_status\":";
  if (evaluation) out << "\"" << StatusName(evaluation->status) << "\"";
  else out << "null";
  out << ",\"service\":\"" << kService << "\""
      << ",\"schema_version\":\"s3_d3_typed_scene_metadata/v3\"}";
  return out.str();
}

bool PrepareRequestBytes(gz::msgs::Empty *request, std::string *bytes,
                         const bool inject_failure)
{
  return !inject_failure && request->SerializeToString(bytes);
}

std::chrono::steady_clock::time_point NextPollTime(
    const std::chrono::steady_clock::time_point now,
    const std::chrono::steady_clock::time_point deadline,
    const unsigned int polling_ms)
{
  const auto candidate = now + std::chrono::milliseconds(polling_ms);
  return candidate < deadline ? candidate : deadline;
}

bool SafeMissingTarget(const fs::path &path)
{
  std::error_code ec;
  const fs::file_status status = fs::symlink_status(path, ec);
  if (ec && ec != std::errc::no_such_file_or_directory) return false;
  return status.type() == fs::file_type::not_found;
}

bool WriteFile(const fs::path &path, const std::string &content)
{
  if (path.empty() || fs::is_symlink(path.parent_path()) || !SafeMissingTarget(path)) return false;
  static std::atomic<uint64_t> serial{0};
  const fs::path temporary = path.parent_path() /
      ("." + path.filename().string() + "." + std::to_string(::getpid()) + "." +
       std::to_string(serial.fetch_add(1, std::memory_order_relaxed)) + ".tmp");
  const int fd = ::open(temporary.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0600);
  if (fd < 0) return false;
  bool ok = true;
  size_t offset = 0;
  while (offset < content.size())
  {
    const ssize_t wrote = ::write(fd, content.data() + offset, content.size() - offset);
    if (wrote <= 0) { ok = false; break; }
    offset += static_cast<size_t>(wrote);
  }
  if (ok && ::fsync(fd) != 0) ok = false;
  if (::close(fd) != 0) ok = false;
  if (!ok) { ::unlink(temporary.c_str()); return false; }
  constexpr unsigned int kRenameNoReplace = 1U;
  if (::syscall(SYS_renameat2, AT_FDCWD, temporary.c_str(), AT_FDCWD,
                path.c_str(), kRenameNoReplace) != 0)
  {
    ::unlink(temporary.c_str());
    return false;
  }
  const int directory_fd = ::open(path.parent_path().c_str(), O_RDONLY | O_DIRECTORY);
  if (directory_fd < 0 || ::fsync(directory_fd) != 0)
  {
    if (directory_fd >= 0) ::close(directory_fd);
    ::unlink(path.c_str());
    return false;
  }
  if (::close(directory_fd) != 0) return false;
  return true;
}

bool ReadFile(const fs::path &path, std::string *content)
{
  std::ifstream stream(path, std::ios::binary);
  if (!stream) return false;
  *content = std::string((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
  return static_cast<bool>(stream) || stream.eof();
}

struct PersistResult { bool ok; std::string reason; };

bool ManifestMatchesRunId(const fs::path &output_dir, const std::string &run_id)
{
  std::string manifest;
  if (!ReadFile(output_dir / "run_manifest.json", &manifest)) return false;
  const std::string token = "\"run_id\":\"" + JsonEscape(run_id) + "\"";
  const size_t first = manifest.find(token);
  return first != std::string::npos && manifest.find(token, first + token.size()) == std::string::npos;
}

PersistResult PrepareOutputDirectory(const fs::path &output_dir,
                                     const std::optional<std::string> &expected_run_id = std::nullopt)
{
  std::error_code ec;
  if (fs::is_symlink(output_dir)) return {false, "OUTPUT_DIRECTORY_SYMLINK_FORBIDDEN"};
  if (expected_run_id)
  {
    if (!fs::exists(output_dir) || !fs::is_directory(output_dir) ||
        !ValidRunId(*expected_run_id) || !ManifestMatchesRunId(output_dir, *expected_run_id))
      return {false, "OUTPUT_DIRECTORY_RUN_ID_MANIFEST_MISMATCH"};
  }
  else fs::create_directories(output_dir, ec);
  if (ec || !fs::is_directory(output_dir) || fs::is_symlink(output_dir)) return {false, "OUTPUT_DIRECTORY_CREATE_FAILED"};
  return {true, ""};
}

PersistResult WriteTerminalMetadata(const fs::path &output_dir, const std::string &run_id,
                                    const std::string &outer_status, const std::string &detail,
                                    std::optional<uint64_t> preflight_start_ns,
                                    std::optional<uint64_t> preflight_end_ns,
                                    std::optional<uint64_t> request_start_ns,
                                    std::optional<uint64_t> request_end_ns,
                                    const bool request_raw_called)
{
  const PersistResult prepared = PrepareOutputDirectory(output_dir);
  if (!prepared.ok) return prepared;
  if (!WriteFile(output_dir / "request_metadata.json",
                 MetadataJson(outer_status, detail, run_id, nullptr, preflight_start_ns,
                              preflight_end_ns, request_start_ns, request_end_ns,
                              request_raw_called))) return {false, "METADATA_WRITE_FAILED"};
  std::ostringstream summary;
  summary << "{\"preflight_end_steady_ns\":" << NullableNs(preflight_end_ns)
          << ",\"preflight_start_steady_ns\":" << NullableNs(preflight_start_ns)
          << ",\"raw_response_sha256\":null,\"reason\":\"" << JsonEscape(detail)
          << "\",\"request_end_steady_ns\":" << NullableNs(request_end_ns)
          << ",\"request_raw_called\":" << (request_raw_called ? "true" : "false")
          << ",\"request_start_steady_ns\":" << NullableNs(request_start_ns)
          << ",\"run_id\":\"" << JsonEscape(run_id)
          << "\",\"schema_version\":\"s3_d3_typed_scene_summary/v4\",\"status\":\""
          << outer_status << "\"}";
  if (!WriteFile(output_dir / "scene_summary.json", summary.str())) return {false, "SUMMARY_WRITE_FAILED"};
  return {true, ""};
}

PersistResult WriteRawBeforeParse(const fs::path &output_dir, const std::string &raw)
{
  const PersistResult prepared = PrepareOutputDirectory(output_dir);
  if (!prepared.ok) return prepared;
  const std::string sha = Sha256(raw);
  if (!WriteFile(output_dir / "scene_response.pb", raw)) return {false, "RAW_RESPONSE_WRITE_FAILED"};
  if (!WriteFile(output_dir / "scene_response.sha256", sha + "\n"))
  {
    std::error_code ignored;
    fs::remove(output_dir / "scene_response.pb", ignored);
    return {false, "RAW_RESPONSE_SHA_WRITE_FAILED"};
  }
  return {true, ""};
}

PersistResult FinalizeArtifact(const fs::path &output_dir, const std::string &run_id,
                               const std::string &raw, const Evaluation &evaluation,
                               uint64_t preflight_start_ns, uint64_t preflight_end_ns,
                               uint64_t request_start_ns, uint64_t request_end_ns)
{
  const std::string summary = SummaryJson(evaluation, Sha256(raw), run_id, preflight_start_ns,
                                          preflight_end_ns, request_start_ns, request_end_ns);
  const std::string metadata = MetadataJson("SCENE_CLASSIFICATION_COMPLETE", "", run_id, &evaluation,
                                             preflight_start_ns, preflight_end_ns, request_start_ns,
                                             request_end_ns, true);
  if (!WriteFile(output_dir / "request_metadata.json", metadata)) return {false, "METADATA_WRITE_FAILED"};
  if (!WriteFile(output_dir / "scene_summary.json", summary)) return {false, "SUMMARY_WRITE_FAILED"};
  return {true, ""};
}

uint64_t SteadyNowNs()
{
  return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count());
}

bool Expect(const std::string &name, const Evaluation &actual, Status expected)
{
  const bool pass = actual.status == expected && actual.status != Status::kSceneSensorPresent;
  std::cout << (pass ? "PASS " : "FAIL ") << name << " actual=" << StatusName(actual.status)
            << " reason=" << actual.reason << '\n';
  return pass;
}

bool ExpectScene(const std::string &name, const gz::msgs::Scene &scene, Status expected)
{
  std::string bytes;
  return scene.SerializeToString(&bytes) && Expect(name, EvaluateBytes(bytes), expected);
}

int OfflineSelfTest()
{
  bool ok = true;
  auto exact = ExactFixture();
  ok &= ExpectScene("exact_chain_identity_only", exact, Status::kSceneSensorPresentIdentityOnly);
  gz::msgs::Scene no_model;
  ok &= ExpectScene("model_absent", no_model, Status::kSceneModelNotObservedAfterDelay);
  auto no_link = ExactFixture(); no_link.mutable_model(0)->clear_link();
  ok &= ExpectScene("link_absent", no_link, Status::kSceneLinkNotObservedAfterDelay);
  auto no_sensor = ExactFixture(); no_sensor.mutable_model(0)->mutable_link(0)->clear_sensor();
  ok &= ExpectScene("sensor_absent", no_sensor, Status::kSceneSensorNotObservedAfterDelay);
  auto duplicate_model = ExactFixture(); duplicate_model.add_model()->set_name(kModel);
  ok &= ExpectScene("duplicate_exact_model", duplicate_model, Status::kSceneResponseUndecodable);
  auto duplicate_link = ExactFixture(); duplicate_link.mutable_model(0)->add_link()->set_name(kLink);
  ok &= ExpectScene("duplicate_exact_link", duplicate_link, Status::kSceneResponseUndecodable);
  auto duplicate_sensor = ExactFixture(); duplicate_sensor.mutable_model(0)->mutable_link(0)->add_sensor()->set_name(kSensor);
  ok &= ExpectScene("duplicate_exact_sensor", duplicate_sensor, Status::kSceneResponseUndecodable);
  auto no_contact = ExactFixture(); no_contact.mutable_model(0)->mutable_link(0)->mutable_sensor(0)->clear_contact();
  ok &= ExpectScene("contact_field_absent", no_contact, Status::kSceneSensorPresentIdentityOnly);
  auto empty_name = ExactFixture(); empty_name.mutable_model(0)->mutable_link(0)->mutable_sensor(0)->mutable_contact()->clear_collision_name();
  ok &= ExpectScene("empty_collision_name", empty_name, Status::kSceneSensorPresentIdentityOnly);
  auto wrong_name = ExactFixture(); wrong_name.mutable_model(0)->mutable_link(0)->mutable_sensor(0)->mutable_contact()->set_collision_name("other_collision");
  ok &= ExpectScene("wrong_collision_name", wrong_name, Status::kSceneSensorPresentIdentityOnly);
  auto missing_collision = ExactFixture(); missing_collision.mutable_model(0)->mutable_link(0)->clear_collision();
  ok &= ExpectScene("missing_same_link_collision", missing_collision, Status::kSceneSensorPresentIdentityOnly);
  auto duplicate_collision = ExactFixture(); duplicate_collision.mutable_model(0)->mutable_link(0)->add_collision()->set_name(kCollision);
  ok &= ExpectScene("duplicate_same_link_collision", duplicate_collision, Status::kSceneResponseUndecodable);
  ok &= Expect("corrupt_raw_protobuf", EvaluateBytes(std::string("\x80", 1)), Status::kSceneResponseUndecodable);
  ok &= HasExactSceneService({"/other", kService});
  ok &= !HasExactSceneService({});
  ok &= !HasExactSceneService({kService, kService});
  RuntimeArguments valid;
  ok &= ParseRuntimeArguments({"--runtime-once", "--run-id", "run-typed-scene-offline", "--preflight-wait-ms", "1", "--request-timeout-ms", "2", "--polling-ms", "3", "--output-dir", "/tmp/out"}, &valid);
  ok &= valid.preflight_wait_ms == 1 && valid.request_timeout_ms == 2;
  RuntimeArguments invalid;
  ok &= !ParseRuntimeArguments({"--runtime-once", "--run-id", "run-typed-scene-offline", "--preflight-wait-ms", "0", "--request-timeout-ms", "2", "--polling-ms", "3", "--output-dir", "/tmp/out"}, &invalid);
  ok &= !ParseRuntimeArguments({"--runtime-once", "--run-id", "run-typed-scene-offline", "--preflight-wait-ms", "x", "--request-timeout-ms", "2", "--polling-ms", "3", "--output-dir", "/tmp/out"}, &invalid);
  ok &= !ParseRuntimeArguments({"--runtime-once", "--run-id", "../bad", "--preflight-wait-ms", "1", "--request-timeout-ms", "2", "--polling-ms", "3", "--output-dir", "/tmp/out"}, &invalid);
  ok &= !ParseRuntimeArguments({"--runtime-once", "--run-id", "run-typed-scene-offline", "--preflight-wait-ms", "1", "--request-timeout-ms", "2", "--polling-ms", "3", "--output-dir", ""}, &invalid);
  const auto now = std::chrono::steady_clock::now();
  const auto deadline = now + std::chrono::milliseconds(25);
  ok &= valid.polling_ms == 3;
  ok &= NextPollTime(now, deadline, valid.polling_ms) > now && NextPollTime(now, deadline, valid.polling_ms) <= deadline;
  gz::msgs::Empty serialization_fixture;
  std::string serialization_bytes;
  ok &= !PrepareRequestBytes(&serialization_fixture, &serialization_bytes, true);
  ok &= PrepareRequestBytes(&serialization_fixture, &serialization_bytes, false);
  std::cout << (ok ? "OFFLINE_SELF_TEST_PASS\n" : "OFFLINE_SELF_TEST_FAIL\n");
  return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}

int OfflineArtifactSelfTest()
{
  char template_path[] = "/tmp/s3_d3_typed_scene_XXXXXX";
  char *root = mkdtemp(template_path);
  if (!root) return EXIT_FAILURE;
  const fs::path root_path(root);
  bool ok = true;
  std::string bytes;
  ExactFixture().SerializeToString(&bytes);
  const Evaluation exact = EvaluateBytes(bytes);
  const fs::path first = root_path / "first";
  const fs::path second = root_path / "second";
  const std::string run_id = "run-typed-scene-offline-artifact";
  ok &= WriteRawBeforeParse(first, bytes).ok;
  ok &= FinalizeArtifact(first, run_id, bytes, exact, 1, 2, 3, 4).ok;
  std::string persisted;
  ok &= ReadFile(first / "scene_response.pb", &persisted) && persisted == bytes;
  std::string persisted_sha;
  ok &= ReadFile(first / "scene_response.sha256", &persisted_sha);
  ok &= persisted_sha == Sha256(bytes) + "\n";
  ok &= Sha256(persisted) == Sha256(bytes);
  ok &= EvaluateBytes(persisted).status == Status::kSceneSensorPresentIdentityOnly;
  ok &= WriteRawBeforeParse(second, bytes).ok;
  ok &= FinalizeArtifact(second, run_id, bytes, exact, 1, 2, 3, 4).ok;
  std::string first_summary, second_summary;
  ok &= ReadFile(first / "scene_summary.json", &first_summary);
  ok &= ReadFile(second / "scene_summary.json", &second_summary);
  ok &= first_summary == second_summary;

  auto duplicate = ExactFixture(); duplicate.add_model()->set_name(kModel);
  std::string duplicate_bytes; duplicate.SerializeToString(&duplicate_bytes);
  ok &= EvaluateBytes(duplicate_bytes).status == Status::kSceneResponseUndecodable;
  ok &= EvaluateBytes(std::string("\x80", 1)).status == Status::kSceneResponseUndecodable;

  const fs::path blocker = root_path / "not_a_directory";
  ok &= WriteFile(blocker, "blocker");
  const PersistResult failed = WriteRawBeforeParse(blocker, bytes);
  ok &= !failed.ok && failed.reason == "OUTPUT_DIRECTORY_CREATE_FAILED";
  if (!failed.ok) std::cout << kPersistenceFailure << " reason=" << failed.reason << '\n';

  const fs::path unavailable = root_path / "service_unavailable";
  const fs::path incomplete = root_path / "request_incomplete";
  ok &= WriteTerminalMetadata(unavailable, run_id, "SCENE_SERVICE_UNAVAILABLE", "PREFLIGHT_DEADLINE", 1, 2, std::nullopt, std::nullopt, false).ok;
  ok &= WriteTerminalMetadata(incomplete, run_id, "SCENE_REQUEST_INCOMPLETE", "REQUEST_RAW_NOT_COMPLETE", 1, 2, 3, 4, true).ok;
  std::string unavailable_metadata, incomplete_metadata;
  ok &= ReadFile(unavailable / "request_metadata.json", &unavailable_metadata);
  ok &= ReadFile(incomplete / "request_metadata.json", &incomplete_metadata);
  ok &= unavailable_metadata.find("SCENE_SERVICE_UNAVAILABLE") != std::string::npos;
  ok &= incomplete_metadata.find("SCENE_REQUEST_INCOMPLETE") != std::string::npos;
  ok &= unavailable_metadata.find("\"request_start_steady_ns\":null") != std::string::npos;
  ok &= unavailable_metadata.find("\"request_end_steady_ns\":null") != std::string::npos;
  ok &= incomplete_metadata.find("\"preflight_start_steady_ns\":1") != std::string::npos;
  ok &= incomplete_metadata.find("\"request_start_steady_ns\":3") != std::string::npos;
  ok &= !fs::exists(unavailable / "scene_response.pb");
  ok &= !fs::exists(unavailable / "scene_response.sha256");
  ok &= unavailable_metadata.find("\"run_id\":\"run-typed-scene-offline-artifact\"") != std::string::npos;
  const fs::path matching_manifest = root_path / "manifest_match";
  std::error_code manifest_ec; fs::create_directories(matching_manifest, manifest_ec);
  ok &= !manifest_ec && WriteFile(matching_manifest / "run_manifest.json", "{\"run_id\":\"run-typed-scene-offline-artifact\"}");
  ok &= PrepareOutputDirectory(matching_manifest, run_id).ok;
  ok &= !PrepareOutputDirectory(matching_manifest, "run-typed-scene-other").ok;
  const fs::path existing = root_path / "existing";
  ok &= WriteFile(existing, "first");
  ok &= !WriteFile(existing, "second");
  std::string existing_bytes; ok &= ReadFile(existing, &existing_bytes) && existing_bytes == "first";
  const fs::path linked_target = root_path / "linked_target";
  ok &= WriteFile(linked_target, "target");
  const fs::path symlink_target = root_path / "symlink_target";
  std::error_code symlink_ec; fs::create_symlink(linked_target, symlink_target, symlink_ec);
  ok &= !symlink_ec && !WriteFile(symlink_target, "must_not_overwrite");
  const fs::path duplicate_raw = root_path / "duplicate_raw";
  ok &= WriteRawBeforeParse(duplicate_raw, bytes).ok;
  ok &= !WriteRawBeforeParse(duplicate_raw, bytes).ok;
  const fs::path partial_pair = root_path / "partial_pair";
  std::error_code partial_ec; fs::create_directories(partial_pair, partial_ec);
  ok &= !partial_ec && WriteFile(partial_pair / "scene_response.sha256", "locked\n");
  const PersistResult partial = WriteRawBeforeParse(partial_pair, bytes);
  ok &= !partial.ok && partial.reason == "RAW_RESPONSE_SHA_WRITE_FAILED";
  ok &= !fs::exists(partial_pair / "scene_response.pb");
  bool leaked_temp = false;
  for (const auto &entry : fs::recursive_directory_iterator(root_path))
    if (entry.path().filename().string().find(".tmp") != std::string::npos) leaked_temp = true;
  ok &= !leaked_temp;

  std::error_code ec;
  fs::remove_all(root_path, ec);
  ok &= !ec && !fs::exists(root_path);
  std::cout << (ok ? "OFFLINE_ARTIFACT_SELF_TEST_PASS\n" : "OFFLINE_ARTIFACT_SELF_TEST_FAIL\n");
  return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}

// This function is intentionally unreachable from either offline mode.
// It contains the only future transport request in this source file.
int RuntimeOnce(const RuntimeArguments &arguments)
{
  const PersistResult prepared = PrepareOutputDirectory(arguments.output_dir, arguments.run_id);
  if (!prepared.ok) { std::cerr << kPersistenceFailure << ' ' << prepared.reason << '\n'; return EXIT_FAILURE; }
  gz::transport::Node node;
  const uint64_t preflight_start_ns = SteadyNowNs();
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(arguments.preflight_wait_ms);
  bool service_visible = false;
  while (true)
  {
    std::vector<std::string> services;
    node.ServiceList(services);
    if (HasExactSceneService(services)) { service_visible = true; break; }
    const auto now = std::chrono::steady_clock::now();
    if (now >= deadline) break;
    std::this_thread::sleep_until(NextPollTime(now, deadline, arguments.polling_ms));
  }
  const uint64_t preflight_end_ns = SteadyNowNs();
  if (!service_visible)
  {
    const PersistResult metadata = WriteTerminalMetadata(arguments.output_dir, arguments.run_id, "SCENE_SERVICE_UNAVAILABLE", "EXACT_SERVICE_NOT_DISCOVERED", preflight_start_ns, preflight_end_ns, std::nullopt, std::nullopt, false);
    if (!metadata.ok) std::cerr << kPersistenceFailure << ' ' << metadata.reason << '\n';
    return metadata.ok ? EXIT_SUCCESS : EXIT_FAILURE;
  }
  gz::msgs::Empty request;
  std::string request_bytes, response_bytes;
  const uint64_t request_start_ns = SteadyNowNs();
  if (!PrepareRequestBytes(&request, &request_bytes, false))
  {
    const uint64_t request_end_ns = SteadyNowNs();
    const PersistResult metadata = WriteTerminalMetadata(arguments.output_dir, arguments.run_id, "SCENE_REQUEST_INCOMPLETE", "REQUEST_SERIALIZATION_FAILED", preflight_start_ns, preflight_end_ns, request_start_ns, request_end_ns, false);
    if (!metadata.ok) std::cerr << kPersistenceFailure << ' ' << metadata.reason << '\n';
    return metadata.ok ? EXIT_SUCCESS : EXIT_FAILURE;
  }
  gz::msgs::Scene response;
  bool service_result = false;
  const bool completed = node.RequestRaw(kService, request_bytes, request.GetTypeName(), response.GetTypeName(), arguments.request_timeout_ms, response_bytes, service_result);
  const uint64_t request_end_ns = SteadyNowNs();
  if (!completed || !service_result)
  {
    const PersistResult metadata = WriteTerminalMetadata(arguments.output_dir, arguments.run_id, "SCENE_REQUEST_INCOMPLETE", "REQUEST_RAW_NOT_COMPLETE", preflight_start_ns, preflight_end_ns, request_start_ns, request_end_ns, true);
    if (!metadata.ok) std::cerr << kPersistenceFailure << ' ' << metadata.reason << '\n';
    return metadata.ok ? EXIT_SUCCESS : EXIT_FAILURE;
  }
  const PersistResult raw = WriteRawBeforeParse(arguments.output_dir, response_bytes);
  if (!raw.ok) { std::cerr << kPersistenceFailure << ' ' << raw.reason << '\n'; return EXIT_FAILURE; }
  const Evaluation evaluation = EvaluateBytes(std::string(response_bytes));
  const PersistResult final = FinalizeArtifact(arguments.output_dir, arguments.run_id, response_bytes, evaluation, preflight_start_ns, preflight_end_ns, request_start_ns, request_end_ns);
  if (!final.ok) { std::cerr << kPersistenceFailure << ' ' << final.reason << '\n'; return EXIT_FAILURE; }
  std::cout << StatusName(evaluation.status) << ' ' << evaluation.reason << '\n';
  return evaluation.status == Status::kSceneSensorPresent ? EXIT_FAILURE : EXIT_SUCCESS;
}

void Usage(const char *program)
{
  std::cout << "Usage: " << program << " --offline-self-test | --offline-artifact-self-test | "
            << "--runtime-once --run-id <opaque-run-id> --preflight-wait-ms <positive-integer> --request-timeout-ms <positive-integer> --polling-ms <positive-integer> --output-dir <absolute-directory>\n";
}
}  // namespace

int main(int argc, char **argv)
{
  if (argc == 2 && std::string(argv[1]) == "--offline-self-test") return OfflineSelfTest();
  if (argc == 2 && std::string(argv[1]) == "--offline-artifact-self-test") return OfflineArtifactSelfTest();
  if (argc == 12)
  {
    RuntimeArguments arguments;
    std::vector<std::string> parsed;
    for (int index = 1; index < argc; ++index) parsed.emplace_back(argv[index]);
    if (!ParseRuntimeArguments(parsed, &arguments)) return EXIT_FAILURE;
    return RuntimeOnce(arguments);
  }
  Usage(argv[0]);
  return EXIT_FAILURE;
}
