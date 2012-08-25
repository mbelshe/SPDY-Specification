#!/usr/bin/python

from huffman import Huffman
from bit_bucket import BitBucket
from bit_bucket import PrintAsBits

request_freq_table = [
  ('\x00', 0), ('\x01', 0), ('\x02', 0), ('\x03', 0), ('\x04', 0), ('\x05', 0),
  ('\x06', 0), ('\x07', 0), ('\x08', 0), ('\t', 0), ('\n', 0), ('\x0b', 0),
  ('\x0c', 0), ('\r', 0), ('\x0e', 0), ('\x0f', 0), ('\x10', 0), ('\x11', 0),
  ('\x12', 0), ('\x13', 0), ('\x14', 0), ('\x15', 0), ('\x16', 0), ('\x17', 0),
  ('\x18', 0), ('\x19', 0), ('\x1a', 0), ('\x1b', 0), ('\x1c', 0), ('\x1d', 0),
  ('\x1e', 0), ('\x1f', 0), (' ', 28), ('!', 27), ('"', 0), ('#', 0),
  ('$', 2), ('%', 1273), ('&', 1293), ("'", 2), ('(', 23), (')', 23),
  ('*', 18), ('+', 15), (',', 875), ('-', 1222), ('.', 2212), ('/', 3366), 
  ('0', 2419), ('1', 2743), ('2', 3072), ('3', 2358), ('4', 1845), ('5', 1528),
  ('6', 1796), ('7', 1448), ('8', 1585), ('9', 1453), (':', 147), (';', 122),
  ('<', 0), ('=', 1692), ('>', 0), ('?', 222), ('@', 0), ('A', 771),
  ('B', 354), ('C', 399), ('D', 651), ('E', 314), ('F', 709), ('G', 462),
  ('H', 246), ('I', 489), ('J', 212), ('K', 207), ('L', 329), ('M', 269),
  ('N', 306), ('O', 210), ('P', 313), ('Q', 244), ('R', 315), ('S', 396),
  ('T', 339), ('U', 351), ('V', 355), ('W', 243), ('X', 250), ('Y', 251),
  ('Z', 257), ('[', 2), ('\\', 0), (']', 2), ('^', 0), ('_', 1442),
  ('`', 0), ('a', 3281), ('b', 1184), ('c', 2353), ('d', 1564), ('e', 3447),
  ('f', 802), ('g', 1917), ('h', 988), ('i', 2488), ('j', 792), ('k', 529),
  ('l', 1571), ('m', 1980), ('n', 2526), ('o', 2349), ('p', 2016), ('q', 312),
  ('r', 2003), ('s', 3133), ('t', 2752), ('u', 974), ('v', 763), ('w', 764),
  ('x', 564), ('y', 586), ('z', 358), ('{', 11), ('|', 0), ('}', 11),
  ('~', 4), ('\x7f', 0), ('\x80', 1029)]


test_data = [
    "abbcccddddeeeee",
    "foobarbaz",
    "0-2rklnsvkl;-23kDFSi01k0=",
    "-9083480-12hjkadsgf8912345kl;hjajkl;       `123890",
    "\0\0-3;jsdf"
    ]

def MakeReadableString(val):
  printable = string.digits + string.letters + string.punctuation + ' ' + "\t"
  out = []
  for c in val:
    if c in printable:
      out.append("   %c " % c)
    else:
      out.append("0x%02x " % ord(c))
  return ''.join(out)

def main():
  h = Huffman(request_freq_table)
  for s in test_data:
    print " encoding: ", s
    sp = [ord(c) for c in s]
    e_result = h.Encode(sp, False)
    print "      e_result: ", PrintAsBits(e_result)
    d_result = ''.join(h.Decode(e_result[0], False, e_result[1]))
    if d_result != s:
      print "difference found: ", d_result, " ", s
    else:
      print "It worked: ", s
    print
  #bb = BitBucket()
  #bb.StoreBits(([0xff],7))
  #bb.StoreBits(([0x00],5))
  #bb.StoreBits(([0xff],5))
  #bb.StoreBits(([0x00],6))
  #bb.StoreBits(([0xff],5))
  #bb.StoreBits(([0x00],5))
  #bb.StoreBits(([0xff],6))
  #bb.StoreBits(([0x00],5))
  #bb.StoreBits(([0xff],8))
  #print PrintAsBits(bb.GetAllBits())

main()

