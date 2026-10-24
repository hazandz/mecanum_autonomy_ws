#include "step07_nav2_baseline_runtime_observer/lifecycle_ingress.hpp"

#include <gtest/gtest.h>
#include <rmw/qos_policy_kind.h>
#include <rmw/types.h>
#include <openssl/sha.h>

#include <chrono>
#include <filesystem>
#include <stdexcept>
#include <thread>
#include <unistd.h>
#include <utility>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <sys/wait.h>
#include <cstdlib>

namespace {
using step07_observer::LifecycleIngress;
using step07_observer::LifecyclePublisherEndpoint;

std::filesystem::path make_directory() {
  std::string pattern = "/tmp/step07-lifecycle-ingress-test-XXXXXX";
  auto *created = ::mkdtemp(pattern.data());
  if (created == nullptr) throw std::runtime_error("mkdtemp failed");
  return created;
}

LifecyclePublisherEndpoint endpoint(std::string gid = std::string(2 * RMW_GID_STORAGE_SIZE, 'a')) {
  return {"/mecanum/safety_lifecycle_state",
          "mecanum_nav_rl_interfaces/msg/SafetyLifecycleState",
          "safety_lifecycle", "/", std::move(gid),
          RMW_QOS_POLICY_RELIABILITY_RELIABLE,
          RMW_QOS_POLICY_DURABILITY_VOLATILE,
          RMW_QOS_POLICY_HISTORY_KEEP_LAST, 10};
}

bool wait_for_record(LifecycleIngress &ingress, size_t count) {
  for (int i = 0; i < 100; ++i) {
    if (ingress.live_document().at("records").size() >= count) return true;
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return false;
}

std::string sha256(const std::string &raw) {
  unsigned char digest[SHA256_DIGEST_LENGTH];
  SHA256(reinterpret_cast<const unsigned char *>(raw.data()), raw.size(), digest);
  std::ostringstream out;
  out << std::hex << std::setfill('0');
  for (auto byte : digest) out << std::setw(2) << static_cast<unsigned>(byte);
  return out.str();
}

void write_request(const std::filesystem::path &path, LifecycleIngress::Json request) {
  request["request_digest"] = sha256(request.dump(-1, ' ', false,
      LifecycleIngress::Json::error_handler_t::strict));
  const auto temporary = path.string() + ".tmp";
  { std::ofstream stream(temporary, std::ios::binary | std::ios::trunc); stream << request.dump(); }
  std::filesystem::rename(temporary, path);
}

bool wait_for_ack(LifecycleIngress &ingress, uint64_t revision) {
  for (int i = 0; i < 100; ++i) {
    const auto ack = ingress.live_document().value("reference_ack", LifecycleIngress::Json::object());
    if (ack.value("revision", uint64_t{0}) == revision && ack.value("status", "") == "ACKNOWLEDGED") return true;
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return false;
}

bool wait_for_next_record(LifecycleIngress &ingress, uint64_t next_index) {
  for (int i = 0; i < 100; ++i) {
    if (ingress.live_document().value("record_index_next", uint64_t{0}) >= next_index) return true;
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }
  return false;
}
}  // namespace

TEST(LifecycleIngress, PinsSingleEndpointAndPublishesAdmittedMessage) {
  const auto root = make_directory();
  const auto live = root / "lifecycle_ingress.live.json";
  LifecycleIngress ingress(live.string(), (root / "refs.json").string(),
      (root / "final.json").string(), "invocation-1", "session-1", std::string(64, 'a'));
  EXPECT_FALSE(ingress.ready());
  EXPECT_TRUE(ingress.pin_endpoint({endpoint()}));
  EXPECT_TRUE(ingress.ready());
  EXPECT_TRUE(ingress.admit({{"sequence", uint64_t{7}}, {"motion_permitted", true}},
      endpoint().gid, 1234, 5678));
  ASSERT_TRUE(wait_for_record(ingress, 1));
  const auto document = ingress.live_document();
  ASSERT_EQ(document.at("records").size(), 1u);
  EXPECT_EQ(document.at("records").at(0).at("record_index"), 1u);
  EXPECT_EQ(document.at("records").at(0).at("sequence"), 7u);
  EXPECT_EQ(document.at("records").at(0).at("receive_time").at("clock"), "CLOCK_MONOTONIC");
  const auto final = ingress.finalize();
  EXPECT_EQ(final.at("state"), "FINALIZED");
  EXPECT_TRUE(std::filesystem::is_regular_file(root / "final.json"));
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, ExtraPublisherAndChangedMessageGidFailClosed) {
  const auto root = make_directory();
  LifecycleIngress extra((root / "live.json").string(), (root / "refs.json").string(),
      (root / "final.json").string(), "invocation-2", "session-2", std::string(64, 'b'));
  EXPECT_FALSE(extra.pin_endpoint({endpoint(), endpoint(std::string(2 * RMW_GID_STORAGE_SIZE, 'b'))}));
  EXPECT_TRUE(extra.failed());
  EXPECT_EQ(extra.failure_literal(), "LIFECYCLE_EXTRA_OR_AMBIGUOUS_PUBLISHER");
  extra.finalize();

  LifecycleIngress changed((root / "live2.json").string(), (root / "refs2.json").string(),
      (root / "final2.json").string(), "invocation-3", "session-3", std::string(64, 'c'));
  ASSERT_TRUE(changed.pin_endpoint({endpoint()}));
  EXPECT_FALSE(changed.admit({{"sequence", uint64_t{1}}}, std::string(2 * RMW_GID_STORAGE_SIZE, 'c'), 1, 2));
  EXPECT_EQ(changed.failure_literal(), "LIFECYCLE_MESSAGE_GID_MISMATCH");
  changed.finalize();
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, EndpointQosCannotChangeAfterPinAndTypedRequestFailsClosed) {
  const auto root = make_directory();
  const auto live = root / "live.json";
  const auto refs = root / "refs.json";
  LifecycleIngress ingress(live.string(), refs.string(), (root / "final.json").string(),
      "invocation-endpoint", "session-endpoint", std::string(64, '9'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  auto changed = endpoint();
  changed.depth = 9;
  EXPECT_FALSE(ingress.pin_endpoint({changed}));
  EXPECT_EQ(ingress.failure_literal(), "LIFECYCLE_PUBLISHER_SET_OR_GID_CHANGED");
  EXPECT_EQ(ingress.finalize().at("state"), "FAILED");

  LifecycleIngress malformed((root / "live2.json").string(), (root / "refs2.json").string(),
      (root / "final2.json").string(), "invocation-type", "session-type", std::string(64, '8'));
  ASSERT_TRUE(malformed.pin_endpoint({endpoint()}));
  auto bad = LifecycleIngress::Json{{"schema", "mecanum.step07-run005.lifecycle-ingress/v1"},
      {"schema_version", "1.0"}, {"protocol_revision", "2.0"},
      {"invocation_id", "invocation-type"}, {"collector_session_id", "session-type"},
      {"config_hash", std::string(64, '8')}, {"request_revision", "1"},
      {"operation", "RESERVE"}, {"record_index", uint64_t{1}},
      {"record_sha256", std::string(64, 'a')}, {"references", LifecycleIngress::Json::array()}};
  write_request(root / "refs2.json", bad);
  for (int i = 0; i < 100 && !malformed.failed(); ++i)
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  EXPECT_TRUE(malformed.failed());
  EXPECT_EQ(malformed.finalize().at("state"), "FAILED");
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, HeartbeatSequenceMayRepeatButRegressionFails) {
  const auto root = make_directory();
  const auto live = root / "live.json";
  LifecycleIngress ingress(live.string(), (root / "refs.json").string(),
      (root / "final.json").string(), "invocation-4", "session-4", std::string(64, 'd'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  ASSERT_TRUE(ingress.admit({{"sequence", uint64_t{8}}}, endpoint().gid, 1, 2));
  ASSERT_TRUE(ingress.admit({{"sequence", uint64_t{8}}}, endpoint().gid, 2, 3));
  ASSERT_TRUE(ingress.admit({{"sequence", uint64_t{7}}}, endpoint().gid, 3, 4) == false);
  EXPECT_EQ(ingress.failure_literal(), "LIFECYCLE_BARRIER_SEQUENCE_REGRESSION");
  const auto final = ingress.finalize();
  EXPECT_EQ(final.at("state"), "FAILED");
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, ReservePromoteRetainsExactRecordThroughFinalize) {
  const auto root = make_directory();
  const auto live = root / "live.json";
  const auto refs = root / "refs.json";
  LifecycleIngress ingress(live.string(), refs.string(), (root / "final.json").string(),
      "invocation-protocol", "session-protocol", std::string(64, 'e'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  ASSERT_TRUE(ingress.admit({{"sequence", uint64_t{7}}, {"primary_state", 2},
      {"barrier_state", 1}, {"motion_permitted", true}}, endpoint().gid, 1234, 5678));
  ASSERT_TRUE(wait_for_record(ingress, 1));
  const auto row = ingress.live_document().at("records").at(0);
  const auto digest = sha256(row.dump());
  LifecycleIngress::Json request{{"schema", "mecanum.step07-run005.lifecycle-ingress/v1"},
      {"schema_version", "1.0"}, {"protocol_revision", "2.0"},
      {"invocation_id", "invocation-protocol"}, {"collector_session_id", "session-protocol"},
      {"config_hash", std::string(64, 'e')}, {"request_revision", uint64_t{1}},
      {"operation", "RESERVE"}, {"record_index", uint64_t{1}},
      {"record_sha256", digest}, {"references", LifecycleIngress::Json::array()}};
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 1));
  request["request_revision"] = uint64_t{2};
  request["operation"] = "RELEASE";
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 2));
  EXPECT_EQ(ingress.live_document().at("committed_reference_count"), 0u);
  request["request_revision"] = uint64_t{3};
  request["operation"] = "RESERVE";
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 3));
  request["request_revision"] = uint64_t{4};
  request["operation"] = "RELEASE";
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 4));
  request["request_revision"] = uint64_t{5};
  request["operation"] = "RESERVE";
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 5));
  request["request_revision"] = uint64_t{6};
  request["operation"] = "RELEASE";
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 6));
  EXPECT_EQ(ingress.live_document().at("committed_reference_count"), 0u);
  request["request_revision"] = uint64_t{7};
  request["operation"] = "RESERVE";
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 7));
  request["request_revision"] = uint64_t{8};
  request["operation"] = "PROMOTE";
  request["references"] = LifecycleIngress::Json::array({
      {{"record_index", uint64_t{1}}, {"record_sha256", digest}}});
  write_request(refs, request);
  ASSERT_TRUE(wait_for_ack(ingress, 8));
  auto sample_refs = request["references"];
  for (uint64_t revision = 9; revision <= 12; ++revision) {
    sample_refs.push_back({{"record_index", uint64_t{1}}, {"record_sha256", digest}});
    request["request_revision"] = revision;
    request["references"] = sample_refs;
    write_request(refs, request);
    ASSERT_TRUE(wait_for_ack(ingress, revision));
  }
  const auto final = ingress.finalize();
  EXPECT_EQ(final.at("protocol_revision"), "2.0");
  EXPECT_EQ(final.at("state"), "FINALIZED");
  ASSERT_EQ(final.at("retained_references").size(), 1u);
  ASSERT_EQ(final.at("committed_references").size(), 1u);
  EXPECT_EQ(final.at("retained_references").at(0).at("record_sha256"), digest);
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, NestedDuplicateReferenceJsonFailsClosed) {
  const auto root = make_directory();
  const auto live = root / "live.json";
  const auto refs = root / "refs.json";
  LifecycleIngress ingress(live.string(), refs.string(), (root / "final.json").string(),
      "invocation-json", "session-json", std::string(64, '1'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  { std::ofstream stream(refs); stream << "{\"outer\":{\"duplicate\":1,\"duplicate\":2}}"; }
  for (int i = 0; i < 100 && !ingress.failed(); ++i)
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  EXPECT_TRUE(ingress.failed());
  EXPECT_EQ(ingress.failure_literal(), "LIFECYCLE_REFERENCE_JSON_INVALID");
  EXPECT_EQ(ingress.finalize().at("state"), "FAILED");
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, BomNonFiniteOversizeAndSymlinkRequestsFailClosed) {
  struct InvalidInput {
    const char *name;
    std::string payload;
    const char *expected;
    bool as_symlink{false};
  };
  const std::vector<InvalidInput> cases{
      {"bom", std::string("\xef\xbb\xbf{}"), "LIFECYCLE_REFERENCE_BOM_FORBIDDEN"},
      {"nonfinite", "{\"value\":NaN}", "LIFECYCLE_REFERENCE_JSON_INVALID"},
      {"oversize", std::string(8193, ' '), "LIFECYCLE_REFERENCE_READ_OR_SIZE_INVALID"},
      {"symlink", "{}", "LIFECYCLE_REFERENCE_READ_OR_SIZE_INVALID", true},
  };
  for (const auto &test_case : cases) {
    SCOPED_TRACE(test_case.name);
    const auto root = make_directory();
    const auto live = root / "live.json";
    const auto refs = root / "refs.json";
    const auto target = root / "target.json";
    { std::ofstream stream(target, std::ios::binary); stream << test_case.payload; }
    if (test_case.as_symlink) std::filesystem::create_symlink(target, refs);
    else std::filesystem::copy_file(target, refs);
    LifecycleIngress ingress(live.string(), refs.string(), (root / "final.json").string(),
        std::string("invocation-") + test_case.name,
        std::string("session-") + test_case.name, std::string(64, '4'));
    ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
    for (int i = 0; i < 100 && !ingress.failed(); ++i)
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    EXPECT_TRUE(ingress.failed());
    EXPECT_EQ(ingress.failure_literal(), test_case.expected);
    EXPECT_EQ(ingress.finalize().at("state"), "FAILED");
    std::filesystem::remove_all(root);
  }
}

TEST(LifecycleIngress, LiveWriterIoFailureIsLatchedForFinalization) {
  const auto root = make_directory();
  const auto blocked = root / "missing-parent" / "artifact.json";
  LifecycleIngress ingress(blocked.string(), (root / "missing-parent" / "refs.json").string(),
      (root / "missing-parent" / "final.json").string(), "invocation-io", "session-io",
      std::string(64, '2'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  for (int i = 0; i < 100 && !ingress.failed(); ++i)
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  EXPECT_TRUE(ingress.failed());
  EXPECT_EQ(ingress.finalize().at("state"), "FAILED");
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, CommittedCopySurvivesMoreThanHistoryCapacity) {
  const auto root = make_directory();
  const auto live = root / "live.json";
  const auto refs = root / "refs.json";
  LifecycleIngress ingress(live.string(), refs.string(), (root / "final.json").string(),
      "invocation-rollover", "session-rollover", std::string(64, '3'));
  ASSERT_TRUE(ingress.pin_endpoint({endpoint()}));
  ASSERT_TRUE(ingress.admit({{"sequence", uint64_t{1}}}, endpoint().gid, 1, 11));
  ASSERT_TRUE(wait_for_record(ingress, 1));
  const auto row = ingress.live_document().at("records").at(0);
  const auto digest = sha256(row.dump());
  LifecycleIngress::Json request{{"schema", "mecanum.step07-run005.lifecycle-ingress/v1"},
      {"schema_version", "1.0"}, {"protocol_revision", "2.0"},
      {"invocation_id", "invocation-rollover"}, {"collector_session_id", "session-rollover"},
      {"config_hash", std::string(64, '3')}, {"request_revision", uint64_t{1}},
      {"operation", "RESERVE"}, {"record_index", uint64_t{1}},
      {"record_sha256", digest}, {"references", LifecycleIngress::Json::array()}};
  write_request(refs, request); ASSERT_TRUE(wait_for_ack(ingress, 1));
  request["request_revision"] = uint64_t{2}; request["operation"] = "PROMOTE";
  request["references"] = LifecycleIngress::Json::array({
      {{"record_index", uint64_t{1}}, {"record_sha256", digest}}});
  write_request(refs, request); ASSERT_TRUE(wait_for_ack(ingress, 2));
  for (uint64_t i = 2; i <= 70; ++i) {
    ASSERT_TRUE(ingress.admit({{"sequence", i}}, endpoint().gid,
        static_cast<int64_t>(i), static_cast<int64_t>(i + 10)));
    ASSERT_TRUE(wait_for_next_record(ingress, i + 1));
  }
  const auto live_doc = ingress.live_document();
  EXPECT_FALSE(ingress.failed());
  EXPECT_EQ(live_doc.at("records").size(), LifecycleIngress::kHistoryCapacity);
  const auto final = ingress.finalize();
  EXPECT_EQ(final.at("state"), "FINALIZED");
  ASSERT_EQ(final.at("retained_references").size(), 1u);
  EXPECT_EQ(final.at("retained_references").at(0).at("record_index"), 1u);
  std::filesystem::remove_all(root);
}

TEST(LifecycleIngress, PythonReaderUsesNativeReserveAckPromotionAndFinalRetention) {
  const auto root = make_directory();
  const auto live = root / "lifecycle_ingress.live.json";
  const auto refs = root / "lifecycle_ingress.references.json";
  const auto final = root / "lifecycle_ingress.final.json";
  const std::string invocation = "INVOCATION_TEMPORAL_PROTOCOL2_FIXTURE";
  const std::string session = "collector-temporal-fixture";
  std::ifstream runner_file(STEP07_RUN005_RUNNER);
  ASSERT_TRUE(runner_file.good());
  const std::string config_prefix = "RUN005_CONFIG_HASH = \"";
  std::string config, runner_line;
  while (std::getline(runner_file, runner_line)) {
    const auto at = runner_line.find(config_prefix);
    if (at != std::string::npos) {
      const auto start = at + config_prefix.size();
      const auto end = runner_line.find('"', start);
      ASSERT_NE(end, std::string::npos);
      config = runner_line.substr(start, end - start);
      break;
    }
  }
  ASSERT_EQ(config.size(), 64u);
  const std::string gid(2 * RMW_GID_STORAGE_SIZE, '1');
  LifecycleIngress ingress(live.string(), refs.string(), final.string(), invocation, session, config);
  ASSERT_TRUE(ingress.pin_endpoint({endpoint(gid)}));
  ASSERT_TRUE(ingress.admit({{"stamp_sec", 0}, {"stamp_nanosec", 980000000}, {"frame_id", ""},
      {"episode_generation", 1}, {"reset_epoch", 2}, {"runtime_generation", 3},
      {"sequence", uint64_t{7}}, {"primary_state", 2}, {"barrier_state", 1},
      {"motion_permitted", true}, {"reason", "ACTIVE"},
      {"barrier_stamp_sec", 0}, {"barrier_stamp_nanosec", 980000000}}, gid, 980000000, 200));
  ASSERT_TRUE(wait_for_record(ingress, 1));

  int to_child[2]{};
  int from_child[2]{};
  ASSERT_EQ(::pipe(to_child), 0);
  ASSERT_EQ(::pipe(from_child), 0);
  const pid_t child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    ::dup2(to_child[0], STDIN_FILENO);
    ::dup2(from_child[1], STDOUT_FILENO);
    ::close(to_child[0]); ::close(to_child[1]);
    ::close(from_child[0]); ::close(from_child[1]);
    ::setenv("PYTHONPATH", STEP07_RL_PYTHON_SOURCE, 1);
    const char *script = R"PY(
import hashlib, importlib.util, json, shutil, sys, time
from pathlib import Path
from mecanum_nav_rl.observations.step07_lifecycle_ingress import LifecycleIngressClient, SCHEMA
root, repo, invocation, session, config = sys.argv[1:]
repo=Path(repo)
tools=repo/'artifacts/simulation/step07_nav2_baseline_campaign/tools'
sys.path.insert(0,str(tools))
import run_step07_nav2_baseline_run005 as runner
assert runner.RUN005_CONFIG_HASH == config
client = LifecycleIngressClient(live_path=root+'/lifecycle_ingress.live.json',
    references_path=root+'/lifecycle_ingress.references.json',
    final_path=root+'/lifecycle_ingress.final.json', invocation_id=invocation,
    collector_session_id=session, config_hash=config)
live=client.read_live(); row=live['records'][0]
from mecanum_nav_rl.observations.step07_lifecycle_ingress import canonical_json_bytes
digest=hashlib.sha256(canonical_json_bytes(row)).hexdigest()
ref={'record_index':row['record_index'],'record_sha256':digest}
sample_refs=[]
def wait_ack(label):
 deadline=time.monotonic()+3
 while True:
  current=client.read_live()
  if client.acknowledged(current): return current
  if time.monotonic() >= deadline: raise RuntimeError(label+'_ACK_TIMEOUT')
  time.sleep(.01)
for _ in range(5):
 client.request_references([row],sample_references=sample_refs)
 wait_ack('RESERVE')
 sample_refs.append(ref)
 client.promote_reference(row,sample_references=sample_refs)
 wait_ack('PROMOTE')
print('ACKED',flush=True)
if sys.stdin.readline().strip() != 'FINAL': raise RuntimeError('missing final signal')
doc=client.verify_final()
assert doc['committed_references']==[ref]

# Run the actual runner handoff against the native files before using them in
# the sealed current-contract fixture.
from pathlib import Path
identity={'schema':SCHEMA,'protocol_revision':'2.0',
 'collector_session_id':session,'live_artifact':'lifecycle_ingress.live.json',
 'reference_request_artifact':'lifecycle_ingress.references.json',
 'final_artifact':'lifecycle_ingress.final.json','selected_record_references':[]}
record={'invocation_id':invocation,'config_hash':config,'lifecycle_ingress':identity}
collection={'samples':[{} for _ in range(5)],'lifecycle_ingress':{
 'schema':SCHEMA,'collector_session_id':session,
 'selected_record_references':[ref for _ in range(5)]}}
handoff=runner._validate_native_lifecycle_references(collection,{'lifecycle_ingress':doc},record,Path(root))
assert len(handoff['selected_record_references'])==5
assert len({r['record_index'] for r in handoff['selected_record_references']})==1

# Build a fully sealed PASS-shaped contract bundle, replace its synthetic
# native sidecars with the exact native outputs, then run the production runner
# handoff and validator over that same bundle.
spec=importlib.util.spec_from_file_location('validator_tests',tools/'test_step07_gate_b_evidence_validator.py')
validator_tests=importlib.util.module_from_spec(spec); spec.loader.exec_module(validator_tests)
bundle=validator_tests._protocol2_temporal_pass_bundle(Path(root)/'sealed_bundle')
files={name:json.loads((bundle/name).read_text(encoding='utf-8')) for name in
 ('run_record.json','runtime_observer.json','gate_b_vectors.json','gate_b_terminal.json')}
record=files['run_record.json']; observer=files['runtime_observer.json']
gate=files['gate_b_vectors.json']; terminal=files['gate_b_terminal.json']
for name in ('lifecycle_ingress.live.json','lifecycle_ingress.references.json','lifecycle_ingress.final.json'):
 shutil.copyfile(Path(root)/name,bundle/name)
native_live=json.loads((bundle/'lifecycle_ingress.live.json').read_text(encoding='utf-8'))
native_request=json.loads((bundle/'lifecycle_ingress.references.json').read_text(encoding='utf-8'))
native_final=json.loads((bundle/'lifecycle_ingress.final.json').read_text(encoding='utf-8'))
native_row=native_final['retained_references'][0]['record']
identity.update({'selected_record_references':[ref for _ in range(5)]})
record['lifecycle_ingress']=identity
gate['lifecycle_ingress'].update(collector_session_id=session,
 selected_record_references=[ref for _ in range(5)])
for sample in gate['samples']:
 sample['correlation'].update(lifecycle_sequence=native_row['sequence'],
  lifecycle_record_index=ref['record_index'],lifecycle_record_sha256=ref['record_sha256'])
 sample['temporal_proof']['native_lifecycle_reference']=ref
observer['lifecycle_ingress']=native_final
terminal.update(lifecycle_ingress_session_id=session,
 selected_lifecycle_references=[ref for _ in range(5)])

def write_doc(name,value): validator_tests._write_canonical_json(bundle/name,value)
for name,value in files.items(): write_doc(name,value)
# Invoke the production runner handoff on the exact files the validator reads.
handoff=runner._validate_native_lifecycle_references(gate,observer,record,bundle)
assert len(handoff['selected_record_references'])==5
write_doc('run_record.json',record)
chain,chain_bytes=validator_tests.canonical_navigation_evidence_chain(observer,gate)
observer['navigation_evidence_chain']=chain
observer['navigation_evidence_chain_canonical']=chain_bytes.decode('utf-8')
observer['navigation_evidence_chain_sha256']=hashlib.sha256(chain_bytes).hexdigest()
write_doc('runtime_observer.json',observer)
write_doc('gate_b_vectors.json',gate)
validator_tests._write_canonical_json(bundle/'navigation_evidence_chain.json',{
 'schema_version':'1.0','chain':chain,'canonical':chain_bytes.decode('utf-8'),
 'sha256':hashlib.sha256(chain_bytes).hexdigest()})
validator_tests._refresh_protocol2_terminal_binding(bundle)
result=validator_tests.validate_run_directory(bundle)
assert result['verdict']['pass'] is True
print('VERIFIED',flush=True)
)PY";
    ::execlp("python3", "python3", "-c", script, root.c_str(),
        STEP07_REPOSITORY_ROOT, invocation.c_str(), session.c_str(), config.c_str(),
        static_cast<char *>(nullptr));
    _exit(127);
  }
  ::close(to_child[0]); ::close(from_child[1]);
  FILE *reader = ::fdopen(from_child[0], "r");
  ASSERT_NE(reader, nullptr);
  char line[128]{};
  ASSERT_NE(::fgets(line, sizeof(line), reader), nullptr);
  ASSERT_STREQ(line, "ACKED\n");
  const auto native_final = ingress.finalize();
  ASSERT_EQ(native_final.at("state"), "FINALIZED");
  ASSERT_EQ(::write(to_child[1], "FINAL\n", 6), 6);
  ASSERT_NE(::fgets(line, sizeof(line), reader), nullptr);
  EXPECT_STREQ(line, "VERIFIED\n");
  ::close(to_child[1]);
  ::fclose(reader);
  int status = 0;
  ASSERT_EQ(::waitpid(child, &status, 0), child);
  EXPECT_TRUE(WIFEXITED(status));
  EXPECT_EQ(WEXITSTATUS(status), 0);
  std::filesystem::remove_all(root);
}
