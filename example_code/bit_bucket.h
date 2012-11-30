// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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
  vector<uint8_t> bsa;  // Byte Storage Array
  size_t bsa_boff;            // Byte Storage Array Bit OFFset
  size_t idx_byte;            // indexed byte
  size_t idx_boff;            // index bit offset
  size_t num_bits;
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

  uint8_t& GetByteAlignedUint8(size_t pos) {
    return *static_cast<uint8_t*>(&bsa[pos]);
  }

  uint16_t& GetByteAlignedUint16(size_t pos) {
    return *reinterpret_cast<uint16_t*>(&bsa[pos]);
  }

  uint32_t& GetByteAlignedUint32(size_t pos) {
    return *reinterpret_cast<uint32_t*>(&bsa[pos]);
  }

  template <typename T>
  void StoreByteAligned(T begin, T end) {
    bsa.insert(bsa.end(), begin, end);
    bsa_boff = 0;
    num_bits = bsa.size() * 8;
  }

  void StoreByteAligned(const vector<char>& inp_bytes) {
    StoreByteAligned(inp_bytes.begin(), inp_bytes.end());
  }

  void StoreByteAlignedUint8(uint8_t byte) {
    bsa.push_back(byte);
    bsa_boff = 0;
    num_bits = bsa.size() * 8;
  }

  void StoreByteAlignedUint16(uint16_t val) {
    char* val_base = reinterpret_cast<char*>(&val);
    StoreByteAligned(val_base, val_base + 2);
    bsa_boff = 0;
    num_bits = bsa.size() * 8;
  }

  void StoreByteAlignedUint32(uint32_t val) {
    char* val_base = reinterpret_cast<char*>(&val);
    StoreByteAligned(val_base, val_base + 4);
    bsa_boff = 0;
    num_bits = bsa.size() * 8;
  }

  typedef vector<uint8_t>::iterator byte_iterator;

  byte_iterator BytesBegin() { return bsa.begin(); }
  byte_iterator BytesEnd()   { return bsa.end(); }

  void Seek(size_t bit_loc) {
    idx_boff = bit_loc % 8;
    idx_byte = bit_loc / 8;
  }

  void SeekDelta(size_t bit_loc_delta) {
    Seek(BitsConsumed() + bit_loc_delta);
  }

  void ConsumeBits(size_t bits_consumed) {
    SeekDelta(bits_consumed);
  }

  // This is horribly inefficient.
  void ShiftBitsIntoWord(uint32_t* word, size_t num_bits) {
    *word <<= num_bits;
    size_t saved_idx_byte = idx_byte;
    size_t saved_idx_boff = idx_boff;
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

  void StoreBits8(uint8_t val) {
    if (bsa_boff == 0) {
      bsa.push_back(static_cast<uint8_t>(val));
      return;
    }
    size_t bits_left_in_byte = 8 - bsa_boff;
    bsa.back() |= val >> bsa_boff;
    bsa.push_back(val << bits_left_in_byte);
    num_bits += 8;
  }

  void StoreBits16(uint16_t val) {
    if (bsa_boff == 0) {
      bsa.push_back(static_cast<uint8_t>(val >> 8));
      bsa.push_back(static_cast<uint8_t>(val & 255u));
      return;
    }
    size_t bits_left_in_byte = 8 - bsa_boff;
    uint8_t c = val >> 8;
    bsa.back() |= c >> bsa_boff;
    bsa.push_back(c << bits_left_in_byte);
    c = val & 255u;
    bsa.back() |= c >> bsa_boff;
    bsa.push_back(c << bits_left_in_byte);
    num_bits += 16;
  }

  void StoreBits32(uint32_t val) {
    if (bsa_boff == 0) {
      bsa.push_back(static_cast<uint8_t>(        val >> 24));
      bsa.push_back(static_cast<uint8_t>(255u & (val >> 16)));
      bsa.push_back(static_cast<uint8_t>(255u & (val >>  8)));
      bsa.push_back(static_cast<uint8_t>(255u & (val >>  0)));
      return;
    }
    size_t bits_left_in_byte = 8 - bsa_boff;
    uint8_t c = val >> 24;
    bsa.back() |= c >> bsa_boff;
    bsa.push_back(c << bits_left_in_byte);
    c =  255u & (val >> 16);
    bsa.back() |= c >> bsa_boff;
    bsa.push_back(c << bits_left_in_byte);
    c =  255u & (val >>  8);
    bsa.back() |= c >> bsa_boff;
    bsa.push_back(c << bits_left_in_byte);
    c =  255u & (val >>  0);
    bsa.back() |= c >> bsa_boff;
    bsa.push_back(c << bits_left_in_byte);
    num_bits += 32;
  }

  void StoreBits(const vector<char>& inp_bytes, size_t inp_bits) {
    StoreBits(inp_bytes.begin(), inp_bytes.end(), inp_bits);
  }

  template <typename T>
  void StoreBits(T inp_bytes_begin, T inp_bytes_end, size_t inp_bits) {
    size_t inp_bytes_size = inp_bytes_end - inp_bytes_begin;
    if (inp_bits == 0) return;
    size_t old_bsa_boff = bsa_boff;
    num_bits += inp_bits;
    if (bsa_boff == 0) {
      bsa.insert(bsa.end(), inp_bytes_begin, inp_bytes_end);
      bsa_boff = inp_bits % 8;
      if (bsa_boff) {
        bsa.back() &= ~(0xff >> bsa_boff);  // zero out trailing  right-bits
      }
    } else {
      size_t leftover_bits = 0;
      if (inp_bits % 8) {
        leftover_bits = inp_bits % 8;
      } else {
        leftover_bits = 8;
      }
      size_t bits_left_in_byte = 8 - bsa_boff;
      bsa.reserve(bsa.size() + inp_bytes_size);
      for (size_t i = 0; i < inp_bytes_size; ++i) {
        uint8_t c = inp_bytes_begin[i];
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

  template <typename T>
  void StoreBytes(T inp_bytes_begin, T inp_bytes_end) {
    size_t inp_bytes_size = inp_bytes_end - inp_bytes_begin;

    if (bsa_boff == 0) {
      bsa.insert(bsa.end(), inp_bytes_begin, inp_bytes_end);
    } else {
      size_t bits_left_in_byte = 8 - bsa_boff;
      bsa.reserve(bsa.size() + inp_bytes_size);
      for (size_t i = 0; i < inp_bytes_size; ++i) {
        uint8_t c = inp_bytes_begin[i];
        bsa.back() |= c >> bsa_boff;
        bsa.push_back(c << bits_left_in_byte);
      }
    }
    num_bits += inp_bytes_size * 8;
  }

  size_t NumBits() const {
    return num_bits;
  }
  size_t BitsConsumed() const {
    return idx_byte * 8 + idx_boff;
  }
  bool AllConsumed() const {
    return BitsConsumed() >= NumBits();
  }
  size_t BitsRemaining() const {
    return NumBits() - BitsConsumed();
  }

  bool GetBit() {
    if (idx_byte >= bsa.size()) return 0;
    bool bit = bsa[idx_byte] & (0x80 >> idx_boff);
    ++idx_boff;
    if (idx_boff >= 8) {
      ++idx_byte;
      idx_boff -= 8;
    }
    return bit;
  }

  void GetBits(vector<char>* retval, size_t num_bits) {
    size_t output_bytes = (num_bits + 7) / 8;
    retval->reserve(output_bytes);
    size_t old_idx_boff = idx_boff;
    if (num_bits > NumBits()) {
      cerr << "Oops, we're asking to get more bits than are available.\n";
      cerr << "Bits available: " << BitsRemaining() << "\n";
      cerr << "Bits requested: " << num_bits << "\n";
      abort();
    }
    size_t bits_left = num_bits;
    if (idx_boff == 0) {
      retval->insert(retval->end(), bsa.begin() + idx_byte, bsa.begin() + idx_byte + output_bytes);
      idx_byte += num_bits / 8;
      idx_boff = num_bits % 8;
      if (idx_boff) {
        retval->back() &= ~(0xff >> idx_boff);
      }
    } else { // idx_boff != 0. There WILL be shifting about.
      size_t idx_leftover = 8 - idx_boff;
      while (bits_left >= 8) {
        size_t c = bsa[idx_byte] << idx_boff;
        ++idx_byte;
        c |= bsa[idx_byte] >> idx_leftover;
        // cout << "ONE_BYTE DOWN, BITS_LEFT:" << bits_left
        //      << " " << FormatAsBits(&c, 8) << "\n";
        retval->push_back((char)c);
        bits_left -= 8;
      }
      if (bits_left) {
        //cout << "BITS LEFT: " << bits_left << "\n";
        size_t cur_boff = 0;
        size_t cur_byte = 0;
        while (true) {
          size_t bits_to_consume = min(min(8 - cur_boff, idx_leftover), bits_left);
          size_t mask = ~(0xff >> bits_to_consume);
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
  string DebugStr(size_t offset=0, size_t range=1) const {
    stringstream ss;
    size_t num_bits_consumed = idx_byte * 8 + idx_boff;
    num_bits_consumed += offset;
    for (size_t i = 0; i < num_bits_consumed; ++i) {
      if (!(i%8)) ss << "|";
      ss << "-";
    }
    for (size_t i = num_bits_consumed ; i < num_bits_consumed + range; ++i) {
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

  size_t BytesRequired() {
    return bsa.size();
  }
};

#endif  // BITBUCKET_H
