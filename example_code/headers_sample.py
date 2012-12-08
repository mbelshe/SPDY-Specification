#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import re
import optparse

import harfile
import default_headers
import http1_gzip
import spdy3_codec
import spdy4_codec

options = {}

def CompareHeaders(a, b):
  """
  Compares two sets of headers, and returns a message denoting any differences.
  It ignores ordering differences in cookies, but tests that all the content
  does exist in both.
  If nothing is different, it returns an empty string
  """
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


def ProcessAndFormat(top_message,
                     frametype_message,
                     protocol_name_field_width,
                     framers,
                     baseline_name,
                     request, test_frame,
                     accumulator):
  """
  This uses the various different framing classes to encode/compress,
  potentially report on the results of each, and then accumulates stats on the
  effectiveness of each.
  'top_message' is the message printed at the top of the results,
                e.g. "request foo"
  'frametype_message' denotes the kind of message, e.g. request or response.
  'framers' is a dictionary of protocol_name: framer. It *must* include a
           'spdy4' and 'http1' framer if the function is to do its job properly.
  'request' is the request associated with the test_frame. If the test_frame is
            a request, this would simply be a repetition of that. If the
            test_frame is a response, this would be the request which engendered
            the response.
  'accumulator' is a dictionary of protocol_name to list-of-ints (of size two).
               this function adds the compressed and uncompressed sizes into
               the dictionary entry corresponding to the protocol_name for each
               of the framers in 'framers'
  """
  if options.v >= 1:
    print '    ######## %s ########' % top_message
  processing_results = []

  baseline_size = None
  for protocol_name, framer in framers.iteritems():
    result = framer.ProcessFrame(test_frame, request)
    processing_results.append((protocol_name, result))
    if protocol_name == baseline_name:
      baseline_size = len(result['serialized_ops'])

    if options.v >= 2 and 'decompressed_interpretable_ops' in result:
      framer.PrintOps(result['decompressed_interpretable_ops'])
    if 'output_headers' in result:
      output_headers = result['output_headers']
      message = CompareHeaders(test_frame, output_headers)
      if message:
        print 'Something is wrong with this frame.'
        if options.v >= 1:
          print message
        if options.v >= 5:
          print 'It should be:'
          for k,v in        request.iteritems(): print '\t%s: %s' % (k,v)
          print 'but it was:'
          for k,v in output_headers.iteritems(): print '\t%s: %s' % (k,v)

  lines = []
  for protocol_name, results in processing_results:
    compressed_size = len(results['compressed'])
    uncompressed_size = len(results['serialized_ops'])
    accumulator[protocol_name][0] += compressed_size
    accumulator[protocol_name][1] += uncompressed_size
    if baseline_size is not None:
      ratio = 1.0 * compressed_size / baseline_size
    else:
      ratio = 0
    lines.append( ('%s %s' % (protocol_name, frametype_message),
                  uncompressed_size,
                  compressed_size,
                  ratio) )
  if options.v >= 1:
    print ('\t%% %ds              UC  |  CM  | ratio' % (
           protocol_name_field_width+10)) % ''
    line_format = '\t%% %ds frame size: %%4d | %%4d | %%2.2f ' % (
        protocol_name_field_width+10)
    for line in sorted(lines):
      print line_format % line
    print

# comman-separated list of name[="string"]
def ParseCodecList(options_string):
  key_accum= []
  val_accum= []
  parsed_params = {}

  i = 0
  os_len = len(options_string)
  parsing_val = False
  escape = False
  while i < os_len:
    c = options_string[i]
    i += 1
    if not parsing_val:
      if c == ',':
        if key_accum:
          parsed_params[''.join(key_accum)] = ''.join(val_accum)
          key_accum = []
          val_accum = []
      elif c == '=':
        parsing_val = True
        c = options_string[i]
        i += 1
        if c != '"':
          raise StandardError()
        continue
      else:  # c != ',' and c != '='
        key_accum.append(c)

    else:  # parsing_key == False
      if escape:
        escape = False
        val_accum.append(c)
      else:
        if c == '\\':
          escape = True
        elif c == '"':
          parsing_val = False
        else:
          val_accum.append(c)
  if key_accum:
    parsed_params[''.join(key_accum)] = ''.join(val_accum)
  print parsed_params
  return parsed_params

