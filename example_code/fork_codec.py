# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import struct
import common_utils

class Processor(object):
  def __init__(self, options, is_request, params):
    print "CREATING FORK PROCESSOR FOR", params
    # 'is_request' is  ignored
    self.options = options
    self.process = subprocess.Popen(params.split(),
                                    #bufsize=-1,
                                    shell=False,
                                    stdout=subprocess.PIPE,
                                     stdin=subprocess.PIPE)

  def ProcessFrame(self, inp_headers, request_headers):
    """
    'inp_headers' are the headers that will be processed
    'request_headers' are the request headers associated with this frame
       the host is extracted from this data. For a response, this would be
       the request that engendered the response. For a request, it is just
       the request again.
    """
    http1_frame = common_utils.FormatAsHTTP1(inp_headers)
    #print "Printing\n", http1_frame
    self.process.stdin.write(http1_frame)
    output = self.process.stdout.read(8)
    size = struct.unpack("q", output)[0]
    output = self.process.stdout.read(int(size))
    retval = {
      'compressed': output,
      'serialized_ops': output
    }
    return retval
