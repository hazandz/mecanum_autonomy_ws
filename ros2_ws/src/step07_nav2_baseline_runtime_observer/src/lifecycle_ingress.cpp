#include "step07_nav2_baseline_runtime_observer/lifecycle_ingress.hpp"

#include <cerrno>
#include <cstring>
#include <filesystem>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <fstream>
#include <openssl/sha.h>
#include "rmw/qos_policy_kind.h"
#include "rmw/types.h"

namespace step07_observer {
namespace {
constexpr const char *kSchema = "mecanum.step07-run005.lifecycle-ingress/v1";
std::atomic<uint64_t> temp_counter{0};

bool parse_no_duplicate_keys(const std::string &raw, nlohmann::json &out) {
  std::map<int, std::set<std::string>> keys;
  auto callback = [&](int depth, nlohmann::json::parse_event_t event,
                      nlohmann::json &parsed) {
    if (event == nlohmann::json::parse_event_t::object_start) keys[depth].clear();
    if (event == nlohmann::json::parse_event_t::key) {
      const auto key = parsed.get<std::string>();
      if (!keys[depth].insert(key).second) return false;
    }
    if (event == nlohmann::json::parse_event_t::object_end) keys.erase(depth);
    return true;
  };
  try {
    out = nlohmann::json::parse(raw, callback, true, false);
    return out.is_object();
  } catch (...) {
    return false;
  }
}

std::string sha256_hex(const std::string &raw) {
  unsigned char digest[SHA256_DIGEST_LENGTH];
  SHA256(reinterpret_cast<const unsigned char *>(raw.data()), raw.size(), digest);
  static constexpr char hex[] = "0123456789abcdef";
  std::string out(SHA256_DIGEST_LENGTH * 2, '0');
  for (size_t i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
    out[i * 2] = hex[digest[i] >> 4];
    out[i * 2 + 1] = hex[digest[i] & 0x0f];
  }
  return out;
}

bool safe_regular_read(const std::string &path, size_t maximum, std::string &raw) {
  int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0) return false;
  struct stat status {};
  if (::fstat(fd, &status) != 0 || !S_ISREG(status.st_mode) ||
      status.st_size < 0 || static_cast<size_t>(status.st_size) > maximum) {
    ::close(fd);
    return false;
  }
  raw.clear();
  char buffer[4096];
  while (raw.size() <= maximum) {
    const auto count = ::read(fd, buffer, sizeof(buffer));
    if (count == 0) break;
    if (count < 0) {
      if (errno == EINTR) continue;
      ::close(fd);
      return false;
    }
    raw.append(buffer, static_cast<size_t>(count));
  }
  ::close(fd);
  return raw.size() <= maximum;
}
}  // namespace

LifecycleIngress::LifecycleIngress(std::string live_path, std::string references_path,
                                   std::string final_path, std::string invocation_id,
                                   std::string collector_session_id, std::string config_hash)
    : live_path_(std::move(live_path)), references_path_(std::move(references_path)),
      final_path_(std::move(final_path)), invocation_id_(std::move(invocation_id)),
      session_id_(std::move(collector_session_id)), config_hash_(std::move(config_hash)) {
  if (live_path_.empty() || references_path_.empty() || final_path_.empty() ||
      invocation_id_.empty() || session_id_.empty() || config_hash_.size() != 64) {
    throw std::invalid_argument("LIFECYCLE_INGRESS_IDENTITY_INVALID");
  }
  worker_ = std::thread(&LifecycleIngress::worker_loop, this);
}

LifecycleIngress::~LifecycleIngress() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    stopping_ = true;
  }
  wake_.notify_all();
  if (worker_.joinable()) worker_.join();
}

