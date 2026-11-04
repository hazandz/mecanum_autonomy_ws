#include "mecanum_sim_backend/heartbeat_trace_writer_c.h"
#include "mecanum_sim_backend/heartbeat_trace_writer.hpp"

#include <cerrno>
#include <fcntl.h>
#include <memory>
#include <string>
#include <sys/file.h>
#include <time.h>
#include <unistd.h>

struct hbtrace_writer {
  int fd{-1};
  std::unique_ptr<mecanum_sim_backend::heartbeat_trace::Writer> writer;
};

extern "C" hbtrace_writer *hbtrace_open_path(
    const char *path, uint64_t device, uint64_t inode, uint32_t capacity,
    const char *collection, const char *session, uint64_t backend,
    const char *config, const char *world, const char *clock,
    const char *role, const char *provenance) {
  if (!path || !collection || !session || !config || !world || !clock || !role || !provenance) return nullptr;
  const int fd = open(path, O_RDWR | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0 || flock(fd, LOCK_EX | LOCK_NB) != 0) {
    if (fd >= 0) close(fd);
    return nullptr;
  }
  try {
    auto handle = std::make_unique<hbtrace_writer>();
    handle->fd = fd;
    handle->writer = std::make_unique<mecanum_sim_backend::heartbeat_trace::Writer>(
        fd, capacity, collection, session, backend, config, world, clock, role,
        provenance, device, inode);
    return handle.release();
  } catch (...) {
    close(fd);
    return nullptr;
  }
}

extern "C" int hbtrace_append(hbtrace_writer *writer, uint32_t kind,
                               uint64_t timestamp_ns, uint64_t status_sequence,
                               const unsigned char *payload, size_t payload_size) {
  if (!writer || !writer->writer) return 0;
  try {
    return writer->writer->append(kind, timestamp_ns, status_sequence,
                                  payload, payload_size) ? 1 : 0;
  } catch (...) {
    return 0;
  }
}

extern "C" void hbtrace_close(hbtrace_writer *writer) {
  if (!writer) return;
  writer->writer.reset();
  if (writer->fd >= 0) close(writer->fd);
  delete writer;
}

extern "C" uint64_t hbtrace_clock_monotonic_ns(void) {
  timespec value{};
  if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) return 0;
  return static_cast<uint64_t>(value.tv_sec) * 1000000000ULL + static_cast<uint64_t>(value.tv_nsec);
}
