#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from bit_bucket import BitBucket

def RunTestCase(bb, testcase):
  pre_bb = str(bb)
  for instruction in testcase:
    (store_this, expected_output) = instruction
    bb.StoreBits(store_this)
    str_bb = str(bb)
    if str_bb != expected_output:
      print 
      print "Failure!: \"%s\" != \"%s\"" % (str_bb, expected_output)
      print "op: ", store_this
      print "Pre bb:   \"%s\"" % pre_bb
      print "expected: \"%s\"" % expected_output
      print "post bb:  \"%s\"" % str_bb
      raise StandardError()
    pre_bb = str_bb


def main():
  bb = BitBucket()
  testcase_a = [
    (([0xFF,0],6+8),  "|11111111|000000 [6]"),
    (([0xFF], 3),     "|11111111|00000011|1 [1]"),
    (([0x00], 3),     "|11111111|00000011|1000 [4]"),
    (([0xFF,0], 8+6), "|11111111|00000011|10001111|11110000|00 [2]"),
    (([0xFF], 4),     "|11111111|00000011|10001111|11110000|001111 [6]"),
    (([0x0], 4),      "|11111111|00000011|10001111|11110000|00111100|00 [2]"),
    ]
  RunTestCase(bb, testcase_a)


  testcase_b = [
    (([0xF0], 5), "|11110 [5]"),
    (([0x0F], 5), "|11110000|01 [2]"),
    (([0xF0], 5), "|11110000|0111110 [7]"),
    (([0x0F], 5), "|11110000|01111100|0001 [4]"),
    (([0xF0], 5), "|11110000|01111100|00011111|0 [1]"),
    (([0x0F], 5), "|11110000|01111100|00011111|000001 [6]"),
    (([0xF0], 5), "|11110000|01111100|00011111|00000111|110 [3]"),
    (([0x0F], 5), "|11110000|01111100|00011111|00000111|11000001 [0]"),
    (([0xF0], 5), "|11110000|01111100|00011111|00000111|11000001|11110 [5]"),
    ]
  bb.Clear()
  RunTestCase(bb, testcase_b)


  testcase_c = [
    (([0xF0], 1),        "|1 [1]"),
    (([0x0F], 1),        "|10 [2]"),
    (([0xF0], 1),        "|101 [3]"),
    (([0x0F], 1),        "|1010 [4]"),
    (([0xF0], 1),        "|10101 [5]"),
    (([0x0F], 1),        "|101010 [6]"),
    (([0xF0], 1),        "|1010101 [7]"),
    (([0x0F], 1),        "|10101010 [0]"),
    (([0xF0], 1),        "|10101010|1 [1]"),
    (([0x00,0xFF], 8+7), "|10101010|10000000|01111111 [0]"),
    ]
  bb.Clear()
  RunTestCase(bb, testcase_c)


  testcase_d = [
    (([0xF0], 8),        "|11110000 [0]"),
    (([0xF0], 8),        "|11110000|11110000 [0]"),
    (([0xF0], 1),        "|11110000|11110000|1 [1]"),
    (([0x0F], 8),        "|11110000|11110000|10000111|1 [1]"),
    ]
  bb.Clear()
  RunTestCase(bb, testcase_d)

  testcase_e = [
    (([0,52], 8+6), "|00000000|001101 [6]"),
    (([185], 8),    "|00000000|00110110|111001 [6]"),
   ]
  bb.Clear()
  RunTestCase(bb, testcase_e)
  print "Success!"


main()
