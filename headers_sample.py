#!/usr/bin/python
import zlib
import string
import sys
import array
import struct

def IntTo3B(val):
  if val > 16777215:
    raise StandardError()
  return struct.pack("!L", val)[1:]

def IntTo2B(val):
  if val > 65535:
    raise StandardError()
  return struct.pack("!L", val)[2:]

def B3ToInt(val):
  arg = "%c%c%c%c" % (0,val[0],val[1],val[2])
  return struct.unpack("!L", arg)[0]

def B2ToInt(val):
  arg = "%c%c%c%c" % (0,0,val[0],val[1])
  return struct.unpack("!L", arg)[0]

def ListToStr(val):
  return ''.join(["%c" % c for c in val])

def RealMakeFB(opcode, k, l):
  if k:
    k = 1
  else:
    k = 0
  if l == 1 or l == 'c':
    l = 1
  else:
    l = 0
  if opcode == 'ERef':
    opcode = 0
  elif opcode == 'Store':
    opcode = 0x1
  elif opcode == 'TaCo':
    opcode = 0x2
  elif opcode == 'KVSto':
    opcode = 0x3
  elif opcode == 'Rem':
    opcode = 0x4
  return struct.pack("!B", opcode << 5 | (k << 4) | (l << 3))

def ParseFB(byte):
  return (((byte >> 5) & 0x7), ((byte >> 4) & 0x1), ((byte >> 3) & 0x1))


def RealMakeERef(key, val):
  retval = []
  retval.append(RealMakeFB('ERef',0,0))
  retval.append(IntTo3B(len(key)))
  retval.append(key)
  retval.append(IntTo3B(len(val)))
  retval.append(val)
  return ''.join(retval)

def RealMakeTaCo(is_key, dict_level, index, truncate_to, str_val):
  retval = []
  retval.append(RealMakeFB('TaCo', is_key, dict_level))
  retval.append(IntTo3B(truncate_to))
  retval.append(IntTo2B(index))
  retval.append(IntTo3B(len(str_val)))
  retval.append(str_val)
  return ''.join(retval)

def RealMakeRem(dict_level, index):
  retval = []
  retval.append(RealMakeFB('Rem', 0, dict_level))
  retval.append(IntTo2B(index))
  return ''.join(retval)

def RealMakeStore(is_key, dict_level, index, str_val):
  retval = []
  retval.append(RealMakeFB('Store', is_key, dict_level))
  retval.append(IntTo2B(index))
  retval.append(IntTo3B(len(str_val)))
  retval.append(str_val)
  return ''.join(retval)

def RealMakeKVSto(dict_level, index, key, val):
  retval = []
  retval.append(RealMakeFB('KVSto', 0, dict_level))
  retval.append(IntTo2B(index))
  retval.append(IntTo3B(len(key)))
  retval.append(key)
  retval.append(IntTo3B(len(val)))
  retval.append(val)
  return ''.join(retval)

def MakeERef(key, value):
  op = {'opcode': 'ERef',
        'key_str_len': len(key),
        'key_str': key,
        'val_str_len': len(value),
        'val_str': value}
  return op

def MakeTaCo(is_key, dict_level, index, truncate_to, str_val):
  op = {'opcode': 'TaCo',
        'k': is_key,
        'dict_level': dict_level,
        'index': index,
        'truncate_to': truncate_to,
        'str_len': len(str_val),
        'str_val': str_val}
  return op

def MakeRem(dict_level, index):
  op = {'opcode': 'Rem',
      'dict_level': dict_level,
      'index': index}
  return op

def MakeStore(is_key, dict_level, index, str_val):
  op = {'opcode': 'Store',
        'k': is_key,
        'dict_level': dict_level,
        'index': index,
        'str_len': len(str_val),
        'str_val': str_val}
  return op

def MakeKVSto(dict_level, index, key, val):
  op = {'opcode': 'KVSto',
        'dict_level': dict_level,
        'index': index,
        'key_len': len(key),
        'key_str': key,
        'val_len': len(val),
        'val_str': val}
  return op


def OpToRealOp(op):
  if op['opcode'] == 'Store':
    return RealMakeStore(op['k'], op['dict_level'], op['index'], op['str_val'])
  if op['opcode'] == 'TaCo':
    return RealMakeTaCo(op['k'], op['dict_level'], op['index'],
        op['truncate_to'],op['str_val'][op['truncate_to']:])
  if op['opcode'] == 'ERef':
    return RealMakeERef(op['key_str'], op['val_str'])
  if op['opcode'] == 'KVSto':
    return RealMakeKVSto(op['dict_level'], op['index'],
                         op['key_str'], op['val_str'])
  if op['opcode'] == 'Rem':
    return RealMakeRem(op['dict_level'], op['index'])
  raise StandardError()

