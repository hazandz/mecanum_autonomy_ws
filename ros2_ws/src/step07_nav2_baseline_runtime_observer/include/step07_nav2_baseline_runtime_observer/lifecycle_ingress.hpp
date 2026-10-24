#pragma once

#include <condition_variable>
#include <cstdint>
#include <deque>
#include <map>
#include <optional>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <vector>

#include "nlohmann/json.hpp"

namespace step07_observer {

struct LifecyclePublisherEndpoint {
  std::string topic;
  std::string type;
  std::string node_name;
  std::string node_namespace;
  std::string gid;
  int reliability{-1};
  int durability{-1};
  int history{-1};
  int depth{-1};
};

class LifecycleIngress final {
 public:
  using Json = nlohmann::json;
  static constexpr size_t kQueueCapacity = 64;
  static constexpr size_t kHistoryCapacity = 64;
  static constexpr size_t kRecordMaxBytes = 8192;
  static constexpr size_t kArtifactMaxBytes = 1048576;
  static constexpr size_t kReferenceMaxBytes = 8192;
  static constexpr size_t kReferenceMaxCount = 5;
  static constexpr size_t kPendingReferenceMaxCount = 1;

  LifecycleIngress(std::string live_path, std::string references_path,
                   std::string final_path, std::string invocation_id,
                   std::string collector_session_id, std::string config_hash);
  ~LifecycleIngress();
  LifecycleIngress(const LifecycleIngress &) = delete;
  LifecycleIngress &operator=(const LifecycleIngress &) = delete;

  bool pin_endpoint(const std::vector<LifecyclePublisherEndpoint> &publishers);
  bool admit(const Json &payload, const std::string &message_gid,
             int64_t ros_stamp_ns, int64_t receive_monotonic_ns);
  bool ready() const;
  bool failed() const;
  std::string failure_literal() const;
  Json live_document() const;
  Json finalize();

 private:
  void worker_loop();
  void process_references_locked(const Json &request);
  Json live_document_locked() const;
  void latch_failure_locked(const std::string &literal);
  bool write_atomic(const std::string &path, const Json &document, size_t maximum);
  bool read_strict(const std::string &path, Json &document, size_t maximum,
                   std::string &failure);

  const std::string live_path_;
  const std::string references_path_;
  const std::string final_path_;
  const std::string invocation_id_;
  const std::string session_id_;
  const std::string config_hash_;
  mutable std::mutex mutex_;
  std::condition_variable wake_;
  std::deque<Json> queue_;
  std::deque<Json> history_;
  std::map<uint64_t, Json> retained_;
  std::map<uint64_t, std::string> committed_;
  std::vector<Json> sample_references_;
  std::optional<std::pair<uint64_t, std::string>> pending_;
  Json request_ack_ = Json::object();
  uint64_t request_revision_{0};
  std::string request_digest_;
  std::string request_bytes_;
  Json endpoint_ = Json::object();
  std::string failure_;
  uint64_t next_record_index_{1};
  uint64_t last_sequence_{0};
  bool has_sequence_{false};
  bool endpoint_pinned_{false};
  bool stopping_{false};
  bool finalized_{false};
  std::thread worker_;
};

}  // namespace step07_observer
