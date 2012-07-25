#!/usr/bin/python
import zlib
import string
import sys
import array
import struct

def MakeERef(key, value):
  op = {'opcode': 'ERef',
        'key_str_len': len(key),
        'key_str': key,
        'val_str_len': len(value),
        'val_str': value}
  return op

def RealMakeERef(key, val):
  key_len = len(key)
  val_len = len(val)
  if len(key) > 16777215:
    raise StandardError()
  if len(val) > 16777215:
    raise StandardError()
  retval = []
  a = 0
  b = ((key_len & 0xff0000) >> 16)
  c = ((key_len & 0x00ff00) >> 8)
  d = ((key_len & 0x0000ff) >> 0)
  e = key
  f = ((val_len & 0xff0000) >> 16)
  g = ((val_len & 0x00ff00) >> 8)
  h = ((val_len & 0x0000ff) >> 0)
  i = val
  return struct.pack("!BBBB%dsBBB%ds" % (key_len, val_len), a,b,c,d,e,f,g,h,i)

def MakeTaCo(is_key, dict_level, index, truncate_to, str_val):
  op = {'opcode': 'TaCo',
        'k': is_key,
        'dict_level': dict_level,
        'index': index,
        'truncate_to': truncate_to,
        'str_len': len(str_val) - truncate_to,
        'str_val': str_val[truncate_to:]}
  return op

def RealMakeTaCo(is_key, dict_level, index, truncate_to, str_val):
  str_len = len(str_val)
  k = 0
  if is_key:
    k = 1
  l = 0
  if dict_level == 'c':
    l = 1
  if str_len > 16777215:
    raise StandardError()
  if truncate_to > 16777215:
    raise StandardError()
  if index > 65535:
    raise StandardError()
  truncto = truncate_to
  retval = []
  a = (0x80 | (k << 5) | (l << 4))
  b = ((truncto & 0xff0000) >> 16)
  c = ((truncto & 0x00ff00) >> 8)
  d = ((truncto & 0x0000ff) >> 0)
  e = ((index & 0xff00) >> 8)
  f = ((index & 0x00ff) >> 0)
  g = ((str_len & 0xff0000) >> 16)
  h = ((str_len & 0x00ff00) >> 8)
  i = ((str_len & 0x0000ff) >> 0)
  j = str_val
  return struct.pack("!BBBBBBBBB%ds" % str_len, a,b,c,d,e,f,g,h,i,j)

def MakeRemove(dict_level, index):
  return MakeStore(0, dict_level, index, '')

def RealMakeRemove(dict_level, index):
  return RealMakeStore(0, dict_level, index, '')

def MakeStore(is_key, dict_level, index, str_val):
  op = {'opcode': 'Store',
        'k': is_key,
        'dict_level': dict_level,
        'index': index,
        'str_len': len(str_val),
        'str_val': str_val}
  return op

def RealMakeStore(is_key, dict_level, index, str_val):
  str_len = len(str_val)
  k = 0
  if is_key:
    k = 1
  l = 0
  if dict_level == 'c':
    l = 1
  if str_len > 16777215:
    raise StandardError()
  if index > 65535:
    raise StandardError()
  a = (0x40 | (k << 5) | (l << 4))
  b = ((index & 0xff00) >> 8)
  c = ((index & 0x00ff) >> 0)
  d = ((str_len & 0xff0000) >> 16)
  e = ((str_len & 0x00ff00) >> 8)
  f = ((str_len & 0x0000ff) >> 0)
  return struct.pack("!BBBBBB%ds" % str_len, a,b,c,d,e,f, str_val)

def OpSize(op):
  if op['opcode'] == 'Store':
    return 1+2+3+ op['str_len']
  if op['opcode'] == 'TaCo':
    return 1+2+3+3+ op['str_len']
  if op['opcode'] == 'ERef':
    return 1+3+3+op['key_str_len'] + op['val_str_len']
  raise StandardError()

def OpToRealOp(op):
  if op['opcode'] == 'Store':
    return RealMakeStore(op['k'], op['dict_level'], op['index'], op['str_val'])
  if op['opcode'] == 'TaCo':
    return RealMakeTaCo(op['k'], op['dict_level'], op['index'],
        op['truncate_to'],op['str_val'])
  if op['opcode'] == 'ERef':
    return RealMakeERef(op['key'], op['value'])
  raise StandardError()

