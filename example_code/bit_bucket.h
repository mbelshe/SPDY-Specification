#ifndef BITBUCKET_H
#define BITBUCKET_H

#include <algorithm>
#include <iostream>
#include <sstream>
#include <stdlib.h>
#include <string>
#include <vector>

#include "utils.h"

using std::cerr;
using std::cout;
using std::flush;
using std::max;
using std::min;
using std::min;
using std::ostream;
using std::string;
using std::stringstream;
using std::vector;

class BitBucket {
  vector<unsigned char> bsa;
  int bsa_boff;
  int idx_byte;
  int idx_boff;
  int num_bits;
  BitBucket(const BitBucket&);
 public:
  BitBucket() {
    Clear();
  }
  void Clear() {
    bsa.clear();
    bsa_boff = 0;
    idx_byte = 0;
    idx_boff = 0;
    num_bits = 0;
  }

  void Seek(unsigned int bit_loc) {
    idx_boff = bit_loc % 8;
    idx_byte = bit_loc / 8;
  }

  void SeekDelta(int bit_loc_delta) {
    Seek(BitsConsumed() + bit_loc_delta);
  }

  void ConsumeBits(int bits_consumed) {
    SeekDelta(bits_consumed);
  }

  // This is horribly inefficient.
  void ShiftBitsIntoWord(uint32_t* word, int num_bits) {
    *word <<= num_bits;
    int saved_idx_byte = idx_byte;
    int saved_idx_boff = idx_boff;
    uint32_t tmp_word = 0;
    while (num_bits) {
      tmp_word <<= 1;
      tmp_word |= GetBit();
      --num_bits;
    }
    *word |= tmp_word;
    idx_byte = saved_idx_byte;
    idx_boff = saved_idx_boff;
  }

  void StoreBit(bool bit) {
    ++num_bits;
    uint32_t byte_idx = ((num_bits + 7) / 8);
    if (byte_idx > bsa.size())
      bsa.push_back(0);
    bsa.back() |= bit << (7 - bsa_boff);
    ++bsa_boff;
    bsa_boff %= 8;
  }

  void StoreBits(const vector<char>& inp_bytes, int inp_bits) {
    if (inp_bits == 0) return;
    int old_bsa_boff = bsa_boff;
    num_bits += inp_bits;
    if (bsa_boff == 0) {
      bsa.insert(bsa.end(), inp_bytes.begin(), inp_bytes.end());
      bsa_boff = inp_bits % 8;
      if (bsa_boff) {
        bsa.back() &= ~(0xff >> bsa_boff);  // zero out trailing  right-bits
      }
    } else {
      int leftover_bits = 0;
      if (inp_bits % 8) {
        leftover_bits = inp_bits % 8;
      } else {
        leftover_bits = 8;
      }
      int bits_left_in_byte = 8 - bsa_boff;
      bsa.reserve(bsa.size() + inp_bytes.size());
      for (unsigned int i = 0; i < inp_bytes.size(); ++i) {
        unsigned char c = inp_bytes[i];
        bsa.back() |= c >> bsa_boff;
        bsa.push_back(c << bits_left_in_byte);
      }
      if (bsa_boff + leftover_bits <= 8) {
        bsa.pop_back();
      }
      bsa_boff = (bsa_boff + leftover_bits) % 8;
      if (bsa_boff)
        bsa.back() &= ~(0xff >> bsa_boff);
    }
    if (bsa_boff != (old_bsa_boff + inp_bits) % 8) {
      cerr << "There was some logic error in the code doing StoreBits\n";
      cerr << "bsa_boff(" << bsa_boff << ") should equal: "
           << (old_bsa_boff + inp_bits) % 8 << "\n";
      abort();
    }
  }

  int NumBits() const {
    return num_bits;
  }
  int BitsConsumed() const {
    return idx_byte * 8 + idx_boff;
  }
  bool AllConsumed() const {
    return BitsConsumed() >= NumBits();
  }
  int BitsRemaining() const {
    return NumBits() - BitsConsumed();
  }