bool LifecycleIngress::pin_endpoint(const std::vector<LifecyclePublisherEndpoint> &publishers) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!failure_.empty()) return false;
  if (endpoint_pinned_) {
    if (publishers.size() != 1 || publishers.front().gid != endpoint_.value("publisher_gid", "") ||
        publishers.front().topic != endpoint_.value("topic", "") ||
        publishers.front().type != endpoint_.value("type", "") ||
        publishers.front().node_name != endpoint_.value("node_name", "") ||
        publishers.front().node_namespace != endpoint_.value("node_namespace", "")) {
      latch_failure_locked("LIFECYCLE_PUBLISHER_SET_OR_GID_CHANGED");
      return false;
    }
    return true;
  }
  if (publishers.empty()) {
    wake_.notify_one();
    return false;
  }
  if (publishers.size() != 1) {
    latch_failure_locked("LIFECYCLE_EXTRA_OR_AMBIGUOUS_PUBLISHER");
    wake_.notify_one();
    return false;
  }
  const auto &publisher = publishers.front();
  if (publisher.topic != "/mecanum/safety_lifecycle_state" ||
      publisher.type != "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState" ||
      publisher.node_name != "safety_lifecycle" || publisher.node_namespace != "/") {
    latch_failure_locked("LIFECYCLE_PUBLISHER_IDENTITY_MISMATCH");
    wake_.notify_one();
    return false;
  }
  if (publisher.gid.empty() || publisher.gid.size() != 2 * RMW_GID_STORAGE_SIZE ||
      std::all_of(publisher.gid.begin(), publisher.gid.end(), [](char c) { return c == '0'; })) {
    latch_failure_locked("LIFECYCLE_PUBLISHER_GID_UNAVAILABLE");
    wake_.notify_one();
    return false;
  }
  if (publisher.reliability != RMW_QOS_POLICY_RELIABILITY_RELIABLE ||
      publisher.durability != RMW_QOS_POLICY_DURABILITY_VOLATILE ||
      !((publisher.history == RMW_QOS_POLICY_HISTORY_KEEP_LAST && publisher.depth == 10) ||
        (publisher.history == RMW_QOS_POLICY_HISTORY_UNKNOWN && publisher.depth == 0))) {
    latch_failure_locked("LIFECYCLE_PUBLISHER_QOS_MISMATCH");
    wake_.notify_one();
    return false;
  }
  endpoint_ = Json{{"topic", publisher.topic}, {"type", publisher.type},
                   {"node_name", publisher.node_name},
                   {"node_namespace", publisher.node_namespace},
                   {"publisher_gid", publisher.gid},
                   {"reliability", publisher.reliability},
                   {"durability", publisher.durability},
                   {"history", publisher.history}, {"depth", publisher.depth},
                   {"qos_history_depth_status", publisher.history == RMW_QOS_POLICY_HISTORY_UNKNOWN
                       ? "UNOBSERVABLE" : "OBSERVED_MATCH"}};
  endpoint_pinned_ = true;
  wake_.notify_one();
  return true;
}

bool LifecycleIngress::admit(const Json &payload, const std::string &message_gid,
                             int64_t ros_stamp_ns, int64_t receive_monotonic_ns) {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!failure_.empty() || stopping_) return false;
  if (!endpoint_pinned_) return false;
  if (message_gid.empty() || message_gid != endpoint_.value("publisher_gid", "")) {
    latch_failure_locked("LIFECYCLE_MESSAGE_GID_MISMATCH");
    wake_.notify_one();
    return false;
  }
  if (!payload.is_object() || !payload.contains("sequence") || !payload["sequence"].is_number_unsigned()) {
    latch_failure_locked("LIFECYCLE_PAYLOAD_SCHEMA_INVALID");
    wake_.notify_one();
    return false;
  }
  const auto sequence = payload["sequence"].get<uint64_t>();
  if (has_sequence_ && sequence < last_sequence_) {
    latch_failure_locked("LIFECYCLE_BARRIER_SEQUENCE_REGRESSION");
    wake_.notify_one();
    return false;
  }
  if (receive_monotonic_ns <= 0 || ros_stamp_ns < 0) {
    latch_failure_locked("LIFECYCLE_RECEIVE_TIME_INVALID");
    wake_.notify_one();
    return false;
  }
  Json row{{"record_index", next_record_index_}, {"sequence", sequence},
           {"receive_time", {{"clock", "CLOCK_MONOTONIC"},
                              {"monotonic_ns", receive_monotonic_ns}}},
           {"ros_stamp_ns", ros_stamp_ns}, {"publisher_gid", message_gid},
           {"payload_provenance", "rclcpp::MessageInfo.publisher_gid"},
           {"payload", payload}, {"validity", "ADMITTED"}};
  if (row.dump().size() > kRecordMaxBytes) {
    latch_failure_locked("LIFECYCLE_ADMITTED_RECORD_OVERSIZE");
    wake_.notify_one();
    return false;
  }
  if (queue_.size() >= kQueueCapacity) {
    latch_failure_locked("LIFECYCLE_INGRESS_QUEUE_OVERFLOW");
    wake_.notify_one();
    return false;
  }
  ++next_record_index_;
  last_sequence_ = sequence;
  has_sequence_ = true;
  queue_.push_back(std::move(row));
  wake_.notify_one();
  return true;
}

bool LifecycleIngress::ready() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return endpoint_pinned_ && failure_.empty();
}

bool LifecycleIngress::failed() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return !failure_.empty();
}

std::string LifecycleIngress::failure_literal() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return failure_;
}

