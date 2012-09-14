#ifndef HEADER_FREQ_TABLES
#define HEADER_FREQ_TABLES

#include <stdint.h>

#include <utility>
#include <vector>

using std::pair;
using std::vector;

typedef pair<uint16_t, uint32_t> FreqEntry;
typedef vector<FreqEntry> FreqTable;

struct FreqTables {
 public:
  static FreqTable request_freq_table;
  static FreqTable response_freq_table;
};

#endif
