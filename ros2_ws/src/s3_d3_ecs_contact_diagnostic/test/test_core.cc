#include <algorithm>
#include <filesystem>
#include <functional>
#include <fstream>
#include <vector>
#include <string>

#include <gtest/gtest.h>

#include "s3_d3_ecs_contact_diagnostic/collector.hh"
#include "s3_d3_ecs_contact_diagnostic/core.hh"
#include "s3_d3_ecs_contact_diagnostic/run_spec.hh"

namespace s3_d3::ecs_contact
{
namespace
{
DiagnosticConfig Config()
{
  DiagnosticConfig config;
  config.receipt_topic = "/s3_d3/test/receipt"; config.run_id = "run_1234";
  config.world_name = "world_demo"; config.model_name = "ROBOT_URDF_final";
  config.link_name = "base_link"; config.sensor_name = "s3_d3_base_contact_sensor";
  config.plugin_source_sha256 = std::string(64, 'a'); config.plugin_binary_sha256 = std::string(64, 'b');
  config.collector_source_sha256 = std::string(64, 'c'); config.collector_binary_sha256 = std::string(64, 'd');
  config.base_world_template_sha256 = std::string(64, 'e'); config.native_model_sha256 = std::string(64, 'f');
  config.system_wait_timeout_sim_time_ns = 1; config.system_delivery_wait_timeout_steady_ns = 1;
  config.collector_receipt_wait_timeout_steady_ns = 1; config.collector_persist_timeout_steady_ns = 1;
  return config;
}

HierarchyObservation Complete()
{
  HierarchyObservation value;
  value.model_exact_count = value.link_exact_count = value.sensor_exact_count = value.collision_exact_count = 1;
  value.world_id = 1; value.model_id = 2; value.link_id = 3; value.sensor_id = 4; value.collision_id = 5;
  value.link_parent_id = 2; value.sensor_parent_id = 3; value.collision_parent_id = 3;
  value.world_id_present = value.model_id_present = value.link_id_present = value.sensor_id_present = value.collision_id_present = true;
  value.link_parent_id_present = value.sensor_parent_id_present = value.collision_parent_id_present = true;
  value.link_parent_matches = value.sensor_parent_matches = value.collision_parent_matches = true;
  value.contact_component_present = value.contact_element_present = value.collision_element_present = true;
  value.configured_collision_target = "s3_d3_base_contact_collision";
  value.collision_name = value.configured_collision_target;
  return value;
}

EcsContactSensorDiagnosticReceipt ValidReceipt()
{
  auto receipt = EvaluateHierarchy(Config(), Complete());
  receipt.set_first_postupdate_sim_time_ns(1); receipt.set_first_postupdate_sim_time_present(true);
  receipt.set_terminal_sim_time_ns(2); receipt.set_terminal_sim_time_present(true);
  receipt.set_first_postupdate_steady_time_ns(3); receipt.set_first_postupdate_steady_time_present(true);
  receipt.set_terminal_steady_time_ns(4); receipt.set_terminal_steady_time_present(true);
  return receipt;
}

std::filesystem::path TemporaryDirectory(const std::string &name)
{
  const auto path = std::filesystem::temp_directory_path() / name;
  std::filesystem::remove_all(path); std::filesystem::create_directory(path); return path;
}
}  // namespace

TEST(ConfigTest, RejectsMissingMalformedAndTraversalFields)
{
  auto config = Config(); EXPECT_TRUE(ValidateConfig(config, nullptr));
  config.receipt_topic = "/bad/../topic"; EXPECT_FALSE(ValidateConfig(config, nullptr));
  config = Config(); config.run_id = "line\nbreak"; EXPECT_FALSE(ValidateConfig(config, nullptr));
  config = Config(); config.collector_binary_sha256.clear(); EXPECT_FALSE(ValidateConfig(config, nullptr));
  config = Config(); config.collector_persist_timeout_steady_ns = 0; EXPECT_FALSE(ValidateConfig(config, nullptr));
}

TEST(HierarchyTest, EmitsEveryLockedTerminalStatusWithExplicitReasons)
{
  const auto config = Config(); auto observation = Complete();
  const std::vector<std::pair<HierarchyObservation, EcsContactSensorDiagnosticReceipt::TerminalStatus>> cases = {
    {observation, EcsContactSensorDiagnosticReceipt::ECS_SENSOR_TARGET_COLLISION_CHILD_OBSERVED},
    {[&] { auto x = observation; x.model_exact_count = 0; return x; }(), EcsContactSensorDiagnosticReceipt::ECS_MODEL_UNCONFIRMED},
    {[&] { auto x = observation; x.link_exact_count = 0; return x; }(), EcsContactSensorDiagnosticReceipt::ECS_LINK_UNCONFIRMED},
    {[&] { auto x = observation; x.sensor_exact_count = 0; return x; }(), EcsContactSensorDiagnosticReceipt::ECS_SENSOR_UNCONFIRMED},
    {[&] { auto x = observation; x.contact_component_present = false; return x; }(), EcsContactSensorDiagnosticReceipt::ECS_CONTACT_COMPONENT_MISSING},
    {[&] { auto x = observation; x.configured_collision_target.clear(); return x; }(), EcsContactSensorDiagnosticReceipt::ECS_CONTACT_CONFIGURATION_INCOMPLETE},
    {[&] { auto x = observation; x.collision_exact_count = 0; return x; }(), EcsContactSensorDiagnosticReceipt::ECS_TARGET_COLLISION_CHILD_UNCONFIRMED},
  };
  for (const auto &[input, status] : cases) {
    const auto receipt = EvaluateHierarchy(config, input);
    EXPECT_EQ(receipt.terminal_status(), status);
    EXPECT_EQ(receipt.reason_code(), ExpectedReasonCode(status));
  }
  EXPECT_EQ(ExpectedReasonCode(EcsContactSensorDiagnosticReceipt::TERMINAL_STATUS_UNSPECIFIED),
      EcsContactSensorDiagnosticReceipt::REASON_CODE_UNSPECIFIED);
}

TEST(ReceiptTest, RejectsMissingEveryRequiredProvenanceClass)
{
  const auto config = Config(); const auto receipt = ValidReceipt();
  EXPECT_TRUE(ValidateReceipt(receipt, config, nullptr));
  auto wrong = receipt; wrong.clear_collector_source_sha256(); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.clear_collector_binary_sha256(); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.set_first_postupdate_sim_time_present(false); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.set_world_id_present(false); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.set_sensor_id(0); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.set_terminal_steady_time_ns(-1); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.set_terminal_sim_time_ns(0); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
  wrong = receipt; wrong.set_reason_code(EcsContactSensorDiagnosticReceipt::CONTACT_COMPONENT_NOT_PRESENT); EXPECT_FALSE(ValidateReceipt(wrong, config, nullptr));
}

TEST(DeliveryTest, SealsOnlyAfterOnePublishResultOrTimeout)
{
  DeliveryGate gate; const auto receipt = ValidReceipt();
  EXPECT_TRUE(gate.SealSnapshot(receipt)); EXPECT_FALSE(gate.SealSnapshot(receipt));
  EXPECT_FALSE(gate.CanPublish(false)); EXPECT_TRUE(gate.CanPublish(true));
  EXPECT_FALSE(gate.CompletePublish(false)); EXPECT_EQ(gate.Outcome(), DeliveryOutcome::kPublishFailed);
  EXPECT_EQ(gate.State(), DeliveryState::kDeliverySealed); EXPECT_EQ(gate.PublishAttempts(), 1U);
  EXPECT_FALSE(gate.CompletePublish(true));
  DeliveryGate deadline; ASSERT_TRUE(deadline.SealSnapshot(receipt)); deadline.SealDeliveryWithoutPublish();
  EXPECT_EQ(deadline.Outcome(), DeliveryOutcome::kConnectionDeadlineExpired); EXPECT_EQ(deadline.PublishAttempts(), 0U);
}

TEST(PersistenceTest, CommitsOneAtomicBundleAndNoOverwrite)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_persist_success");
  const auto receipt = ValidReceipt(); std::string raw; ASSERT_TRUE(receipt.SerializeToString(&raw));
  ASSERT_TRUE(DurableReceiptStore::PersistAccepted(directory, Config(), receipt, raw, nullptr));
  const auto bundle = directory / "ecs_contact_receipt_bundle";
  EXPECT_TRUE(std::filesystem::is_directory(bundle));
  for (const auto &name : {"ecs_contact_receipt.raw.pb", "ecs_contact_receipt.raw.sha256", "ecs_contact_receipt.normalized.pb", "ecs_contact_receipt.json", "ecs_contact_receipt_collector_metadata.json"}) EXPECT_TRUE(std::filesystem::is_regular_file(bundle / name));
  EXPECT_FALSE(DurableReceiptStore::PersistAccepted(directory, Config(), receipt, raw, nullptr));
  std::filesystem::remove_all(directory);
}