def PrintOp(op):
  order = ['opcode', 'k', 'dict_level', 'index', 'truncate_to', 'str_len',
      'str_val', 'key_str_len', 'key_str', 'val_str_len', 'val_str']
  outp = ['{']
  inp = []
  for key in order:
    if key in op and key is not 'opcode':
      inp.append("'%s': %s" % (key, repr(op[key])))
    if key in op and key is 'opcode':
      inp.append(("'%s': " % key).ljust(8) + repr(op[key]))
  for (key, val) in op.iteritems():
    if key in order:
      continue
    inp.append("'%s': " % key, " ", repr(op[key]))
  outp.append(', '.join(inp))
  outp.append('}')
  print ''.join(outp)

def NextIndex(dict):
  indices = [idx for (idx, val) in dict.iteritems()]
  if len(indices) == 0:
    return 1
  indices.sort()
  prev_idx = 0
  idx = 0
  for idx in indices:
    if idx - prev_idx > 1:
      # jumped up by more than one.
      #print "ni: ", prev_idx + 1
      return prev_idx + 1
    prev_idx = idx
  #print "ni: ", idx + 1
  return idx + 1

def CommonPrefixLen(str1, str2):
  prefix_match_len = 0
  for i in xrange(0, min(len(str1),len(str2))):
    if str1[i] != str2[i]:
      break;
    prefix_match_len += 1
  return prefix_match_len

def KeyIndexInDict(dict, key):
  for (index, dict_entry) in dict.iteritems():
    if dict_entry[1] == key:
      return index
  return -1

class CompressorDecompressor:
  def __init__(self):
    self.compressor = zlib.compressobj()
    self.decompressor = zlib.decompressobj()
    self.generation = 0
    self.connection_dict = {}
    self.stream_group_dicts = {0: {}}

    self.connection_headers = [":method", ":version", "user-agent" ]
    self.limits = {'TotalHeaderStorageSize': 16*1024,
                   'MaxHeaderGroups': 1,
                   'MaxEntriesInTable': 64}
    self.total_storage = 0

  def FindAppropriateEntry(self, key, stream_group):
    dict = self.connection_dict
    dict_level = 'c'
    key_idx = KeyIndexInDict(dict, key)
    if key_idx == -1:  # if not in connection headers, try stream-group
      dict = self.stream_group_dicts[stream_group]
      dict_level = 'g'
      key_idx = KeyIndexInDict(dict, key)
      if key_idx == -1: # also not in stream-group. Add to appropriate level.
        if key in self.connection_headers:
          dict = self.connection_dict
          dict_level = 'c'
        # otherwise it'll get added to the group level
    return (dict, dict_level, key_idx)

  def MakeOps(self, key, value, stream_group):
    ops = []
    (dict, dict_level, key_idx) = self.FindAppropriateEntry(key, stream_group)

    if key_idx == -1:  # store a new one.
      key_idx = NextIndex(dict)
      ops.extend([MakeStore(1, dict_level, key_idx, key),
                  MakeStore(0, dict_level, key_idx, value)])
    else:
      dict_value = ''
      if key_idx in dict:
        dict_value = dict[key_idx][0]
      prefix_match_len = CommonPrefixLen(dict_value, value)
      if prefix_match_len == len(value):
        self.Touch(dict, key_idx)
      elif prefix_match_len > 3:  # 3 == trunc_to len
        ops.append(MakeTaCo(0, dict_level, key_idx, prefix_match_len, value))
      else:
        ops.append(MakeStore(0, dict_level, key_idx, value))

    for op in ops: # gotta keep our state up-to-date.
      #print "executing: ", PrintOp(op)
      self.ExecuteOp(op, stream_group, {})
    return ops


  def GenerateAllHeaders(self, stream_group, ephemereal_headers):
    headers = {}
    for (idx, item) in self.connection_dict.iteritems():
      headers[item[1]] = item[0]
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      headers[item[1]] = item[0]
      for (key, value) in ephemereal_headers.iteritems():
        headers[key] = value
    return headers

  def Touch(self, dict, index):
    dict[index][2] = self.generation

  def NotCurrent(self, item):
    return item[2] != self.generation

  def ModifyDictEntry(self, dict, index, is_key, str_val):
    if index not in dict:
      dict[index] = ['', '', 0]
    self.total_storage -= len(dict[index][is_key])
    if str_val == '':
      self.total_storage -= len(dict[index][not is_key])
      del dict[index]
      return
    self.total_storage += len(str_val)
    dict[index][is_key] = str_val
    self.Touch(dict, index);
    if dict[index][1] == '':
      raise StandardError()
    #print self.total_storage

  def ExecuteOps(self, ops, stream_group, ephemereal_headers):
    for op in ops:
      self.ExecuteOp(op, stream_group, ephemereal_headers)

  def ExecuteOp(self, op, stream_group, ephemereal_headers):
    opcode = op['opcode']
    if opcode == 'ERef':
      key_str_len = op['key_str_len']
      key_str = op['key_str']
      val_str_len = op['val_str_len']
      val_str = op['val_str']
      if key_str_len == 0 or val_str_len == 0:
        raise StandardError()
      if key_str in ephemereal_headers:
        raise StandardError()
      ephemereal_headers[key_str] = val_str
      return

    dict = self.connection_dict
    dict_level = op['dict_level']
    is_key = op['k']
    index = op['index']
    str_val = op['str_val']
    str_len = op['str_len']

    if dict_level != 'c':
      dict = self.stream_group_dicts[stream_group]
    if opcode == 'Store':
      self.ModifyDictEntry(dict, index, is_key, str_val)
    elif opcode == 'TaCo':
      truncate_to = op['truncate_to']
      if str_len == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key,
          dict[index][is_key][:truncate_to] + str_val)
    else:
      # unknown opcode
      raise StandardError()

  def MakeRemovalOps(self, stream_group):
    remove_ops = []
    for (idx, item) in self.connection_dict.iteritems():
      if self.NotCurrent(item):
        remove_ops.append(MakeRemove('c', idx))
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      if self.NotCurrent(item):
        remove_ops.append(MakeRemove('g', idx))
    for op in remove_ops:
      self.ExecuteOp(op, stream_group, {})
    return remove_ops

  # returns a list of operations
  def Compress(self, headers, stream_group):
    self.generation += 1
    ops = []
    for (key, value) in headers.iteritems():
      if not stream_group in self.stream_group_dicts:
        self.stream_group_dict[stream_group] = {}
      ops.extend(self.MakeOps(key, value, stream_group))
    remove_ops = self.MakeRemovalOps(stream_group)
    return remove_ops + ops

