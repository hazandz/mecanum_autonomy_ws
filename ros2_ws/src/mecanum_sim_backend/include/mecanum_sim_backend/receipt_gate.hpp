#pragma once

#include <array>
#include <cstdint>
#include <deque>
#include <optional>
#include <string>

namespace mecanum_sim_backend
{
struct ReceiptKey
{
  std::uint64_t publisher_instance_id{};
  std::uint64_t publish_sequence{};
};

struct ReceiptFacts
{
  std::string session_id;
  std::string config_hash;
  ReceiptKey key;
  std::uint64_t episode_generation{};
  std::uint32_t reset_epoch{};
  std::uint32_t runtime_generation{};
  std::uint64_t step_index{};
  std::string transition_id;
  std::uint8_t source{};
  std::uint64_t sequence{};
  std::uint64_t source_instance_id{};
  std::int64_t stamp_ns{};
  std::string frame_id;
  std::array<double, 6> twist{};
};

enum class GateDisposition
{
  Inhibited, Anchored, Applied, Duplicate, Rejected, Faulted
};

struct GateResult
{
  GateDisposition disposition{GateDisposition::Inhibited};
  std::string reason;
  std::optional<ReceiptFacts> accepted;
  bool refresh_watchdog{};
};

struct GateBinding
{
  std::string session_id;
  std::string config_hash;
  std::string frame_id{"base_link"};
  std::uint64_t final_publisher_instance_id{};
  std::int64_t barrier_stamp_ns{};
  std::uint64_t episode_generation{};
  std::uint32_t reset_epoch{};
  std::uint32_t runtime_generation{};
  std::uint64_t safe_stop_source_instance_id{};
  std::uint64_t next_safe_stop_sequence{};
  std::uint64_t policy_source_instance_id{};
  std::uint64_t next_policy_sequence{};
  std::uint64_t expected_step_index{};
  std::string expected_transition_id;
  std::int64_t max_ros_age_ns{500'000'000};
  std::int64_t max_steady_age_ns{500'000'000};
  double max_vx{0.25};
  double max_vy{0.20};
  double max_wz{0.80};
};

class ReceiptGate
{
public:
  static constexpr std::size_t kQueueCapacity = 128;
  static constexpr std::int64_t kWatchdogNs = 100'000'000;
  explicit ReceiptGate(GateBinding binding);
  bool Enqueue(ReceiptFacts receipt, std::int64_t receive_steady_ns);
  GateResult ConsumeNext(std::int64_t now_ros_ns, std::int64_t now_steady_ns);
  bool WatchdogExpired(std::int64_t now_steady_ns) const;
  void SetExpectedPolicyStep(std::uint64_t step_index,
                             std::uint64_t source_sequence,
                             std::string transition_id);
  void Invalidate(std::string reason);
  bool Faulted() const;
  std::uint64_t Watermark() const;
  std::int64_t LastAcceptedSteadyNs() const;

private:
  struct QueuedReceipt { ReceiptFacts facts; std::int64_t receive_steady_ns{}; };
  GateResult Fault(std::string reason);
  bool ValidPayload(const ReceiptFacts &, std::string &) const;
  static bool Equal(const ReceiptFacts &, const ReceiptFacts &);
  GateBinding binding_;
  std::deque<QueuedReceipt> queue_;
  std::optional<ReceiptFacts> last_receipt_;
  std::uint64_t watermark_{};
  std::int64_t last_accepted_steady_ns_{};
  bool anchored_{};
  bool faulted_{};
  std::string fault_reason_;
};
}  // namespace mecanum_sim_backend
