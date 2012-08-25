
def PrintAsBits(output_and_bits):
  (output, bits) = output_and_bits
  retval = []
  last_byte = output[-1]
  for c in output[:-1]:
    retval.append('|')
    retval.append("{0:08b}".format(c))
  if (bits % 8) != 0:
    retval.append('|')
    retval.append("{0:08b}".format(last_byte)[0:(bits % 8)])
  else:
    retval.append('|')
    retval.append("{0:08b}".format(last_byte))
  retval.extend([' [%d]' % bits])
  return ''.join(retval)

class BitBucket:
  def __init__(self):
    self.Clear()

  def Clear(self):
    self.output = [0]
    self.out_byte = 0
    self.out_boff = 0
    self.idx_byte = 0
    self.idx_boff = 0

  def StoreBits(self, input):
    (inp_bytes, inp_bits) = input
    leftover_bits = inp_bits - (8*(len(inp_bytes)-1))
    out_byte = self.output.pop()
    if self.out_boff == 0:
      self.output.extend(inp_bytes)
      if leftover_bits:
        self.out_boff = leftover_bits
        out_byte = self.output.pop() & ~(255 >> self.out_boff)
    else:
      # We know there is a non-zero bit offset if we're below here.
      bits_left_in_byte = 8 - self.out_boff
      for c in inp_bytes[:-1]:
        out_byte |= c >> self.out_boff
        self.output.append(out_byte)
        out_byte = (c << bits_left_in_byte) & 255
      c = inp_bytes[-1] & ~(255 >> leftover_bits)
      if leftover_bits < bits_left_in_byte:
        out_byte |= c >> self.out_boff
        self.out_boff = self.out_boff + leftover_bits
      else:
        out_byte |= c >> self.out_boff
        self.output.append(out_byte)
        out_byte = (c << bits_left_in_byte) & 255
        self.out_boff = (self.out_boff + leftover_bits) % 8
    self.output.append(out_byte)

  def GetAllBits(self):
    return (self.output, self.NumBits())

  def NumBits(self):
    return 8 * (len(self.output) - 1) + self.out_boff

  def GetBits(self, num_bits):
    if num_bits > self.NumBits() - (8*self.idx_byte + self.idx_boff):
      raise StandardError()

    retval = []
    bits_left = num_bits
    if self.idx_boff == 0:
      while bits_left >= 8:
        retval.append(self.output[self.idx_byte])
        self.idx_byte += 1
        bits_left -= 8
      if bits_left:
        # get bits_left left bits
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
          cur_byte |=  (self.output[self.idx_byte] >> ( 8 - self.idx_boff))
          retval.append(cur_byte)
          bits_left -= 8
        else:
          bits_to_consume = min(min(8 - cur_boff, 8 - self.idx_boff),
                                num_bits)
          c = self.output[self.idx_byte]
          c <<= self.idx_boff
          c &= 255
          cur_byte |= (c >> cur_boff) & ~(255 >> bits_to_consume)
          bits_left -= bits_to_consume
          cur_boff += bits_to_consume
          self.idx_boff += bits_to_consume
          if cur_boff >= 8:
            retval.append(cur_byte)
            cur_byte = 0
            cur_boff %= 8
          if self.idx_boff >= 8:
            self.idx_byte += 1
            self.idx_boff %= 8
      if cur_boff:
        retval.append(cur_byte)
    return (retval, num_bits)

  def __str__(self):
    return PrintAsBits((self.output, self.out_boff))

  def __repr__(self):
    return self.__str__()