def main():
  requests = [ {':method': "get",
                ':path': '/index.html',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
                'accept-encoding': 'sdch, bzip, compress',
                ':host': 'www.foo.com',
                'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
                'date': 'Wed Jul 18 11:50:43 2012'},
               {':method': "get",
                ':path': '/index.js',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
                'accept-encoding': 'sdch, bzip, compress',
                ':host': 'www.foo.com',
                'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
                'date': 'Wed Jul 18 11:50:44 2012'},
               {':method': "get",
                ':path': '/index.css',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
                'accept-encoding': 'sdch, bzip, compress',
                ':host': 'www.foo.com',
                'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;FOOBLA',
                'date': 'Wed Jul 18 11:50:45 2012'},
               {':method': "get",
                ':path': '/generate_foo.html',
                ':version': 'HTTP/1.1',
                ':host': 'www.foo.com',
                'date': 'Wed Jul 18 11:50:45 2012'},
               {':method': "get",
                ':path': '/index.css',
                ':version': 'HTTP/1.1',
                'user-agent': 'blah blah browser version blah blah',
                'accept-encoding': 'sdch, bzip, compress',
                ':host': 'www.foo.com',
                'cookie': 'SOMELONGSTRINGTHATISMOSTLYOPAQUE;BLAJBLA',
                'date': 'Wed Jul 18 11:50:46 2012'},
               ]
  frame_list = []
  compressor = CompressorDecompressor()
  decompressor = CompressorDecompressor()
  for request in requests:
    print "Compressing: ", request
    frame_list.append(compressor.Compress(request, 0))
  print
  print "Opcodes: "
  for ops in frame_list:
    frame_size = 11  # that is the size of the header's frame preamble
    for op in ops:
      PrintOp(op)
      frame_size += OpSize(op)
      # realop = OpToRealOp(op)
      # sys.stdout.write(str.format("\\0b{0:08b}" , ord(realop[0])))
      # for i in xrange(1,len(realop)):
      #   sys.stdout.write("\\%s" % hex(ord(realop[i])))
      # print
      # print
    print
  for ops in frame_list:
    decompressor.ExecuteOps(ops, 0, {})
    print "Decompressed: ", decompressor.GenerateAllHeaders(0, {})

main()