  bool GetBit() {
    bool bit = bsa[idx_byte] & (0x80 >> idx_boff);
    ++idx_boff;
    if (idx_boff >= 8) {
      ++idx_byte;
      idx_boff -= 8;
    }
    return bit;
  }

  void GetBits(vector<char>* retval, int num_bits) {
    int output_bytes = (num_bits + 7) / 8;
    retval->reserve(output_bytes);
    int old_idx_boff = idx_boff;
    if (num_bits > NumBits()) {
      cerr << "Oops, we're asking to get more bits than are available.\n";
      cerr << "Bits available: " << BitsRemaining() << "\n";
      cerr << "Bits requested: " << num_bits << "\n";
      abort();
    }
    int bits_left = num_bits;
    if (idx_boff == 0) {
      retval->insert(retval->end(), bsa.begin() + idx_byte, bsa.begin() + idx_byte + output_bytes);
      idx_byte += num_bits / 8;
      idx_boff = num_bits % 8;
      if (idx_boff) {
        retval->back() &= ~(0xff >> idx_boff);
      }
    } else { // idx_boff != 0. There WILL be shifting about.
      int idx_leftover = 8 - idx_boff;
      while (bits_left >= 8) {
        unsigned int c = bsa[idx_byte] << idx_boff;
        ++idx_byte;
        c |= bsa[idx_byte] >> idx_leftover;
        // cout << "ONE_BYTE DOWN, BITS_LEFT:" << bits_left
        //      << " " << FormatAsBits(&c, 8) << "\n";
        retval->push_back((char)c);
        bits_left -= 8;
      }
      if (bits_left) {
        //cout << "BITS LEFT: " << bits_left << "\n";
        int cur_boff = 0;
        unsigned int cur_byte = 0;
        while (true) {
          int bits_to_consume = min(min(8 - cur_boff, idx_leftover), bits_left);
          unsigned int mask = ~(0xff >> bits_to_consume);
          cur_byte |= ((bsa[idx_byte] << idx_boff) & mask) >> cur_boff;
          bits_left -= bits_to_consume;
          idx_boff += bits_to_consume;
          if (idx_boff >= 8) {
            ++idx_byte;
            idx_boff -= 8;
          }
          cur_boff += bits_to_consume;
          if (cur_boff >= 8) {
            // something is wrong.
            cerr << "Logic error. cur_boff >= 8\n";
            cerr << "cur_boff: " << cur_boff << "\n";
            cerr << "bits_left: " << bits_left << "\n";
            abort();
          }
          if (bits_left == 0) {
            // cout << "BITS LEFT: " << bits_left
            //      << " " << FormatAsBits(&cur_byte, 8) << "\n";
            retval->push_back((char)cur_byte);
            break;
          }
        }
      }
    }
    if (idx_boff != (old_idx_boff + num_bits) % 8) {
      cerr<< "idx_boff != (old_idx_boff + num_bits) % 8\n";
      cerr << "old_idx_boff: " << old_idx_boff << "\n";
      cerr << "    idx_boff: " << idx_boff << "\n";
      cerr << "    num_bits: " << num_bits << "\n";
      abort();
    }
  }

  string AsString() const {
    stringstream ss;
    ss << *this;
    return ss.str();
  }
  string DebugStr(int offset=0, int range=1) const {
    stringstream ss;
    int num_bits_consumed = idx_byte * 8 + idx_boff;
    num_bits_consumed += offset;
    for (int i = 0; i < num_bits_consumed; ++i) {
      if (!(i%8)) ss << "|";
      ss << "-";
    }
    for (int i = num_bits_consumed ; i < num_bits_consumed + range; ++i) {
      if (!(i%8)) ss << "|";
      ss << "^";
    }
    return ss.str();
  }

  friend ostream& operator<<(ostream& os, const BitBucket& bb) {
    os << FormatAsBits(bb.bsa, bb.NumBits())
       << " [" << bb.NumBits() << "," << bb.bsa_boff << "]";
    return os;
  }
};

#endif  // BITBUCKET_H