def main():
  parser = optparse.OptionParser()
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
  parser.add_option('-c', '--codecs',
                    dest='c',
                    help='If set, the argument will be parsed as a'
                    'comma-separated list of compression module names'
                    'to use and the parameters to be passed to each.'
                    'e.g. --c'
                    'http1_gzip,spdy3_codec,spdy4_codec,exec_codec="exec_parap1,'
                    'exec_param2" [default: %default]',
                    default="http1_gzip,spdy3_codec,spdy4_codec")
  parser.add_option('-b', '--baseline',
                    dest='b',
                    help='Baseline codec-- all comparitive ratios are based on'
                    'this',
                    default='http1_gzip')
  global options
  (options, args) = parser.parse_args()
  codec_params = ParseCodecList(options.c)

  # load .har files
  requests = default_headers.default_requests
  responses = default_headers.default_responses
  if args >= 1:
    requests = []
    responses = []
    for filename in args:
      (har_requests, har_responses) = harfile.ReadHarFile(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)

  baseline_name = options.b

  # load indicated codec modules and prepare for their execution
  codec_names = []
  codec_modules = {}
  req_accum = {}
  rsp_accum = {}
  request_processors = {}
  response_processors = {}
  module_name_to_module = {}
  longest_module_name = 0
  for module_name, params in codec_params.iteritems():
    if len(module_name) > longest_module_name:
      longest_module_name = len(module_name)
    module = __import__(module_name, globals(), locals(), [], -1)
    module_name_to_module[module_name] = module
    req_accum[module_name] = [0,0]
    rsp_accum[module_name] = [0,0]

    request_processor = module.Processor(options, True, params)
    request_processors[module_name] = request_processor
    response_processor = module.Processor(options, False, params)
    response_processors[module_name] = response_processor

  for i in xrange(len(requests)):
    request = requests[i]
    response = responses[i]
    if options.v >= 2:
      print '##################################################################'
      print '    ####### request-path: "%s"' % requests[i][':path'][:80]
    ProcessAndFormat("request", "req",
        longest_module_name,
        request_processors,
        baseline_name,
        #{'http1': http1_req, 'spdy3': spdy3_req, 'spdy4': spdy4_req},
        request, request,
        req_accum)
    ProcessAndFormat("response", "rsp",
        longest_module_name,
        response_processors,
        baseline_name,
        #{'http1': http1_rsp, 'spdy3': spdy3_rsp, 'spdy4': spdy4_rsp},
        request, response,
        rsp_accum)
  print 'Thats all folks. If you see this, everything worked OK'

  print '######################################################################'
  print '######################################################################'
  print
  baseline_size = 0
  lines = []
  if baseline_name in req_accum:
    baseline_size = req_accum[baseline_name][1]
  for module_name, stats in req_accum.iteritems():
    (compressed_size, uncompressed_size) = stats
    ratio = 0
    if baseline_size > 0:
      ratio = 1.0* compressed_size / baseline_size
    lines.append(('req',
                  module_name,
                  uncompressed_size,
                  compressed_size,
                  ratio) )
  if baseline_name in rsp_accum:
    baseline_size = rsp_accum[baseline_name][1]
  for module_name, stats in rsp_accum.iteritems():
    (compressed_size, uncompressed_size) = stats
    ratio = 0
    if baseline_size > 0:
      ratio = 1.0* compressed_size / baseline_size
    lines.append(('rsp',
                  module_name,
                  uncompressed_size,
                  compressed_size,
                  ratio) )
  print ('\t    %% %ds                UC    |    CM    | ratio' % (
         longest_module_name+10)) % ''
  line_format = '\t%%s %% %ds frame size: %%8d | %%8d | %%2.2f ' % (
      longest_module_name+10)
  for line in sorted(lines):
    print line_format % line
  print

main()