TEST(PersistenceTest, FaultsNeverCommitSuccessBundle)
{
  const auto receipt = ValidReceipt(); std::string raw; ASSERT_TRUE(receipt.SerializeToString(&raw));
  const std::vector<DurableReceiptStore::FailurePoint> faults = {
    DurableReceiptStore::FailurePoint::kRawWrite, DurableReceiptStore::FailurePoint::kRawHashWrite,
    DurableReceiptStore::FailurePoint::kNormalizedWrite, DurableReceiptStore::FailurePoint::kJsonWrite,
    DurableReceiptStore::FailurePoint::kMetadataWrite, DurableReceiptStore::FailurePoint::kFileFsync,
    DurableReceiptStore::FailurePoint::kFileClose, DurableReceiptStore::FailurePoint::kStagingDirectoryFsync,
    DurableReceiptStore::FailurePoint::kCommit};
  for (std::size_t index = 0; index < faults.size(); ++index) {
    const auto directory = TemporaryDirectory("s3_d3_ecs_contact_fault_" + std::to_string(index));
    EXPECT_FALSE(DurableReceiptStore::PersistAccepted(directory, Config(), receipt, raw, nullptr, faults[index]));
    EXPECT_FALSE(std::filesystem::exists(directory / "ecs_contact_receipt_bundle"));
    std::filesystem::remove_all(directory);
  }
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_eintr");
  EXPECT_TRUE(DurableReceiptStore::PersistAccepted(directory, Config(), receipt, raw, nullptr, DurableReceiptStore::FailurePoint::kWriteEintrOnce));
  std::filesystem::remove_all(directory);
}

