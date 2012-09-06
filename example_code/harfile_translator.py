#!/usr/bin/python

from harfile import ReadHarFile
from optparse import OptionParser

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
      (har_requests, har_responses) = ReadHarFile(filename)
      requests.extend(har_requests)
      responses.extend(har_responses)
  for i in xrange(len(requests)):
    FormatIt(requests[i])
    print
    FormatIt(responses[i])
    print

main()