def RealOpsToOps(realops):
  input_size = len(realops)
  idx = 0
  ops = []
  realop = [ord(c) for c in realops]
  #print "input_size: ", input_size
  while input_size > idx:
    (opcode, k, l) = ParseFB(realop[idx])
    if l:
      l = 'c'
    else:
      l = 'g'
    idx += 1

    if opcode == 0x0:  # ERef
      key_len = B3ToInt(realop[idx+0:idx+3])
      idx += 3
      key = ListToStr(realop[idx:idx+key_len])
      idx += key_len
      val_len = B3ToInt(realop[idx+0:idx+3])
      idx += 3
      val = ListToStr(realop[idx:idx+val_len])
      idx += val_len
      ops.append(MakeERef(key, val))
      continue
    if opcode == 0x1:  # Store
      index   = B2ToInt(realop[idx+0:idx+2])
      str_len = B3ToInt(realop[idx+2:idx+5])
      idx += 5
      str_val = ListToStr(realop[idx:idx+str_len])
      idx += str_len
      ops.append(MakeStore(k, l, index, str_val))
      continue
    if opcode == 0x2:  # TaCo
      truncto = B3ToInt(realop[idx+0:idx+3])
      index   = B2ToInt(realop[idx+3:idx+5])
      str_len = B3ToInt(realop[idx+5:idx+8])
      idx += 8
      str_val = ListToStr(realop[idx:idx+str_len])
      idx += str_len
      ops.append(MakeTaCo(k, l, index, truncto, str_val))
      continue
    if opcode == 0x3:  # KVSto
      index   = B2ToInt(realop[idx+0:idx+2])
      idx += 2
      key_len = B3ToInt(realop[idx+0:idx+3])
      idx += 3
      key = ListToStr(realop[idx:idx+key_len])
      idx += key_len
      val_len = B3ToInt(realop[idx+0:idx+3])
      idx += 3
      val = ListToStr(realop[idx:idx+val_len])
      idx += val_len
      ops.append(MakeKVSto(l, index, key, val))
      continue
    if opcode == 0x4:  # Rem
      index   = B2ToInt(realop[idx+0:idx+2])
      idx += 2
      ops.append(MakeRem(l, index))
      continue

    print "unknown opcode: ", hex(opcode)
    raise StandardError()  # unknown opcode.
  return ops