TEST(PersistenceTest, RejectsSymlinkAndOuterFailureIsNotEcsStatus)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_persist_symlink");
  const auto link = directory.parent_path() / "s3_d3_ecs_contact_persist_link";
  std::filesystem::remove(link); std::filesystem::create_directory_symlink(directory, link);
  const auto receipt = ValidReceipt(); std::string raw; ASSERT_TRUE(receipt.SerializeToString(&raw));
  EXPECT_FALSE(DurableReceiptStore::PersistAccepted(link, Config(), receipt, raw, nullptr));
  EXPECT_TRUE(DurableReceiptStore::PersistFailure(directory, Config(), "INVALID_EVIDENCE_PERSISTENCE_FAILURE", nullptr));
  EXPECT_TRUE(std::filesystem::exists(directory / "ecs_contact_receipt_failure.json"));
  std::filesystem::remove(link); std::filesystem::remove_all(directory);
}

TEST(CollectorLifecycleTest, DeadlineProducesOuterReceiptUnconfirmedWithoutSuccessBundle)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_no_receipt");
  std::int64_t now = 1;
  CollectorLifecycle lifecycle(Config(), directory, [&now] { return now; });
  now = 2;
  lifecycle.ExpireIfNeeded();
  EXPECT_TRUE(lifecycle.IsTerminal());
  EXPECT_EQ(lifecycle.Outcome(), CollectorOutcome::kReceiptUnconfirmed);
  EXPECT_TRUE(std::filesystem::exists(directory / "ecs_contact_receipt_failure.json"));
  EXPECT_FALSE(std::filesystem::exists(directory / "ecs_contact_receipt_bundle"));
  std::filesystem::remove_all(directory);
}

