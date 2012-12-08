#!/usr/bin/python
import sys
import struct
import os

def main():
  while True:
    headers = []
    headers_len = 0
    name = ""
    if len(sys.argv) >= 2:
      name = sys.argv[1]
    else:
      name = "%d" % os.getpid()
    while True:
      line = sys.stdin.readline()
      if line == "":
        return
      headers.append(line)
      headers_len += len(line)
      if line == "\r\n" or line == "\n":
        break


    wire_len = struct.pack("q", headers_len)
    sys.stdout.write(wire_len)
    data = ''.join(headers)
    sys.stdout.write(data)
    sys.stdout.flush()

main()