LifecycleIngress::Json LifecycleIngress::live_document() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return live_document_locked();
}

LifecycleIngress::Json LifecycleIngress::live_document_locked() const {
  Json rows = Json::array();
  for (const auto &row : history_) rows.push_back(row);
  Json refs = Json::array();
  for (const auto &[index, digest] : acknowledged_) refs.push_back(
      {{"record_index", index}, {"record_sha256", digest}});
  return Json{{"schema", kSchema}, {"schema_version", "1.0"},
      {"invocation_id", invocation_id_}, {"collector_session_id", session_id_},
      {"config_hash", config_hash_}, {"state", failure_.empty() ? (endpoint_pinned_ ? "READY" : "NOT_READY") : "FAILED"},
      {"failure", failure_.empty() ? Json(nullptr) : Json{{"literal", failure_}}},
      {"endpoint_binding", endpoint_}, {"records", rows},
      {"acknowledged_references", refs}, {"retained_reference_count", retained_.size()},
      {"record_index_next", next_record_index_}};
}

void LifecycleIngress::latch_failure_locked(const std::string &literal) {
  if (failure_.empty()) failure_ = literal;
}

bool LifecycleIngress::write_atomic(const std::string &path, const Json &document, size_t maximum) {
  const std::string raw = document.dump(-1, ' ', false, Json::error_handler_t::strict);
  if (raw.size() > maximum) return false;
  struct stat existing {};
  if (::lstat(path.c_str(), &existing) == 0 && S_ISLNK(existing.st_mode)) return false;
  const std::string temporary = path + ".tmp." + std::to_string(::getpid()) + "." +
      std::to_string(temp_counter.fetch_add(1));
  int fd = ::open(temporary.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0) return false;
  size_t written = 0;
  while (written < raw.size()) {
    const auto n = ::write(fd, raw.data() + written, raw.size() - written);
    if (n < 0) {
      if (errno == EINTR) continue;
      ::close(fd); ::unlink(temporary.c_str()); return false;
    }
    written += static_cast<size_t>(n);
  }
  const bool synced = ::fsync(fd) == 0;
  const bool closed = ::close(fd) == 0;
  if (!synced || !closed || ::rename(temporary.c_str(), path.c_str()) != 0) {
    ::unlink(temporary.c_str()); return false;
  }
  const auto parent = std::filesystem::path(path).parent_path();
  int dir = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (dir < 0) return false;
  const bool dir_synced = ::fsync(dir) == 0;
  ::close(dir);
  return dir_synced;
}

bool LifecycleIngress::read_strict(const std::string &path, Json &document,
                                   size_t maximum, std::string &failure) {
  std::string raw;
  if (!safe_regular_read(path, maximum, raw)) {
    failure = "LIFECYCLE_REFERENCE_READ_OR_SIZE_INVALID";
    return false;
  }
  if (raw.size() >= 3 && static_cast<unsigned char>(raw[0]) == 0xef &&
      static_cast<unsigned char>(raw[1]) == 0xbb && static_cast<unsigned char>(raw[2]) == 0xbf) {
    failure = "LIFECYCLE_REFERENCE_BOM_FORBIDDEN";
    return false;
  }
  if (!parse_no_duplicate_keys(raw, document)) {
    failure = "LIFECYCLE_REFERENCE_JSON_INVALID";
    return false;
  }
  return true;
}