TEST(CollectorLifecycleTest, CapturesCallbackBytesBeforeParseAndSealsOneSuccess)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_raw_success");
  std::int64_t now = 1;
  CollectorLifecycle lifecycle(Config(), directory, [&now] { return now; });
  const auto receipt = ValidReceipt(); std::string raw;
  ASSERT_TRUE(receipt.SerializeToString(&raw));
  ASSERT_TRUE(lifecycle.HandleRaw(raw.data(), raw.size(), Config().receipt_topic,
      EcsContactSensorDiagnosticReceipt::descriptor()->full_name()));
  const auto bundle = directory / "ecs_contact_receipt_bundle";
  std::ifstream input(bundle / "ecs_contact_receipt.raw.pb", std::ios::binary);
  const std::string captured((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  EXPECT_EQ(captured, raw); EXPECT_EQ(Sha256Hex(captured), [] (const auto &path) { std::ifstream hash(path); std::string value; std::getline(hash, value); return value; }(bundle / "ecs_contact_receipt.raw.sha256"));
  EXPECT_FALSE(lifecycle.HandleRaw(raw.data(), raw.size(), Config().receipt_topic,
      EcsContactSensorDiagnosticReceipt::descriptor()->full_name()));
  EXPECT_EQ(lifecycle.Outcome(), CollectorOutcome::kPersisted);
  std::filesystem::remove_all(directory);
}

TEST(CollectorLifecycleTest, RejectsWrongTypeAndPersistenceDeadlineWithoutSuccessBundle)
{
  const auto receipt = ValidReceipt(); std::string raw; ASSERT_TRUE(receipt.SerializeToString(&raw));
  auto directory = TemporaryDirectory("s3_d3_ecs_contact_wrong_type"); std::int64_t now = 1;
  CollectorLifecycle wrong_type(Config(), directory, [&now] { return now; });
  EXPECT_FALSE(wrong_type.HandleRaw(raw.data(), raw.size(), Config().receipt_topic, "wrong.type"));
  EXPECT_EQ(wrong_type.Outcome(), CollectorOutcome::kInvalidReceipt);
  EXPECT_FALSE(std::filesystem::exists(directory / "ecs_contact_receipt_bundle"));
  std::filesystem::remove_all(directory);
  directory = TemporaryDirectory("s3_d3_ecs_contact_persist_deadline");
  std::vector<std::int64_t> readings{1, 2, 4}; std::size_t index = 0;
  CollectorLifecycle timeout(Config(), directory, [&readings, &index] { return readings.at(index++); });
  EXPECT_FALSE(timeout.HandleRaw(raw.data(), raw.size(), Config().receipt_topic,
      EcsContactSensorDiagnosticReceipt::descriptor()->full_name()));
  EXPECT_EQ(timeout.Outcome(), CollectorOutcome::kPersistenceFailure);
  EXPECT_FALSE(std::filesystem::exists(directory / "ecs_contact_receipt_bundle"));
  std::filesystem::remove_all(directory);
}

TEST(CollectorConfigTest, MissingRuntimeConfigFailsBeforeNodeConstruction)
{
  char program[] = "collector"; char mode[] = "--runtime-collector"; char *argv[] = {program, mode};
  CollectorCommandLine command_line; std::string reason;
  EXPECT_FALSE(ParseCollectorCommandLine(2, argv, &command_line, &reason));
  EXPECT_EQ(reason, "INVALID_COLLECTOR_RUNTIME_CONFIG");
}
}  // namespace s3_d3::ecs_contact


