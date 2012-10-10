#ifndef HEADER_FREQ_TABLES
#define HEADER_FREQ_TABLES

#include <stdint.h>

#include <utility>
#include <array>

typedef std::pair<uint16_t, uint32_t> FreqEntry;
typedef std::array<FreqEntry, 257> FreqTable;

struct FreqTables {
 public:
  static FreqTable request_freq_table;
  static FreqTable response_freq_table;
};

#endif