def FormatOp(op):
  order = ['opcode', 'k', 'dict_level', 'index', 'truncate_to', 'str_len',
      'str_val', 'key_str_len', 'key_str', 'val_str_len', 'val_str']
  outp = ['{']
  inp = []
  for key in order:
    if key in op and key is not 'opcode':
      inp.append("'%s': %s" % (key, repr(op[key])))
    if key in op and key is 'opcode':
      inp.append("'%s': %s" % (key, repr(op[key]).ljust(7)))
  for (key, val) in op.iteritems():
    if key in order:
      continue
    inp.append("'%s': " % key, " ", repr(op[key]))
  outp.append(', '.join(inp))
  outp.append('}')
  return ''.join(outp)

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
    self.use_zlib = 1
    self.ephemereal_headers = {}
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
    # ops.append(MakeERef(key, value))
    # return ops
    (dict, dict_level, key_idx) = self.FindAppropriateEntry(key, stream_group)

    if key_idx == -1:  # store a new one.
      key_idx = NextIndex(dict)
      ops.append(MakeKVSto(dict_level, key_idx, key, value))
      #ops.extend([MakeStore(1, dict_level, key_idx, key),
      #            MakeStore(0, dict_level, key_idx, value)])
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
      #print "executing: ", FormatOp(op)
      self.ExecuteOp(op, stream_group, {})
    return ops

  def GenerateAllHeaders(self, stream_group):
    headers = {}
    for (idx, item) in self.connection_dict.iteritems():
      headers[item[1]] = item[0]
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      headers[item[1]] = item[0]
    for (key, value) in self.ephemereal_headers.iteritems():
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

  def Decompress(self, op_blob):
    if not self.use_zlib:
      return op_blob
    return self.decompressor.decompress(op_blob)

  def DeTokenify(self, realops, stream_group):
    ops = RealOpsToOps(realops)
    self.ephemereal_headers = {}
    self.ExecuteOps(ops, stream_group, self.ephemereal_headers)

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
    index = op['index']

    if dict_level != 'c':
      dict = self.stream_group_dicts[stream_group]
    if opcode == 'Store':
      is_key = op['k']
      str_val = op['str_val']
      str_len = op['str_len']
      if str_len == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key, str_val)
    elif opcode == 'TaCo':
      is_key = op['k']
      str_val = op['str_val']
      str_len = op['str_len']
      truncate_to = op['truncate_to']
      if str_len == 0:
        raise StandardError()
      self.ModifyDictEntry(dict, index, is_key,
          dict[index][is_key][:truncate_to] + str_val)
    elif opcode == 'KVSto':
      self.ModifyDictEntry(dict, index, 1, op['key_str'])
      self.ModifyDictEntry(dict, index, 0, op['val_str'])
    elif opcode == 'Rem':
      self.ModifyDictEntry(dict, index, 0, '')
    else:
      # unknown opcode
      raise StandardError()

  def MakeRemovalOps(self, stream_group):
    remove_ops = []
    for (idx, item) in self.connection_dict.iteritems():
      if self.NotCurrent(item):
        remove_ops.append(MakeRem('c', idx))
    for (idx, item) in self.stream_group_dicts[stream_group].iteritems():
      if self.NotCurrent(item):
        remove_ops.append(MakeRem('g', idx))
    for op in remove_ops:
      self.ExecuteOp(op, stream_group, {})
    return remove_ops

  def Compress(self, ops):
    realops = [OpToRealOp(op) for op in ops]
    ba = ''.join(realops)
    if not self.use_zlib:
      return ba
    retval = self.compressor.compress(ba)
    retval += self.compressor.flush(zlib.Z_SYNC_FLUSH)
    return retval

  # returns a list of operations
  def Tokenify(self, headers, stream_group):
    self.generation += 1
    ops = []
    for (key, value) in headers.iteritems():
      if not stream_group in self.stream_group_dicts:
        self.stream_group_dict[stream_group] = {}
      ops.extend(self.MakeOps(key, value, stream_group))
    remove_ops = self.MakeRemovalOps(stream_group)
    return remove_ops + ops


def Spdy3HeadersFormat(request):
  out_frame = []
  for (key, val) in request.iteritems():
    out_frame.append(struct.pack("!L", len(key)))
    out_frame.append(key)
    out_frame.append(struct.pack("!L", len(val)))
    out_frame.append(val)
  return ''.join(out_frame)

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
  spdy4_frame_list = []
  zlib_frame_list = []
  spdy4_compressor = CompressorDecompressor()
  spdy4_decompressor = CompressorDecompressor()
  use_zlib = 1
  spdy4_compressor.use_zlib = use_zlib
  spdy4_decompressor.use_zlib = use_zlib

  zlib_compressor = zlib.compressobj()
  for request in requests:
    print "Tokenify: ", request
    in_ops = spdy4_compressor.Tokenify(request, 0)
    #for op in in_ops:
    #  print FormatOp(op)
    #print
    in_frame = spdy4_compressor.Compress(in_ops)
    spdy4_frame_list.append(in_frame)
    spdy3_frame = Spdy3HeadersFormat(request)
    zlib_frame_list.append(zlib_compressor.compress(spdy3_frame) +
                           zlib_compressor.flush(zlib.Z_SYNC_FLUSH))
  print
  for frame in requests:
    print "origl frame size: 11+%d" % len(Spdy3HeadersFormat(frame))
  print
  for frame in spdy4_frame_list:
    print "spdy4 frame size: 11+%d" % len(frame)
  print
  for frame in zlib_frame_list:
    print "spdy3 frame size: 11+%d" % len(frame)
  print

  out_requests = []
  for frame in spdy4_frame_list:
    out_ops = spdy4_decompressor.Decompress(frame)
    #for op in RealOpsToOps(out_ops):
    #  print FormatOp(op)
    #print
    out_frame = spdy4_decompressor.DeTokenify(out_ops, 0)
    out_request = spdy4_decompressor.GenerateAllHeaders(0)
    out_requests.append(out_request)
    print "Detokened: ", out_request

  if requests == out_requests:
    print "Original requests == output"
  else:
    print "Something is wrong."
    for i in xrange(len(requests)):
      if requests[i] != out_requests[i]:
        print requests[i]
        print "   !="
        print out_requests[i]
        print

main()