namespace s3_d3::ecs_contact
{

TEST(RendererTest, RendersExactlyOneTokenSetWithoutSelfReference)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_renderer_valid");
  const auto template_path = directory / "base.sdf.in";
  const auto output_directory = directory / "caller_created";
  std::filesystem::create_directory(output_directory);
  const std::string template_text =
      "<sdf version=\"1.11\"><world name=\"world_demo\"><plugin filename=\"S3D3EcsContactSensorDiagnosticSystem\" name=\"{{S3D3_PLUGIN_ALIAS}}\">"
      "<receipt_topic>{{S3D3_RECEIPT_TOPIC}}</receipt_topic><run_id>{{S3D3_RUN_ID}}</run_id><world_name>{{S3D3_WORLD_NAME}}</world_name>"
      "<model_name>{{S3D3_MODEL_NAME}}</model_name><link_name>{{S3D3_LINK_NAME}}</link_name><sensor_name>{{S3D3_SENSOR_NAME}}</sensor_name>"
      "<plugin_source_sha256>{{S3D3_PLUGIN_SOURCE_SHA256}}</plugin_source_sha256><plugin_binary_sha256>{{S3D3_PLUGIN_BINARY_SHA256}}</plugin_binary_sha256>"
      "<collector_source_sha256>{{S3D3_COLLECTOR_SOURCE_SHA256}}</collector_source_sha256><collector_binary_sha256>{{S3D3_COLLECTOR_BINARY_SHA256}}</collector_binary_sha256>"
      "<base_world_template_sha256>{{S3D3_BASE_WORLD_TEMPLATE_SHA256}}</base_world_template_sha256><native_model_sha256>{{S3D3_NATIVE_MODEL_SHA256}}</native_model_sha256>"
      "<system_wait_timeout_sim_time_ns>{{S3D3_SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS}}</system_wait_timeout_sim_time_ns>"
      "<system_delivery_wait_timeout_steady_ns>{{S3D3_SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS}}</system_delivery_wait_timeout_steady_ns>"
      "<collector_receipt_wait_timeout_steady_ns>{{S3D3_COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS}}</collector_receipt_wait_timeout_steady_ns>"
      "<collector_persist_timeout_steady_ns>{{S3D3_COLLECTOR_PERSIST_TIMEOUT_STEADY_NS}}</collector_persist_timeout_steady_ns></plugin></world></sdf>";
  { std::ofstream stream(template_path); stream << template_text; }
  auto config = Config(); config.base_world_template_sha256 = Sha256Hex(template_text);
  DiagnosticRunSpec spec{config, template_path, output_directory / "native_sdf_contact_diagnostic.rendered.sdf", output_directory / "renderer_result.json"};
  RenderedDiagnosticWorld result; std::string reason;
  ASSERT_TRUE(RenderDiagnosticWorld(spec, &result, &reason)) << reason;
  EXPECT_EQ(result.base_world_template_sha256, config.base_world_template_sha256);
  EXPECT_NE(result.rendered_world_sha256, result.base_world_template_sha256);
  std::ifstream result_receipt(spec.result_receipt); const std::string receipt((std::istreambuf_iterator<char>(result_receipt)), {});
  EXPECT_NE(receipt.find("s3_d3_renderer_result/v1"), std::string::npos);
  EXPECT_NE(receipt.find(config.run_id), std::string::npos);
  EXPECT_NE(receipt.find(std::filesystem::canonical(template_path).string()), std::string::npos);
  EXPECT_NE(receipt.find((std::filesystem::canonical(output_directory) / spec.rendered_world.filename()).string()), std::string::npos);
  EXPECT_NE(receipt.find(result.base_world_template_sha256), std::string::npos);
  EXPECT_NE(receipt.find(result.rendered_world_sha256), std::string::npos);
  std::ifstream rendered(spec.rendered_world); const std::string text((std::istreambuf_iterator<char>(rendered)), {});
  EXPECT_EQ(text.find("{{S3D3_"), std::string::npos);
  EXPECT_NE(text.find(config.base_world_template_sha256), std::string::npos);
  EXPECT_FALSE(std::filesystem::exists(directory / ".s3d3-render-XXXXXX"));
  std::filesystem::remove_all(directory);
}

