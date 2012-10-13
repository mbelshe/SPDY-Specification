// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
#include <stdint.h>

#include "header_freq_tables.h"
#include "trivial_http_parse.h"

typedef uint16_t LRUIdx;

class OutputStream {
 public:
  vector<char> storage;

  uint32_t StreamPos() {
    return storage.size();
  }
  uint8_t GetUint8(uint32_t pos) {
    return static_cast<uint8_t>(storage[pos]);
  }
  void WriteUint8(uint8_t byte) {
    storage.push_back(static_cast<char>(byte));
  }
  void WriteUint16(uint16_t shrt) {
    //shrt = htons(shrt);
    storage.insert(storage.end(), &shrt, &shrt + 2);
  }
  void WriteUint32(uint32_t word) {
    //wrd = htonl(word);
    storage.insert(storage.end(), &word, &word + 4);
  }
  template <typename T>
  void WriteBytes(const T begin, const T end) {
    storage.insert(storage.end(), begin, end);
  }
  void OverwriteUint16(uint32_t pos, uint16_t arg) {
    //shrt = htons(shrt);
    uint8_t byte = arg >> 8;
    OverwriteUint8(pos, byte);
    byte = arg & 0xFF;
    OverwriteUint8(pos + 1, byte);
  }
  void OverwriteUint8(uint32_t pos, uint8_t byte) {
    storage[pos] = static_cast<char>(byte);
  }
};

class SPDY4HeadersCodecImpl;

class SPDY4HeadersCodec {
 private:
  SPDY4HeadersCodecImpl* impl;
 public:
  SPDY4HeadersCodec(const FreqTable& sft);

  size_t CurrentStateSize() const;

  void OutputCompleteHeaderFrame(OutputStream* os,
                                 uint32_t stream_id,
                                 uint32_t group_id,
                                 const HeaderFrame& headers,
                                 bool this_ends_the_frame);
};




