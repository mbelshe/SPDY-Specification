# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import zlib
import struct
import spdy_dictionary

class Processor(object):
  def __init__(self, options, is_request, params):
    # 'is_request' and 'params' are ignored
    self.options = options
    self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                                       zlib.DEFLATED, 15)
    self.compressor.compress(spdy_dictionary.spdy_dict);
    self.compressor.flush(zlib.Z_SYNC_FLUSH)

  def ProcessFrame(self, inp_headers, request_headers):
    """
    'inp_headers' are the headers that will be processed
    'request_headers' are the request headers associated with this frame
       the host is extracted from this data. For a response, this would be
       the request that engendered the response. For a request, it is just
       the request again.
    It outputs: (spdy3_frame_compressed_with_gzip, uncompressed_spdy3_frame)
    Note that compressing with an unmodified stream-compressor like gzip is
    effective, however it is insecure.
    """

    raw_spdy3_frame = self.Spdy3HeadersFormat(inp_headers)
    compress_me_payload = raw_spdy3_frame[12:]
    final_frame = raw_spdy3_frame[:12]
    final_frame += self.compressor.compress(compress_me_payload)
    final_frame += self.compressor.flush(zlib.Z_SYNC_FLUSH)
    retval = {
      'compressed': final_frame,
      'serialized_ops': raw_spdy3_frame
    }
    return retval

  def Spdy3HeadersFormat(self, request):
    """
    Formats the provided headers in SPDY3 format, uncompressed
    """
    out_frame = []
    frame_len = 0
    for (key, val) in request.iteritems():
      frame_len += 4
      frame_len += len(key)
      frame_len += 4
      frame_len += len(val)
    stream_id = 1
    num_kv_pairs = len(request.keys())
    out_frame.append(struct.pack('!L', 0x1 << 31 | 0x11 << 15 | 0x8))
    out_frame.append(struct.pack('!L', frame_len))
    out_frame.append(struct.pack('!L', stream_id))
    out_frame.append(struct.pack('!L', num_kv_pairs))
    for (key, val) in request.iteritems():
      out_frame.append(struct.pack('!L', len(key)))
      out_frame.append(key)
      out_frame.append(struct.pack('!L', len(val)))
      out_frame.append(val)
    return ''.join(out_frame)

