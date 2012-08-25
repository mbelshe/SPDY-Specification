import heapq
from collections import deque

class Huffman:
  def __init__(self, freq_table):
    self.code_tree = None
    self.code_table = []
    self.BuildCodeTree(freq_table)
    self.BuildCodeTable(self.code_tree)

  def BuildCodeTree(self, freq_table):
    # freq, name, children
    heap = [[freq_table[i], i, []] for i in xrange(len(freq_table))]
    heapq.heapify(heap)
    while heap:
      smallest = heapq.heappop(heap)
      try:
        next_smallest = heapq.heappop(heap)
        # freq, name, [left, right]
        combined = [(smallest[0] + next_smallest[0]), None,
                    [smallest, next_smallest]]
        heapq.heappush(heap, combined)
      except IndexError:
        self.code_tree = smallest
        break

  def BinaryStringToBREP(self, binary_string):
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

  def BuildCodeTable(self, code_tree, path_so_far=''):
    queue = deque([(code_tree, '')])
    pre_table = []
    while queue:
      (tree, path_so_far) = queue.popleft()
      (freq, name, children) = tree
      if name is not None:
        pre_table.append( (name, path_so_far) )
      if children:
        queue.append( (children[0], path_so_far + '0') )
        queue.append( (children[1], path_so_far + '1') )
    pre_table = sorted(pre_table, key=lambda x: x[0])
    for i in xrange(len(pre_table)):
      (name, binary_string) = pre_table[i]
      if i != name:
        print "i (", i, ") != pre_table[i] (", name, ")"
        raise StandardError()
      self.code_table.append(self.BinaryStringToBREP(binary_string))

  def Encode(self, text, include_eof):
    bb = BitBucket()
    for c in text:
      bb.StoreBits(self.code_table[c])
    if include_eof:
      bb.StoreBits(self.code_table[128])
    return bb.GetAllBits()

  def Decode(self, text, includes_eof, bits_to_decode):
    output = []
    if not text:
      return output
    # this is the very very slow way to decode.
    root = self.code_tree
    c = ord(text[0])
    bit_index = 0
    chr_index = 1
    total_bits = 0
    while bits_to_decode == -1 or total_bits < bits_to_decode:
      while not root[3]:
        bit = c & (0x1 << bit_index)
        ++bit_index
        ++total_bits
        if bit_index >= 8:
          bit_index = 0
          chr_index += 1
          c = ord(text[chr_index])
        root = root[2][bit]
      if includes_eof and root[3] == 128:
        break
      elif root[3]:
        output.append(root[3])
    return output

  def FormatCodeTable(self):
    x = sorted([(chr(i), self.code_table[i]) for i in xrange(len(self.code_table))],
      key=lambda x: (x[1][1], x[1][0]))
    return repr(x)

  def __str__(self):
    output = ['[']
    for elem in self.code_table.iteritems():
      output.append(repr(elem))
      output.append(', ')
    output.append(']')
    return ''.join(output)

  def __repr__(self):
    return self.__str__()

