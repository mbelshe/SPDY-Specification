#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from harfile import ReadHarFile
from optparse import OptionParser
import sys
import os

def FormatIt(frame):
  for (k, v) in frame.iteritems():
    print "%s: %s" %(k, v)

def main():
  parser = OptionParser()
  (options, args) = parser.parse_args()
  if not args:
    return
  if args >= 1:
    requests = []
    responses = []
    for filename in args:
      sys.stderr.write(filename)
      (har_requests, har_responses) = ReadHarFile(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)
  for i in xrange(len(requests)):
    FormatIt(requests[i])
    print
    FormatIt(responses[i])
    print
  sys.stdin.close()
  sys.stdout.close()
  sys.stderr.close()
  os.close(0)
  os.close(1)
  os.close(2)

main()