TEST(RendererTest, RejectsDuplicateUnknownUnsafeAndSelfReferenceInputs)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_renderer_reject");
  const auto output_directory = directory / "caller_created";
  std::filesystem::create_directory(output_directory);
  const auto output = output_directory / "native_sdf_contact_diagnostic.rendered.sdf";
  const auto template_path = directory / "base.sdf.in";
  const std::string valid =
      "{{S3D3_RECEIPT_TOPIC}}{{S3D3_RUN_ID}}{{S3D3_WORLD_NAME}}{{S3D3_MODEL_NAME}}{{S3D3_LINK_NAME}}{{S3D3_SENSOR_NAME}}"
      "{{S3D3_PLUGIN_SOURCE_SHA256}}{{S3D3_PLUGIN_BINARY_SHA256}}{{S3D3_COLLECTOR_SOURCE_SHA256}}{{S3D3_COLLECTOR_BINARY_SHA256}}"
      "{{S3D3_BASE_WORLD_TEMPLATE_SHA256}}{{S3D3_NATIVE_MODEL_SHA256}}{{S3D3_SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS}}"
      "{{S3D3_SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS}}{{S3D3_COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS}}"
      "{{S3D3_COLLECTOR_PERSIST_TIMEOUT_STEADY_NS}}{{S3D3_PLUGIN_ALIAS}}";
  auto config = Config();
  { std::ofstream stream(template_path); stream << valid + "{{S3D3_RUN_ID}}"; }
  config.base_world_template_sha256 = Sha256Hex(valid + "{{S3D3_RUN_ID}}");
  DiagnosticRunSpec spec{config, template_path, output, output_directory / "renderer_result.json"}; std::string reason; RenderedDiagnosticWorld result;
  EXPECT_FALSE(RenderDiagnosticWorld(spec, &result, &reason));
  { std::ofstream stream(template_path); stream << valid + "{{S3D3_UNKNOWN}}"; }
  config.base_world_template_sha256 = Sha256Hex(valid + "{{S3D3_UNKNOWN}}"); spec.config = config;
  EXPECT_FALSE(RenderDiagnosticWorld(spec, &result, &reason));
  { std::ofstream stream(template_path); stream << valid; }
  config.base_world_template_sha256 = std::string(64, '0'); spec.config = config;
  EXPECT_FALSE(RenderDiagnosticWorld(spec, &result, &reason));
  std::filesystem::create_symlink(template_path, directory / "symlink.sdf.in");
  spec.base_world_template = directory / "symlink.sdf.in";
  EXPECT_FALSE(ValidateDiagnosticRunSpec(spec, &reason));
  spec.base_world_template = template_path;
  std::filesystem::create_symlink(template_path, output);
  EXPECT_FALSE(ValidateDiagnosticRunSpec(spec, &reason));
  std::filesystem::remove(output);
  { std::ofstream stream(template_path); stream << valid; }
  config.base_world_template_sha256 = Sha256Hex(valid); spec.config = config;
  ASSERT_TRUE(RenderDiagnosticWorld(spec, &result, &reason)) << reason;
  EXPECT_FALSE(RenderDiagnosticWorld(spec, &result, &reason));
  std::filesystem::remove_all(directory);
}

TEST(RendererTest, RejectsExistingOrSymlinkResultReceiptAndStrictInvalidArguments)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_renderer_result_reject");
  const auto output_directory = directory / "caller_created";
  std::filesystem::create_directory(output_directory);
  const auto template_path = directory / "base.sdf.in";
  const std::string template_text =
      "{{S3D3_RECEIPT_TOPIC}}{{S3D3_RUN_ID}}{{S3D3_WORLD_NAME}}{{S3D3_MODEL_NAME}}{{S3D3_LINK_NAME}}{{S3D3_SENSOR_NAME}}"
      "{{S3D3_PLUGIN_SOURCE_SHA256}}{{S3D3_PLUGIN_BINARY_SHA256}}{{S3D3_COLLECTOR_SOURCE_SHA256}}{{S3D3_COLLECTOR_BINARY_SHA256}}"
      "{{S3D3_BASE_WORLD_TEMPLATE_SHA256}}{{S3D3_NATIVE_MODEL_SHA256}}{{S3D3_SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS}}"
      "{{S3D3_SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS}}{{S3D3_COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS}}"
      "{{S3D3_COLLECTOR_PERSIST_TIMEOUT_STEADY_NS}}{{S3D3_PLUGIN_ALIAS}}";
  { std::ofstream stream(template_path); stream << template_text; }
  auto config = Config(); config.base_world_template_sha256 = Sha256Hex(template_text);
  const auto output = output_directory / "native_sdf_contact_diagnostic.rendered.sdf";
  const auto result_path = output_directory / "renderer_result.json";
  { std::ofstream stream(result_path); stream << "already exists"; }
  DiagnosticRunSpec spec{config, template_path, output, result_path}; std::string reason; RenderedDiagnosticWorld result;
  EXPECT_FALSE(RenderDiagnosticWorld(spec, &result, &reason));
  std::filesystem::remove(result_path);
  std::filesystem::create_symlink(template_path, result_path);
  EXPECT_FALSE(ValidateDiagnosticRunSpec(spec, &reason));
  std::filesystem::remove(result_path);
  char command[] = "renderer"; char mode[] = "--render-diagnostic-world"; char unknown[] = "--unknown"; char value[] = "x";
  char *unknown_argv[] = {command, mode, unknown, value};
  EXPECT_FALSE(ParseWorldRendererCommandLine(4, unknown_argv, &spec, &reason));
  char duplicate[] = "--template"; char *duplicate_argv[] = {command, mode, duplicate, value, duplicate, value};
  EXPECT_FALSE(ParseWorldRendererCommandLine(6, duplicate_argv, &spec, &reason));
  std::filesystem::remove_all(directory);
}

