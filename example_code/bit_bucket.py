# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from common_utils import FormatAsBits
from common_utils import StrToList
import sys
import struct

class BitBucket:
  """
  This class allows for bit-level manipulations of a list of bits.
  In particular, it allows for the storage of bits (or sets of bits), and
  it allows for the fetching of those stored bits (effectively in a FIFO manner)
  """
  def __init__(self):
    self.Clear()

  def Clear(self):
    """
    Clears out all data and resets the BitBucket to like-new state
    """
    self.output = []
    self.out_byte = 0
    self.out_boff = 0
    self.idx_byte = 0
    self.idx_boff = 0

  def AdvanceToByteBoundary(self):
    """
    Inserts enough '0's to ensure that the number of bits stored % 8 == 0
    """
    bits_to_advance = (8 - self.idx_boff) % 8
    if bits_to_advance:
      self.idx_boff += bits_to_advance
      self.idx_boff %= 8
      self.idx_byte += 1

  def StoreBit(self, bit):
    """
    Stores a single bit.
    """
    if bit:
      bit = 1
    else:
      bit = 0
    self.StoreBits( ([bit << 7], 1) )

  def StoreBits8(self, val):
    """
    Stores the 8 least-significant-bits from val
    """
    tmp_val = struct.pack(">B", val)
    self.StoreBits( (StrToList(tmp_val), 8))

  def StoreBits16(self, val):
    """
    Stores the 16 least-significant-bits from val in network order (big endian)
    """
    tmp_val = struct.pack(">H", val)
    self.StoreBits( (StrToList(tmp_val), 16))

  def StoreBits32(self, val):
    """
    Stores the 32 least-significant-bits from val in network order (big endian)
    """
    tmp_val = struct.pack(">L", val)
    self.StoreBits( (StrToList(tmp_val), 32))

  def StoreBits(self, input_tuple):
    """
    (inp_bytes, inp_bits) = input_tuple
    Stores inp_bits from inp_bytes. When inp_bits < len(inp_bytes)*8, the
    most-significant-bits (this is opposite the other StoreBits) of the last
    element of inp_bytes are used.
    """
    (inp_bytes, inp_bits) = input_tuple
    old_out_boff = self.out_boff
    if not inp_bytes:
      return
    if inp_bits % 8:
      leftover_bits = inp_bits % 8
    else:
      leftover_bits = 8
    if self.out_boff == 0:
      self.output.extend(inp_bytes)
      if not type(inp_bytes[0]) == int:
        print "type(inp_bytes[0]) == ", type(inp_bytes[0])
        print repr(input)
        raise StandardError()
      self.output[-1] &= ~(255 >> leftover_bits)
      self.out_boff = leftover_bits % 8
    else:
      # We know there is a non-zero bit offset if we're below here.
      # This also implies there MUST be a byte in output already.
      bits_left_in_byte = 8 - self.out_boff
      for c in inp_bytes:
        self.output[-1] |= c >> self.out_boff
        self.output.append(0)
        self.output[-1] = (c << bits_left_in_byte) & 255
      c = inp_bytes[-1]
      if self.out_boff + leftover_bits <= 8:
        self.output.pop()
        c = inp_bytes[-1]
        self.output[-1] |= c >> self.out_boff
      self.out_boff = (self.out_boff + leftover_bits) % 8
      if self.out_boff != 0:
        self.output[-1] &= ~(255 >> self.out_boff)
    if self.out_boff != (old_out_boff + inp_bits) % 8:
      raise StandardError()

  def GetAllBits(self):
    """ Returns a tuple containing (list-of-bytes, number-of-bits)
    When number-of-bits % 8 != 0, the last byte in list-of-bytes
    will have the remaining bits (number-of-bits % 8) stored
    from the most-significant bit onward towards the least-significant bit
    """
    return (self.output, self.NumBits())

  def NumBits(self):
    """
    Returns the number of bits stored into this BitBucket
    """
    num_bits = 8*len(self.output)
    if self.out_boff % 8:
      num_bits -= 8
      num_bits += self.out_boff
    if num_bits < 0:
      print "What the..."
    return num_bits

  def BytesOfStorage(self):
    """
    Returns the number of bytes necessary to hold all of the bits which have
    been stored into this BitBucket
    """
    return (self.NumBits() + 7) / 8

  def BitsRemaining(self):
    """
    Returns the number of unread/unconsumed bits.
    """
    return self.NumBits() - (8*self.idx_byte + self.idx_boff) - 1

  def AllConsumed(self):
    """ Returns true if all stored bits were consumed, else returns false"""
    return self.NumBits() <= (8*self.idx_byte + self.idx_boff)

  def GetBits8(self):
    """
    Gets the next 8 unconsumed bits from the BitBucket and returns that as
    an int
    """
    raw_data = self.GetBits(8)[0]
    arg = "%c%c%c%c" % (0,0, 0, raw_data[0])
    return struct.unpack(">L", arg)[0]

  def GetBits16(self):
    """
    Gets the next 16 unconsumed bits from the BitBucket and returns that as an
    int
    """
    raw_data = self.GetBits(16)[0]
    arg = "%c%c%c%c" % (0,0, raw_data[0], raw_data[1])
    return struct.unpack(">L", arg)[0]

  def GetBits32(self):
    """
    Gets the next 32 unconsumed bits from the BitBucket and returns that as an
    int
    """
    raw_data = self.GetBits(32)[0]
    arg = "%c%c%c%c" % (raw_data[0], raw_data[1], raw_data[2], raw_data[3])
    return struct.unpack(">L", arg)[0]

  def GetBits(self, num_bits):
    """
    Gets the specified number of unconsumed bits and returns it as a list of
    ints (all of which are < 256)
    """
    old_idx_boff = self.idx_boff

    bits_available = self.NumBits() - (8*self.idx_byte + self.idx_boff)
    if num_bits > bits_available:
      print "num_bits: %d but bits_available: %d" % (num_bits, bits_available)
      raise StandardError()
    retval = []
    bits_left = num_bits
    if self.idx_boff == 0:
      while bits_left >= 8:
        retval.append(self.output[self.idx_byte])
        self.idx_byte += 1
        bits_left -= 8
      if bits_left:
        retval.append( ~(255 >> bits_left) & self.output[self.idx_byte])
        self.idx_boff += bits_left
        self.idx_boff %= 8
        bits_left = 0
    else:
      # We know there is a non-zero bit offset if we're below here.
      cur_byte = 0
      cur_boff = 0
      lob = len(self.output)
      while bits_left > 0:
        if bits_left >= 8 and lob > self.idx_byte:
          cur_byte =  255 & (self.output[self.idx_byte] << self.idx_boff)
          self.idx_byte += 1
          cur_byte |=  (self.output[self.idx_byte] >> (8 - self.idx_boff))
          retval.append(cur_byte)
          cur_byte = 0
          bits_left -= 8
        else:
          bits_to_consume = min(min(8 - cur_boff, 8 - self.idx_boff),
                                bits_left)

          c = self.output[self.idx_byte]
          c <<= self.idx_boff
          c &= 255
          cur_byte |= (c & ~(255 >> (bits_to_consume))) >> cur_boff
          bits_left -= bits_to_consume
          cur_boff += bits_to_consume
          self.idx_boff += bits_to_consume
          if cur_boff >= 8:
            retval.append(cur_byte)
            cur_byte = 0
            cur_boff -= 8
          if self.idx_boff >= 8:
            self.idx_byte += 1
            self.idx_boff -= 8
            if self.idx_boff >= 8:
              raise StandardError()
      if cur_boff:
        retval.append(cur_byte)
    if (old_idx_boff + num_bits) % 8 != self.idx_boff:
      print "old_idx_boff(%d) + num_bits(%d) != self.idx_boff(%d) " % (
          old_idx_boff, num_bits, self.idx_boff)
      print "retval: ", (retval, num_bits)
      raise StandardError()
    return (retval, num_bits)

  def DebugFormat(self):
    """
    Prints out (to stdout) a representation intended to help with debugging
    """
    print FormatAsBits((self.output, self.out_boff))
    for i in xrange(self.idx_byte*8 + self.idx_boff - 1):
      if not i % 8:
        sys.stdout.write("|")
      sys.stdout.write("-")
    print "^"

  def __repr__(self):
    return FormatAsBits((self.output, self.out_boff))
