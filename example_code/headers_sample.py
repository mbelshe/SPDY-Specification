#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import zlib
import re
import struct

from common_utils import *
from default_headers import default_requests
from default_headers import default_responses
from harfile import ReadHarFile
from header_freq_tables import request_freq_table
from header_freq_tables import response_freq_table
from headers_codec import FormatOp
from headers_codec import FormatOps
from headers_codec import Spdy4CoDe
from huffman import Huffman
from optparse import OptionParser
from spdy_dictionary import spdy_dict

options = {}

# TODO(eliminate the 'index' parameter in clone and kvsto by
#      adding an index-start to the frame)
# TODO(try var-int encoding for indices)
# TODO(make removals from the LRU implicit-- send no messages about them)
# TODO(use a separate huffman encoding for cookies, and possible path)
# TODO(interpret cookies as binary instead of base-64, does it reduce entropy?)
# TODO(modification to 'toggl' to allow for a list of indices instead
#      of requiring a new operation for each index not in a consecutive range)
# TODO(index renumbering so things which are often used together
#      have near indices. Possibly renumber whever something is referenced)

def KtoV(d):
  return dict((v, k) for k, v in d.iteritems())

def NextIndex(d):
  if not d:
    return 1
  indices = sorted(d.keys())
  prev_idx = 0
  idx = 0
  for idx in indices:
    if idx - prev_idx > 1:
      # jumped up by more than one.
      return prev_idx + 1
    prev_idx = idx
  return idx + 1

class SPDY4(object):
  def __init__(self, options):
    self.compressor   = Spdy4CoDe()
    self.decompressor = Spdy4CoDe()
    self.options = options
    self.hosts = {}
    self.wf = self.compressor.wf

  def ProcessFrame(self, inp_headers, request_headers):
    normalized_host = re.sub('[0-1a-zA-Z-\.]*\.([^.]*\.[^.]*)', '\\1',
                             request_headers[':host'])
    if normalized_host in self.hosts:
      header_group = self.hosts[normalized_host]
    else:
      header_group = NextIndex(KtoV(self.hosts))
      self.hosts[normalized_host] = header_group
    if self.options.f:
      header_group = 0
    inp_ops = self.compressor.MakeOperations(inp_headers, header_group)

    inp_real_ops = self.compressor.OpsToRealOps(inp_ops)
    compressed_blob = self.compressor.Compress(inp_real_ops)
    out_real_ops = self.decompressor.Decompress(compressed_blob)
    out_ops = self.decompressor.RealOpsToOpAndExecute(
        out_real_ops, header_group)
    #FormatOps(out_ops, 'OutOps\t')
    out_headers = self.decompressor.GenerateAllHeaders(header_group)
    return (compressed_blob,
            inp_real_ops, out_real_ops,
            inp_headers,  out_headers,
            inp_ops,      out_ops,
            header_group)

class SPDY3(object):
  def __init__(self, options):
    self.options = options
    self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                                       zlib.DEFLATED, 15)
    self.compressor.compress(spdy_dict);
    self.compressor.flush(zlib.Z_SYNC_FLUSH)

  def ProcessFrame(self, inp_headers, request_headers):
    raw_spdy3_frame = self.Spdy3HeadersFormat(inp_headers)
    compress_me_payload = raw_spdy3_frame[12:]
    final_frame = raw_spdy3_frame[:12]
    final_frame += self.compressor.compress(compress_me_payload)
    final_frame += self.compressor.flush(zlib.Z_SYNC_FLUSH)
    return (final_frame, raw_spdy3_frame)

  def Spdy3HeadersFormat(self, request):
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

class HTTP1(object):
  def __init__(self, options):
    self.options = options
    self.compressor = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION,
                                       zlib.DEFLATED, 15)
    self.compressor.compress(spdy_dict);
    self.compressor.flush(zlib.Z_SYNC_FLUSH)

  def ProcessFrame(self, inp_headers, request_headers):
    http1_frame = self.HTTP1HeadersFormat(inp_headers)
    return ((self.compressor.compress(http1_frame) +
             self.compressor.flush(zlib.Z_SYNC_FLUSH)),
             http1_frame)

  def HTTP1HeadersFormat(self, frame):
    return FormatAsHTTP1(frame)

def CompareHeaders(a, b):
  a = dict(a)
  b = dict(b)
  output = []
  if 'cookie' in a:
    splitvals = a['cookie'].split(';')
    a['cookie'] = '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
  if 'cookie' in b:
    splitvals = b['cookie'].split(';')
    b['cookie'] = '; '.join(sorted([x.lstrip(' ') for x in splitvals]))
  for (k,v) in a.iteritems():
    if not k in b:
      output.append('\tkey: %s present in only one (A)' % k)
      continue
    if v != b[k]:
      output.append('\tkey: %s has mismatched values:' % k)
      output.append('\t  -> %s' % v)
      output.append('\t  -> %s' % b[k])
    del b[k]
  for (k, v) in b.iteritems():
      output.append('\tkey: %s present in only one (B)' % k)
  return '\n'.join(output)


