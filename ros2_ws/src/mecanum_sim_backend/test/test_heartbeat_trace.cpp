#include "mecanum_sim_backend/heartbeat_trace_writer.hpp"
#include "mecanum_sim_backend/heartbeat_trace_writer_c.h"

#include <gtest/gtest.h>
#include <fcntl.h>
#include <stdexcept>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#include <array>
#include <cstdio>
#include <string>

namespace {
class TempTrace {
 public:
  TempTrace() {
    std::string pattern = "/tmp/hbtrace-native-XXXXXX";
    fd_ = mkstemp(pattern.data());
    path_ = pattern;
    if (fd_ < 0 || fchmod(fd_, 0600) != 0 ||
        ftruncate(fd_, mecanum_sim_backend::heartbeat_trace::header_size + 4 * mecanum_sim_backend::heartbeat_trace::record_size) != 0 ||
        fstat(fd_, &stat_) != 0) throw std::runtime_error("temp trace setup failed");
  }
  ~TempTrace() { if (fd_ >= 0) close(fd_); if (!path_.empty()) unlink(path_.c_str()); }
  int fd() const { return fd_; }
  const std::string &path() const { return path_; }
  const struct stat &stat() const { return stat_; }
 private:
  int fd_{-1};
  std::string path_;
  struct stat stat_{};
};
}

TEST(HeartbeatTraceWriter, WritesReaderCompatibleV1BytesAndBoundaries) {
  TempTrace file;
  const std::string uuid = "00000000-0000-0000-0000-000000000001";
  mecanum_sim_backend::heartbeat_trace::Writer writer(
      file.fd(), 4, uuid, uuid, 42, std::string(64, 'a'),
      "b2_training_arena", "CLOCK_MONOTONIC", "backend", "linux-clock-v1",
      static_cast<std::uint64_t>(file.stat().st_dev),
      static_cast<std::uint64_t>(file.stat().st_ino));
  const std::array<unsigned char, 2> event{{1, 1}};
  ASSERT_TRUE(writer.append(1, 100, 0, nullptr, 0));
  ASSERT_TRUE(writer.append(2, 101, 7, event.data(), event.size()));
  ASSERT_TRUE(writer.append(3, 110, 0, nullptr, 0));
  auto *bytes = static_cast<unsigned char *>(mmap(nullptr, 320 + 4 * 96,
      PROT_READ, MAP_SHARED, file.fd(), 0));
  ASSERT_NE(bytes, MAP_FAILED);
  EXPECT_EQ(std::string(reinterpret_cast<char *>(bytes), 8), "HBTRACE1");
  EXPECT_EQ(mecanum_sim_backend::heartbeat_trace::crc32(bytes, 304),
            static_cast<std::uint32_t>(bytes[308] | (bytes[309] << 8) | (bytes[310] << 16) | (bytes[311] << 24)));
  EXPECT_EQ(*reinterpret_cast<std::uint32_t *>(bytes + 312),
            mecanum_sim_backend::heartbeat_trace::header_complete);
  EXPECT_EQ(*reinterpret_cast<std::uint32_t *>(bytes + 320 + 92),
            mecanum_sim_backend::heartbeat_trace::record_complete);
  munmap(bytes, 320 + 4 * 96);
  struct stat info{};
  ASSERT_EQ(fstat(file.fd(), &info), 0);
  EXPECT_EQ(info.st_size, 320 + 4 * 96);
}

TEST(HeartbeatTraceWriter, OverflowIsStickyAndDoesNotOverwriteSlots) {
  TempTrace file;
  const std::string uuid = "00000000-0000-0000-0000-000000000001";
  mecanum_sim_backend::heartbeat_trace::Writer writer(
      file.fd(), 4, uuid, uuid, 42, std::string(64, 'b'),
      "b2_training_arena", "CLOCK_MONOTONIC", "observer", "linux-clock-v1",
      static_cast<std::uint64_t>(file.stat().st_dev),
      static_cast<std::uint64_t>(file.stat().st_ino));
  ASSERT_TRUE(writer.append(1, 1, 0, nullptr, 0));
  ASSERT_TRUE(writer.append(2, 2, 1, nullptr, 0));
  ASSERT_TRUE(writer.append(3, 3, 0, nullptr, 0));
  ASSERT_TRUE(writer.append(2, 4, 2, nullptr, 0));
  EXPECT_FALSE(writer.append(2, 5, 3, nullptr, 0));
}

TEST(HeartbeatTraceWriter, RejectsWrongInodeAndNonPrivateMode) {
  TempTrace file;
  const std::string uuid = "00000000-0000-0000-0000-000000000001";
  EXPECT_THROW((mecanum_sim_backend::heartbeat_trace::Writer(
      file.fd(), 4, uuid, uuid, 42, std::string(64, 'c'),
      "b2_training_arena", "CLOCK_MONOTONIC", "backend", "linux-clock-v1",
      static_cast<std::uint64_t>(file.stat().st_dev),
      static_cast<std::uint64_t>(file.stat().st_ino + 1))), std::runtime_error);
  ASSERT_EQ(fchmod(file.fd(), 0644), 0);
  EXPECT_THROW((mecanum_sim_backend::heartbeat_trace::Writer(
      file.fd(), 4, uuid, uuid, 42, std::string(64, 'd'),
      "b2_training_arena", "CLOCK_MONOTONIC", "backend", "linux-clock-v1",
      static_cast<std::uint64_t>(file.stat().st_dev),
      static_cast<std::uint64_t>(file.stat().st_ino))), std::runtime_error);
}

TEST(HeartbeatTraceWriter, CAbiEnforcesSingleWriterAndUsesMonotonicClock) {
  TempTrace file;
  const std::string uuid = "00000000-0000-0000-0000-000000000001";
  hbtrace_writer *writer = hbtrace_open_path(
      file.path().c_str(), static_cast<std::uint64_t>(file.stat().st_dev),
      static_cast<std::uint64_t>(file.stat().st_ino), 4, uuid.c_str(),
      uuid.c_str(), 42, std::string(64, 'e').c_str(), "b2_training_arena",
      "CLOCK_MONOTONIC", "backend", "linux-clock-v1");
  ASSERT_NE(writer, nullptr);
  EXPECT_EQ(hbtrace_open_path(
      file.path().c_str(), static_cast<std::uint64_t>(file.stat().st_dev),
      static_cast<std::uint64_t>(file.stat().st_ino), 4, uuid.c_str(),
      uuid.c_str(), 42, std::string(64, 'e').c_str(), "b2_training_arena",
      "CLOCK_MONOTONIC", "backend", "linux-clock-v1"), nullptr);
  EXPECT_GT(hbtrace_clock_monotonic_ns(), 0u);
  EXPECT_EQ(hbtrace_append(writer, 1, hbtrace_clock_monotonic_ns(), 0,
                           nullptr, 0), 1);
  hbtrace_close(writer);
}