void LifecycleIngress::process_references_locked(const Json &request) {
  if (request.is_null()) return;
  if (request.value("schema", "") != kSchema || request.value("schema_version", "") != "1.0" ||
      request.value("invocation_id", "") != invocation_id_ ||
      request.value("collector_session_id", "") != session_id_ ||
      !request.contains("references") || !request["references"].is_array() ||
      request["references"].size() > kReferenceMaxCount) {
    latch_failure_locked("LIFECYCLE_REFERENCE_IDENTITY_OR_SCHEMA_INVALID");
    return;
  }
  for (const auto &reference : request["references"]) {
    if (!reference.is_object() || !reference.contains("record_index") ||
        !reference["record_index"].is_number_unsigned() ||
        !reference.contains("record_sha256") || !reference["record_sha256"].is_string()) {
      latch_failure_locked("LIFECYCLE_REFERENCE_ROW_INVALID");
      return;
    }
    const auto index = reference["record_index"].get<uint64_t>();
    const auto digest = reference["record_sha256"].get<std::string>();
    const bool digest_hex = digest.size() == 64 && std::all_of(digest.begin(), digest.end(), [](char c) {
      return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
    if (index == 0 || !digest_hex ||
        (requested_.size() >= kReferenceMaxCount && !requested_.count(index))) {
      latch_failure_locked("LIFECYCLE_REFERENCE_LIMIT_OR_ID_INVALID");
      return;
    }
    requested_.insert(index);
    const auto pinned = retained_.find(index);
    if (pinned != retained_.end()) {
      if (sha256_hex(pinned->second.dump()) != digest)
        latch_failure_locked("LIFECYCLE_REFERENCE_HASH_MISMATCH");
      else acknowledged_[index] = digest;
      continue;
    }
    const auto row = std::find_if(history_.begin(), history_.end(), [&](const Json &candidate) {
      return candidate.value("record_index", uint64_t{0}) == index;
    });
    if (row == history_.end()) {
      if (index < next_record_index_ - kHistoryCapacity) latch_failure_locked("LIFECYCLE_REQUIRED_RECORD_EVICTED");
      continue;
    }
    if (sha256_hex(row->dump()) != digest) {
      latch_failure_locked("LIFECYCLE_REFERENCE_HASH_MISMATCH");
      return;
    }
    if (!retained_.count(index)) retained_[index] = *row;
    acknowledged_[index] = digest;
  }
}

void LifecycleIngress::worker_loop() {
  std::unique_lock<std::mutex> lock(mutex_);
  while (true) {
    wake_.wait_for(lock, std::chrono::milliseconds(10), [&] { return stopping_ || !queue_.empty(); });
    while (!queue_.empty()) {
      if (history_.size() >= kHistoryCapacity) {
        const auto oldest = history_.front().value("record_index", uint64_t{0});
        if (retained_.count(oldest)) {
          latch_failure_locked("LIFECYCLE_REQUIRED_RECORD_EVICTION_BLOCKED");
          queue_.clear();
          break;
        }
        history_.pop_front();
      }
      history_.push_back(std::move(queue_.front()));
      queue_.pop_front();
    }
    lock.unlock();
    Json request = nullptr;
    struct stat status {};
    if (::lstat(references_path_.c_str(), &status) == 0) {
      std::string read_failure;
      if (!read_strict(references_path_, request, kReferenceMaxBytes, read_failure)) {
        lock.lock(); latch_failure_locked(read_failure); lock.unlock();
      }
    } else if (errno != ENOENT) {
      lock.lock(); latch_failure_locked("LIFECYCLE_REFERENCE_STAT_FAILED"); lock.unlock();
    }
    lock.lock();
    process_references_locked(request);
    Json snapshot = live_document_locked();
    const bool stop_after_publish = stopping_;
    lock.unlock();
    const bool published = write_atomic(live_path_, snapshot, kArtifactMaxBytes);
    lock.lock();
    if (!published) latch_failure_locked("LIFECYCLE_LIVE_ARTIFACT_WRITE_FAILED");
    if (stop_after_publish) break;
  }
}

LifecycleIngress::Json LifecycleIngress::finalize() {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (finalized_) return live_document_locked();
    stopping_ = true;
  }
  wake_.notify_all();
  if (worker_.joinable()) worker_.join();
  std::unique_lock<std::mutex> lock(mutex_);
  Json retained = Json::array();
  for (const auto &[index, row] : retained_) {
    retained.push_back({{"record_index", index}, {"record", row},
                        {"record_sha256", acknowledged_.at(index)}});
  }
  Json document{{"schema", kSchema}, {"schema_version", "1.0"},
      {"invocation_id", invocation_id_}, {"collector_session_id", session_id_},
      {"config_hash", config_hash_}, {"state", failure_.empty() ? "FINALIZED" : "FAILED"},
      {"failure", failure_.empty() ? Json(nullptr) : Json{{"literal", failure_}}},
      {"endpoint_binding", endpoint_}, {"retained_references", retained},
      {"record_count_seen", next_record_index_ - 1}, {"record_count_retained", history_.size()}};
  if (document.dump().size() > kArtifactMaxBytes) {
    latch_failure_locked("LIFECYCLE_FINAL_ARTIFACT_WRITE_FAILED");
    document["state"] = "FAILED";
    document["failure"] = Json{{"literal", failure_}};
  }
  finalized_ = true;
  lock.unlock();
  if (!write_atomic(final_path_, document, kArtifactMaxBytes)) {
    lock.lock();
    latch_failure_locked("LIFECYCLE_FINAL_ARTIFACT_WRITE_FAILED");
    lock.unlock();
    document["state"] = "FAILED";
    document["failure"] = Json{{"literal", "LIFECYCLE_FINAL_ARTIFACT_WRITE_FAILED"}};
  }
  return document;
}

}  // namespace step07_observer
