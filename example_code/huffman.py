# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import heapq
from collections import deque
from bit_bucket import BitBucket
from common_utils import FormatAsBits
import string

class Huffman(object):
  """
  This class takes in a frequency table, constructs a huffman code, and
  then allows for encoding and decoding of strings.
  """
  def __init__(self, freq_table):
    self.code_tree = None
    self.code_table = []
    self.BuildCodeTree(freq_table)
    self.BuildCodeTable(self.code_tree)
    #print self.FormatCodeTable()

  def BuildCodeTree(self, freq_table):
    """ Given a frequency table (a list of tuples of (symbol, frequency-count)),
    constructs the huffman tree which is to say a tree where the root of any
    subtree is the sum of the weight of its children, and where subtrees are
    constructed by examining the node with the smallest weight """
    def MN(x):
      if isinstance(x, int):
        return x
      return ord(x)
    if len(freq_table) < 2:
      # that'd be stupid...
      raise StandardError()
    # freq_table is (symbol, count)
    # code_tree is [freq, symbol, children]
    leaves = deque(sorted([ [frq, MN(sym), []] for (sym, frq) in freq_table]))
    internals = deque()
    while len(leaves) + len(internals) > 1:
      children = []
      while len(children) < 2:
        if leaves and internals:
          if leaves[0][0] <= internals[0][0]:
            children.append(leaves.popleft())
          else:
            children.append(internals.popleft())
        elif leaves:
          children.append(leaves.popleft())
        else:
          children.append(internals.popleft())
      internals.append([(children[0][0] + children[1][0]), None, children])
    if len(leaves):
      raise StandardError()
    self.code_tree = internals.pop()

  def BinaryStringToBREP(self, binary_string):
    """
    Given a string containing '1's and '0's, construct the binary
    representation which is (list-of-bytes, number-of-bits-as-int)
    """
    output = []
    bitlen = len(binary_string)
    if not bitlen:
      raise StandardError()
    index = 0
    while index + 8 < bitlen:
      output.append(int(binary_string[index:index+8],2))
      index += 8
    if index != bitlen:
      final = binary_string[index:bitlen]
      for i in xrange(8 - (bitlen - index)):
        final += '0'
      output.append(int(final, 2))
    return (output, bitlen)

  def BuildCodeTable(self, code_tree):
    """ Given a code-tree as constructed in BuildCodeTree,
    construct a table useful or doing (realtively) quick
    encoding of a plaintext symbol into into its huffman encoding.
    The table is ordered in the order of symbols, and contains
    the binary representation of the huffman encoding for each symbol.
    """
    queue = deque([(code_tree, '')])
    pre_table = []
    while queue:
      (tree, path_so_far) = queue.popleft()
      (freq, name, children) = tree
      if name != None:
        if not isinstance(name, int):
          pre_table.append( (ord(name), str(path_so_far)) )
        else:
          pre_table.append( (    name , str(path_so_far)) )
      if children:
        queue.appendleft( (children[0], str(path_so_far + '0')) )
        queue.appendleft( (children[1], str(path_so_far + '1')) )
    pre_table = sorted(pre_table, key=lambda x: x[0])
    for i in xrange(len(pre_table)):
      (name, binary_string) = pre_table[i]
      if i != name:
        raise StandardError()
      self.code_table.append(self.BinaryStringToBREP(binary_string))

  def EncodeToBB(self, bb, text, include_eof):
    """
    Given a BitBucket 'bb', and a string 'text', encode the string using the
    pre-computed huffman codings and store them into the BitBucket. if
    'include_eof' is true, then an EFO will also be encoded at the end.
    """
    for c in text:
      prelen = bb.GetAllBits()[1]
      prestr = str(bb)
      bb.StoreBits(self.code_table[c])
      if bb.GetAllBits()[1] == prelen:
        raise StandardError()
    if include_eof:
      bb.StoreBits(self.code_table[256])

  def Encode(self, text, include_eof):
    """
    Encodes 'text' using the pre-computed huffman coding, and returns it as
    a tuple of (list-of-bytes, number-of-bits-as-int). If 'include_eof' is true,
    then an EOF will be encoded at the end.
    """
    bb = BitBucket()
    self.EncodeToBB(bb, text, include_eof)
    return bb.GetAllBits()

  def DecodeFromBB(self, bb, includes_eof, bits_to_decode):
    """
    Decodes the huffman-encoded text stored in the BitBucket 'bb back into a
    plaintext string.  If 'includes_eof' is true, then it is assumed that the
    string was encoded with an EOF.  If bits_to_decode > 0, then 'includes_eof'
    is allowed to be false, and that many bits will be consumed from the
    BitBucket
    """
    output = []
    total_bits = 0
    if not includes_eof and bits_to_decode <= 0:
      # That can't work.
      raise StandardError()
    if bits_to_decode <= 0:
      bits_to_decode = -1
    while bits_to_decode < 0 or total_bits < bits_to_decode:
      root = self.code_tree
      while root[1] is None:
        bit = bb.GetBits(1)[0][0] >> 7
        root = root[2][bit]
        total_bits += 1
      if includes_eof and root[1] is not None and root[1] == 256:
        break
      elif root[1] is not None:
        output.append(root[1])
      else:
        raise StandardError()
    if bits_to_decode > 0 and total_bits < bits_to_decode:
      bb.GetBits(bits_to_decode - total_bits)
    return output

  def Decode(self, text, includes_eof, bits_to_decode):
    """
    This shouldn't be used (use the DecodeFromBB version instead).
    Decodes a plaintext string from the huffman-encoded string 'text'
    """
    output = []
    if not text:
      return output
    # this is the very very slow way to decode.
    c = text[0]
    bit_index = 0
    chr_index = 0
    if bits_to_decode <= 0:
      bits_to_decode = len(text) * 8
    total_bits = 0
    while total_bits < bits_to_decode:
      root = self.code_tree
      while root[1] is None:
        try:
          c = text[chr_index]
        except:
          print (total_bits, bits_to_decode), (chr_index, len(text)), repr(text)
          raise
        bit = (c >> (7 - bit_index)) & 0x1
        root = root[2][bit]
        bit_index += 1
        total_bits += 1
        if bit_index >= 8:
          bit_index = 0
          chr_index += 1
      if includes_eof and root[1] is not None and ord(root[1]) == 256:
        break
      elif root[1] is not None:
        output.append(root[1])
      else:
        raise StandardError()
    return output

  def FormatCodeTable(self):
    """
    Makes a formatted version of the code table, useful for debugging
    """
    printable = string.digits + string.letters + string.punctuation + ' ' + "\t"
    x = sorted([(i,FormatAsBits( self.code_table[i]))
                for i in xrange(len(self.code_table))])
    retval = []
    for entry in x:
      code, description = entry
      readable_code = ""
      if code < 256 and chr(code) in printable and chr(code) != '\t':
        readable_code = "'%c'" % chr(code)
      while len(readable_code) < 5:
          readable_code = " " + readable_code
      retval.append('%s (%3d): %s' % (readable_code, code, description))
    return '\n'.join(retval)

  def __repr__(self):
    output = ['[']
    for elem in self.code_table.iteritems():
      output.append(repr(elem))
      output.append(', ')
    output.append(']')
    return ''.join(output)

