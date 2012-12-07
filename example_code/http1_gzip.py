# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import zlib
import common_utils
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
    It outputs: (http1_frame_compressed_with_gzip, uncompressed_http1_frame)
    Note that compressing with an unmodified stream-compressor like gzip is
    effective, however it is insecure.
    """
    http1_frame = common_utils.FormatAsHTTP1(inp_headers)
    compressed_data = ''.join([self.compressor.compress(http1_frame),
                               self.compressor.flush(zlib.Z_SYNC_FLUSH)])
    retval = {
      'compressed': compressed_data,
      'serialized_ops': http1_frame
    }
    return retval


def HanderName():
  return "http1"