# this requires that both spdy4 and http1 be present in the list of framers.
def ProcessAndFormat(top_message, frametype_message,
                     framers,
                     request, test_frame,
                     accumulator):
  if options.v >= 1:
    print '    ######## %s ########' % top_message
  processing_results = []

  for protocol_name, framer in framers.iteritems():
    result = framer.ProcessFrame(test_frame, request)
    if protocol_name == 'spdy4':
      spdy4_result = result
      processing_results.append((protocol_name, result[:2]))
    elif protocol_name == 'http1':
      processing_results.append((protocol_name, result))
      http1_uncompressed_size = len(result[1])
    else:
      processing_results.append((protocol_name, result))

  if options.v >= 2:
    for op in spdy4_result[6]:
      print '\t rq_op: ', FormatOp(op)

  message = CompareHeaders(test_frame, spdy4_result[4])
  if message:
    print 'Something is wrong with the request.'
    if options.v >= 1:
      print message
    if options.v >= 5:
      print 'It should be:'
      for k,v in         request.iteritems(): print '\t%s: %s' % (k,v)
      print 'but it was:'
      for k,v in spdy4_result[4].iteritems(): print '\t%s: %s' % (k,v)

  lines = []
  for protocol_name, results in processing_results:
    compressed_size, uncompressed_size = map(len, results)
    accumulator[protocol_name][0] += compressed_size
    accumulator[protocol_name][1] += uncompressed_size
    lines.append( ('%s %s' % (protocol_name, frametype_message),
                  uncompressed_size,
                  compressed_size,
                  1.0 * compressed_size / http1_uncompressed_size) )
  if options.v >= 1:
    print '                            UC  |  CM  | ratio'
    for line in sorted(lines):
      print '     %s frame size: %4d | %4d | %2.2f ' % line
    print


def main():
  parser = OptionParser()
  parser.add_option('-n', '--new',
                    type='int',
                    dest='n',
                    help='if set, uses the new serialization method',
                    default=0)
  parser.add_option('-v', '--verbose',
                    type='int',
                    dest='v',
                    help='Sets verbosity. At v=1, the opcodes will be printed. '
                    'At v=2, so will the headers [default: %default]',
                    default=0,
                    metavar='VERBOSITY')
  parser.add_option('-f', '--force_streamgroup',
                    dest='f',
                    help='If set, everything will use stream-group 0. '
                    '[default: %default]',
                    default=0)
  global options
  (options, args) = parser.parse_args()


  print options
  requests = default_requests
  responses = default_responses
  if args >= 1:
    requests = []
    responses = []
    for filename in args:
      (har_requests, har_responses) = ReadHarFile(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)

  spdy4_req = SPDY4(options)
  spdy4_req.compressor.huffman_table = Huffman(request_freq_table)
  spdy4_req.decompressor.huffman_table = spdy4_req.compressor.huffman_table
  spdy3_req = SPDY3(options)
  http1_req = HTTP1(options)
  spdy4_rsp = SPDY4(options)
  spdy4_rsp.compressor.huffman_table = Huffman(response_freq_table)
  spdy4_rsp.decompressor.huffman_table = spdy4_rsp.compressor.huffman_table
  spdy3_rsp = SPDY3(options)
  http1_rsp = HTTP1(options)

  req_accum = {'http1': [0,0], 'spdy3': [0,0], 'spdy4': [0,0]}
  rsp_accum = {'http1': [0,0], 'spdy3': [0,0], 'spdy4': [0,0]}
  for i in xrange(len(requests)):
    request = requests[i]
    response = responses[i]
    if options.v >= 2:
      print '##################################################################'
      print '    ####### request-path: "%s"' % requests[i][':path'][:80]
    ProcessAndFormat("request", "req",
        {'http1': http1_req, 'spdy3': spdy3_req, 'spdy4': spdy4_req},
        request, request,
        req_accum)
    ProcessAndFormat("response", "rsp",
        {'http1': http1_rsp, 'spdy3': spdy3_rsp, 'spdy4': spdy4_rsp},
        request, response,
        rsp_accum)
  print 'Thats all folks. If you see this, everything worked OK'

  print '######################################################################'
  print '######################################################################'
  print
  print '                                       http1   |   spdy3   |   spdy4 '




  fmtarg = (req_accum['http1'][1], req_accum['spdy3'][1], req_accum['spdy4'][1])
  print 'Req                Compressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg

  fmtarg = (req_accum['http1'][0], req_accum['spdy3'][0], req_accum['spdy4'][0])
  print 'Req              Uncompressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg


  fmtarg = (rsp_accum['http1'][1], rsp_accum['spdy3'][1], rsp_accum['spdy4'][1])
  print 'Rsp                Compressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg

  fmtarg = (rsp_accum['http1'][0], rsp_accum['spdy3'][0], rsp_accum['spdy4'][0])
  print 'Rsp              Uncompressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg



  if req_accum['http1'][1]:
    fmtarg = (1.0 * req_accum['http1'][0]/req_accum['http1'][1],
              1.0 * req_accum['spdy3'][0]/req_accum['http1'][1],
              1.0 * req_accum['spdy4'][0]/req_accum['http1'][1])
    print 'Req   Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  ' % fmtarg

  if rsp_accum['http1'][0]:
    fmtarg = (1.0 * rsp_accum['http1'][0]/rsp_accum['http1'][1],
              1.0 * rsp_accum['spdy3'][0]/rsp_accum['http1'][1],
              1.0 * rsp_accum['spdy4'][0]/rsp_accum['http1'][1])
    print 'Rsp   Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  ' % fmtarg

  print



  #print repr(spdy4_rq.wf)
  #print
  #print spdy4_rq.wf.length_freaks
  #print

  #print repr(spdy4_rs.wf)
  #print
  #print spdy4_rs.wf.length_freaks
  #print
  #print spdy4_rs.wf

main()
