#include <ostream>

#include "utils.h"

using std::ostream;
using std::hex;
using std::dec;

template <>
string FormatAsBits<uint32_t>(const uint32_t& v, int num_bits, int offset) {
  stringstream retval;
  for (int i = 0; i < num_bits; ++i) {
    if ((i + offset) % 8 == 0)
      retval << "|";
    retval << (((v >> (31 - i)) & 0x1U) > 0);
  }
  return retval.str();
}

template <>
string FormatAsBits<uint16_t>(const uint16_t& v, int num_bits, int offset) {
  stringstream retval;
  for (int i = 0; i < num_bits; ++i) {
    if ((i + offset) % 8 == 0)
      retval << "|";
    retval << (((v >> (15 - i)) & 0x1U) > 0);
  }
  return retval.str();
}

template <>
string FormatAsBits<uint8_t>(const uint8_t& v, int num_bits, int offset) {
  stringstream retval;
  for (int i = 0; i < num_bits; ++i) {
    if ((i + offset) % 8 == 0)
      retval << "|";
    retval << (((v >> (7 - i)) & 0x1U) > 0);
  }
  return retval.str();
}

void OutputCharToOstream(ostream& os, unsigned short c) {
  if (c > 256 + 1)
    abort();
  if (c >= 256) {
    os << c;
  } else {
    os << " '";
    if (c < 128 && (isgraph(c) || c == ' ')) {
      os << (char)c;
    } else {
      switch (c) {
        case '\t':
          os << "\\t";
          break;
        case '\n':
          os << "\\n";
          break;
        case '\r':
          os << "\\r";
          break;
        case '\0':
          os << "\\0";
          break;
        default:
          if (c >= 16) {
            os << "\\x" << hex << c << dec;
          } else {
            os << "\\x0" << hex << c << dec;
          }
          break;
      }
    }
    os << "'";
  }
}

string ReadableUShort(uint16_t c) {
  stringstream s;
  OutputCharToOstream(s, c);
  return s.str();
}
