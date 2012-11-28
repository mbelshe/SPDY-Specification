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
    spdy3_frame = self.Spdy3HeadersFormat(inp_headers)
    return ((self.compressor.compress(spdy3_frame) +
             self.compressor.flush(zlib.Z_SYNC_FLUSH)),
             spdy3_frame)

  def Spdy3HeadersFormat(self, request):
    out_frame = []
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
      output.append('key: %s present in only one (A)' % k)
      continue
    if v != b[k]:
      output.append('key: %s has mismatched values:' % k)
      output.append('  -> %s' % v)
      output.append('  -> %s' % b[k])
    del b[k]
  for (k, v) in b.iteritems():
      output.append('key: %s present in only one (B)' % k)
  return '\n'.join(output)


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

  spdy4_rq = SPDY4(options)
  spdy4_rq.compressor.huffman_table = Huffman(request_freq_table)
  spdy4_rq.decompressor.huffman_table = spdy4_rq.compressor.huffman_table
  spdy3_rq = SPDY3(options)
  http1_rq = HTTP1(options)
  spdy4_rs = SPDY4(options)
  spdy4_rs.compressor.huffman_table = Huffman(response_freq_table)
  spdy4_rs.decompressor.huffman_table = spdy4_rs.compressor.huffman_table
  spdy3_rs = SPDY3(options)
  http1_rs = HTTP1(options)

  print '        UC: UnCompressed frame size'
  print '        CM: CoMpressed frame size'
  print '        UR: Uncompressed / Http uncompressed'
  print '        CR:   Compressed / Http compressed'
  def framelen(x):
    return  len(x) + 10
  h1usrq = 0
  h1csrq = 0
  s3usrq = 0
  s3csrq = 0
  s4usrq = 0
  s4csrq = 0
  h1usrs = 0
  h1csrs = 0
  s3usrs = 0
  s3csrs = 0
  s4usrs = 0
  s4csrs = 0
  for i in xrange(len(requests)):
    request = requests[i]
    response = responses[i]
    if options.v >= 2:
      print '##################################################################'
      print '####### request-path: "%s"' % requests[i][':path'][:80]
    if options.v >= 4:
      print '######## request  ########'
      for k,v in request.iteritems():
        print '\t',k, ':', v

    rq4 = spdy4_rq.ProcessFrame(request, request)
    rq3 = spdy3_rq.ProcessFrame(request, request)
    rqh = http1_rq.ProcessFrame(request, request)

    if options.v >= 2:
      print
      for op in rq4[6]:
        print '\trq_op: ', FormatOp(op)

    message = CompareHeaders(request, rq4[4])
    if message:
      print 'Something is wrong with the request.'
      if options.v >= 1:
        print message
      if options.v >= 5:
        print 'It should be:'
        for k,v in request.iteritems(): print '\t%s: %s' % (k,v)
        print 'but it was:'
        for k,v in  rq4[4].iteritems(): print '\t%s: %s' % (k,v)

    (h1comrq, h1uncomrq) = map(len, rqh)
    h1usrq += h1uncomrq; h1csrq += h1comrq
    (s3comrq, s3uncomrq) = map(framelen, rq3)
    s3usrq += s3uncomrq; s3csrq += s3comrq
    (s4comrq, s4uncomrq) = map(len, rq4[:2])
    s4usrq += s4uncomrq; s4csrq += s4comrq

    lines = [
    ('http1 req', h1uncomrq, h1comrq, 1.0*h1comrq/h1uncomrq),
    ('spdy3 req', s3uncomrq, s3comrq, 1.0*s3comrq/h1uncomrq),
    ('spdy4 req', s4uncomrq, s4comrq, 1.0*s4comrq/h1uncomrq),
    ]

    if options.v >= 1:
      print '                            UC  |  CM  |  ratio'
      for fmtarg in lines:
        print '     %s frame size: %4d | %4d | %2.2f ' % fmtarg

    #if options.v >= 4:
    #  print '######## response ########'
    #  for k,v in response.iteritems():
    #    print '\t',k, ':', v

    #rs4 = spdy4_rs.ProcessFrame(response, request)
    #rs3 = spdy3_rs.ProcessFrame(response, request)
    #rsh = http1_rs.ProcessFrame(response, request)

    #if options.v >= 2:
    #  print
    #  for op in rs4[6]:
    #    print '\trs_op: ', FormatOp(op)
    #  print

    #message = CompareHeaders(response, rs4[4])
    #if message:
    #  print 'Something is wrong with the response.'
    #  if options.v >= 1:
    #    print message

    #(h1comrs, h1uncomrs) = map(len, rsh)
    #h1usrs += h1uncomrs; h1csrs += h1comrs
    #(s3comrs, s3uncomrs) = map(framelen, rs3)
    #s3usrs += s3uncomrs; s3csrs += s3comrs
    #(s4comrs, s4uncomrs) = map(len, rs4[:2])
    #s4usrs += s4uncomrs; s4csrs += s4comrs


    #lines = [
    #('http1 res', h1uncomrs, h1comrs, 1.0*h1uncomrs/h1uncomrs, 1.0*h1comrs/h1comrs),
    #('spdy3 res', s3uncomrs, s3comrs, 1.0*s3uncomrs/h1uncomrs, 1.0*s3comrs/h1comrs),
    #('spdy4 res', s4uncomrs, s4comrs, 1.0*s4uncomrs/h1uncomrs, 1.0*s4comrs/h1comrs),
    #]

    #if options.v >= 1:
    #  print '                            UC  |  CM  |  UR  |  CR'
    #  for fmtarg in lines:
    #    print '     %s frame size: %4d | %4d | %2.2f | %2.2f' % fmtarg
    if options.v >= 1:
      print
  print 'Thats all folks. If you see this, everything worked OK'

  print '######################################################################'
  print '######################################################################'
  print
  print '                                       http1   |   spdy3   |   spdy4 '
  fmtarg = (h1usrq, s3usrq, s4usrq)
  print 'Req              Uncompressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg
  fmtarg = (h1csrq,  s3csrq, s4csrq)
  print 'Req                Compressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg

  if h1usrq:
    fmtarg = (h1usrq*1./h1usrq,  s3usrq*1./h1usrq, s4usrq*1./h1usrq)
    print 'Req Uncompressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  ' % fmtarg
    fmtarg = (h1csrq*1./h1usrq,  s3csrq*1./h1usrq, s4csrq*1./h1usrq)
    print 'Req   Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  ' % fmtarg
    print
  fmtarg = (h1usrs, s3usrs, s4usrs)
  #print 'Res              Uncompressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg
  #fmtarg = (h1csrs,  s3csrs, s4csrs)
  #print 'Res                Compressed Sums:  % 8d  | % 8d  | % 8d  ' % fmtarg
  #if h1usrs:
  #  fmtarg = (h1usrs*1./h1usrs,  s3usrs*1./h1usrs, s4usrs*1./h1usrs)
  #  print 'Res Uncompressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  ' % fmtarg
  #  fmtarg = (h1csrs*1./h1usrs,  s3csrs*1./h1usrs, s4csrs*1./h1usrs)
  #  print 'Res   Compressed/uncompressed HTTP:  % 2.5f  | % 2.5f  | % 2.5f  ' % fmtarg
  #print



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