TEST(RendererTest, StrictParserRejectsTrailingGarbageSignedTimeoutAndUnsafePaths)
{
  const auto directory = TemporaryDirectory("s3_d3_ecs_contact_renderer_parser");
  const auto output_directory = directory / "caller_created";
  std::filesystem::create_directory(output_directory);
  const auto template_path = directory / "base.sdf.in";
  const std::string text =
      "{{S3D3_RECEIPT_TOPIC}}{{S3D3_RUN_ID}}{{S3D3_WORLD_NAME}}{{S3D3_MODEL_NAME}}{{S3D3_LINK_NAME}}{{S3D3_SENSOR_NAME}}"
      "{{S3D3_PLUGIN_SOURCE_SHA256}}{{S3D3_PLUGIN_BINARY_SHA256}}{{S3D3_COLLECTOR_SOURCE_SHA256}}{{S3D3_COLLECTOR_BINARY_SHA256}}"
      "{{S3D3_BASE_WORLD_TEMPLATE_SHA256}}{{S3D3_NATIVE_MODEL_SHA256}}{{S3D3_SYSTEM_WAIT_TIMEOUT_SIM_TIME_NS}}"
      "{{S3D3_SYSTEM_DELIVERY_WAIT_TIMEOUT_STEADY_NS}}{{S3D3_COLLECTOR_RECEIPT_WAIT_TIMEOUT_STEADY_NS}}"
      "{{S3D3_COLLECTOR_PERSIST_TIMEOUT_STEADY_NS}}{{S3D3_PLUGIN_ALIAS}}";
  { std::ofstream stream(template_path); stream << text; }
  const auto hash = Sha256Hex(text);
  std::vector<std::string> arguments = {"renderer", "--render-diagnostic-world", "--template", template_path.string(),
      "--output", (output_directory / "native_sdf_contact_diagnostic.rendered.sdf").string(), "--result", (output_directory / "renderer_result.json").string(),
      "--receipt-topic", "/s3_d3/test/receipt", "--run-id", "run_1234", "--world-name", "world_demo", "--model-name", "ROBOT_URDF_final",
      "--link-name", "base_link", "--sensor-name", "s3_d3_base_contact_sensor", "--plugin-source-sha256", std::string(64, 'a'),
      "--plugin-binary-sha256", std::string(64, 'b'), "--collector-source-sha256", std::string(64, 'c'), "--collector-binary-sha256", std::string(64, 'd'),
      "--base-world-template-sha256", hash, "--native-model-sha256", std::string(64, 'f'),
      "--system-wait-timeout-sim-time-ns", "1", "--system-delivery-wait-timeout-steady-ns", "2",
      "--collector-receipt-wait-timeout-steady-ns", "3", "--collector-persist-timeout-steady-ns", "4"};
  auto parse = [&arguments]() {
    std::vector<char *> argv; for (auto &argument : arguments) argv.push_back(argument.data());
    DiagnosticRunSpec spec; std::string reason;
    return ParseWorldRendererCommandLine(static_cast<int>(argv.size()), argv.data(), &spec, &reason);
  };
  EXPECT_TRUE(parse());
  auto set_value = [&arguments](const std::string &key, const std::string &value) { arguments.at(static_cast<std::size_t>(std::find(arguments.begin(), arguments.end(), key) - arguments.begin() + 1)) = value; };
  set_value("--system-wait-timeout-sim-time-ns", "1junk"); EXPECT_FALSE(parse());
  set_value("--system-wait-timeout-sim-time-ns", "-1"); EXPECT_FALSE(parse());
  set_value("--system-wait-timeout-sim-time-ns", "1"); set_value("--run-id", "../escape"); EXPECT_FALSE(parse());
  set_value("--run-id", "run_1234"); set_value("--output", "relative.sdf"); EXPECT_FALSE(parse());
  set_value("--output", (output_directory / ".." / "escape.sdf").string()); EXPECT_FALSE(parse());
  std::filesystem::remove_all(directory);
}

}  // namespace s3_d3::ecs_contact
