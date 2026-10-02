#ifndef S3_D3_ECS_CONTACT_DIAGNOSTIC_COLLECTOR_HH_
#define S3_D3_ECS_CONTACT_DIAGNOSTIC_COLLECTOR_HH_

#include <condition_variable>
#include <filesystem>
#include <functional>
#include <mutex>

#include <gz/transport/Node.hh>

#include "s3_d3_ecs_contact_diagnostic/core.hh"

namespace s3_d3::ecs_contact
{
enum class CollectorOutcome {
  kWaiting, kPersisted, kReceiptUnconfirmed, kInvalidReceipt, kDuplicateReceipt,
  kPersistenceFailure, kSubscribeFailure};

class CollectorLifecycle {
  public: using NowSteadyNs = std::function<std::int64_t()>;
  public: CollectorLifecycle(DiagnosticConfig _config, std::filesystem::path _output_directory,
      NowSteadyNs _now_steady_ns);
  public: bool HandleRaw(const char *_data, std::size_t _size, const std::string &_topic,
      const std::string &_type);
  public: void ExpireIfNeeded();
  public: CollectorOutcome Outcome() const;
  public: bool IsTerminal() const;
  private: bool SealOuterFailure(CollectorOutcome _outcome, const std::string &_reason);
  private: DiagnosticConfig config_;
  private: std::filesystem::path output_directory_;
  private: NowSteadyNs now_steady_ns_;
  private: std::int64_t receipt_deadline_steady_ns_{};
  private: CollectorOutcome outcome_{CollectorOutcome::kWaiting};
};

class ReceiptCollector {
  public: explicit ReceiptCollector(DiagnosticConfig _config,
      std::filesystem::path _output_directory);
  public: bool Subscribe();
  public: int WaitForTerminal();
  public: bool Accepted() const;
  private: void HandleRaw(const char *_data, std::size_t _size,
      const gz::transport::MessageInfo &_info);
  private: DiagnosticConfig config_;
  private: gz::transport::Node node_;
  private: CollectorLifecycle lifecycle_;
  private: mutable std::mutex mutex_;
  private: std::condition_variable terminal_cv_;
};

struct CollectorCommandLine { DiagnosticConfig config; std::filesystem::path output_directory; };
bool ParseCollectorCommandLine(int _argc, char **_argv,
    CollectorCommandLine *_command_line, std::string *_reason);
}  // namespace s3_d3::ecs_contact

#endif
