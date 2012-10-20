// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
#ifndef SPDY4_HEADERS_CODEC_H__
#define SPDY4_HEADERS_CODEC_H__

#include <stdint.h>

#include "header_freq_tables.h"
#include "trivial_http_parse.h"
#include "bit_bucket.h"

typedef uint16_t LRUIdx;

typedef BitBucket OutputStream;

class SPDY4HeadersCodecImpl;

class SPDY4HeadersCodec {
 private:
  SPDY4HeadersCodecImpl* impl;
 public:
  SPDY4HeadersCodec(const FreqTable& sft);
  ~SPDY4HeadersCodec();

  size_t CurrentStateSize() const;

  void OutputCompleteHeaderFrame(OutputStream* os,
                                 uint32_t stream_id,
                                 uint32_t group_id,
                                 const HeaderFrame& headers,
                                 bool this_ends_the_frame);

  void SetMaxStateSize(size_t max_size);

  void SetMaxVals(size_t max_size);
};


#endif //SPDY4_HEADERS_CODEC_H__


