#pragma once

// HBTRACE1 v1 writer; consumers read only after the writer process has joined.
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace mecanum_sim_backend::heartbeat_trace {
constexpr std::size_t header_size = 320;
constexpr std::size_t record_size = 96;
constexpr std::uint32_t record_complete = 0x434f4d54;
constexpr std::uint32_t header_complete = 0x48445231;
static_assert(__atomic_always_lock_free(sizeof(std::uint32_t), nullptr),
              "lock-free aligned 32-bit marker required");

inline void put32(unsigned char *p, std::uint32_t v) {
  for (unsigned i = 0; i < 4; ++i) p[i] = static_cast<unsigned char>(v >> (8 * i));
}
inline void put64(unsigned char *p, std::uint64_t v) {
  for (unsigned i = 0; i < 8; ++i) p[i] = static_cast<unsigned char>(v >> (8 * i));
}
inline std::uint32_t crc32(const unsigned char *p, std::size_t n) {
  std::uint32_t c = 0xffffffffu;
  for (std::size_t i = 0; i < n; ++i) {
    c ^= p[i];
    for (unsigned j = 0; j < 8; ++j)
      c = (c >> 1) ^ (0xedb88320u & (0u - (c & 1u)));
  }
  return c ^ 0xffffffffu;
}
inline void field(unsigned char *p, std::size_t n, const std::string &value) {
  if (value.empty() || value.size() > n || value.find('\0') != std::string::npos)
    throw std::invalid_argument("invalid header field");
  for (unsigned char c : value)
    if (c > 0x7f) throw std::invalid_argument("header field must be ASCII");
  std::memcpy(p, value.data(), value.size());
}

class Writer {
 public:
  Writer(int fd, std::uint32_t capacity, const std::string &collection,
         const std::string &session, std::uint64_t backend,
         const std::string &config, const std::string &world,
         const std::string &clock, const std::string &role,
         const std::string &provenance, std::uint64_t expected_device,
         std::uint64_t expected_inode)
      : size_(header_size + static_cast<std::size_t>(capacity) * record_size),
        capacity_(capacity) {
    if (!capacity || capacity > 524288 || !backend)
      throw std::invalid_argument("invalid capacity or backend identity");
    const std::uint32_t endian = 1;
    if (*reinterpret_cast<const unsigned char *>(&endian) != 1)
      throw std::runtime_error("little-endian host required for v1 markers");
    struct stat info {};
    if (fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_size < 0 ||
        static_cast<std::uint64_t>(info.st_size) != size_ ||
        info.st_uid != geteuid() || (info.st_mode & 0777) != 0600 ||
        info.st_nlink != 1 || static_cast<std::uint64_t>(info.st_dev) != expected_device ||
        static_cast<std::uint64_t>(info.st_ino) != expected_inode)
      throw std::runtime_error("trace file identity, mode, or size mismatch");
    void *map = mmap(nullptr, size_, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) throw std::runtime_error("mmap failed");
    data_ = static_cast<unsigned char *>(map);
    try {
      for (std::size_t i = 0; i < size_; ++i)
        if (data_[i] != 0) throw std::runtime_error("trace file is not fresh");
      std::memcpy(data_, "HBTRACE1", 8);
      put32(data_ + 8, 1); put32(data_ + 12, header_size);
      put32(data_ + 16, record_size); put32(data_ + 20, capacity);
      field(data_ + 24, 36, collection); field(data_ + 60, 36, session);
      put64(data_ + 96, backend); field(data_ + 104, 64, config);
      field(data_ + 168, 32, world); field(data_ + 200, 32, clock);
      field(data_ + 232, 8, role); field(data_ + 240, 64, provenance);
      put32(data_ + 308, crc32(data_, 304));
      __atomic_store_n(reinterpret_cast<std::uint32_t *>(data_ + 312),
                       header_complete, __ATOMIC_RELEASE);
    } catch (...) {
      munmap(data_, size_); data_ = nullptr; throw;
    }
  }
  ~Writer() { if (data_) munmap(data_, size_); }
  Writer(const Writer &) = delete;
  Writer &operator=(const Writer &) = delete;

  bool append(std::uint32_t kind, std::uint64_t timestamp,
              std::uint64_t status_sequence, const unsigned char *payload,
              std::size_t payload_size, bool commit = true) {
    if (payload_size > 56 || !kind || (!payload && payload_size))
      throw std::invalid_argument("invalid trace record");
    if (next_ >= capacity_) {
      __atomic_store_n(reinterpret_cast<std::uint32_t *>(data_ + 304),
                       1u, __ATOMIC_RELEASE);
      return false;
    }
    auto *p = data_ + header_size + static_cast<std::size_t>(next_) * record_size;
    put64(p, static_cast<std::uint64_t>(next_) + 1); put32(p + 8, kind);
    put32(p + 12, static_cast<std::uint32_t>(payload_size));
    put64(p + 16, timestamp); put64(p + 24, status_sequence);
    if (payload_size) std::memcpy(p + 32, payload, payload_size);
    put32(p + 88, crc32(p, 88));
    if (commit)
      __atomic_store_n(reinterpret_cast<std::uint32_t *>(p + 92),
                       record_complete, __ATOMIC_RELEASE);
    ++next_;
    return true;
  }
  bool append(std::uint32_t kind, std::uint64_t timestamp,
              std::uint64_t status_sequence, const std::string &payload,
              bool commit = true) {
    return append(kind, timestamp, status_sequence,
                  reinterpret_cast<const unsigned char *>(payload.data()),
                  payload.size(), commit);
  }

 private:
  unsigned char *data_ = nullptr;
  std::size_t size_;
  std::uint32_t capacity_;
  std::uint32_t next_ = 0;
};
}  // namespace mecanum_sim_backend::heartbeat_trace
