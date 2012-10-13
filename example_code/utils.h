// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
#ifndef UTILS_H
#define UTILS_H

#include <sstream>
#include <string>

using std::string;
using std::stringstream;

string ReadableUShort(uint16_t c);

template <typename T>
string FormatAsBits(const T& v, int num_bits, int offset = 0) {
  stringstream retval;
  for (int i = 0; i < num_bits; ++i) {
    int byte_idx = i / 8;
    unsigned int c = v[byte_idx];
    if ((i + offset) % 8 == 0)
      retval << "|";
    retval << ((c & (0x80U >> (i % 8))) > 0);
  }
  return retval.str();
}

template <>
string FormatAsBits<uint32_t>(const uint32_t& v, int num_bits, int offset);

template <>
string FormatAsBits<uint16_t>(const uint16_t& v, int num_bits, int offset);

template <>
string FormatAsBits<uint8_t>(const uint8_t& v, int num_bits, int offset);

#endif
