
def ListToStr(val):
  return ''.join(["%c" % c for c in val])

def StrToList(val):
  return [ord(c) for c in val]


def MakeReadableString(val):
  printable = string.digits + string.letters + string.punctuation + ' ' + "\t"
  out = []
  for c in val:
    if c in printable:
      out.append("   %c " % c)
    else:
      out.append("0x%02x " % ord(c))
  return ''.join(out)

def FormatAsBits(output_and_bits):
  (output, bits) = output_and_bits
  retval = []
  if not bits:
    total_bits = len(output) * 8
  elif bits % 8:
    total_bits = (len(output) - 1) * 8 + (bits % 8)
  else:
    total_bits = len(output) * 8
  idx = 0
  while total_bits >= 8:
    c = output[idx]
    idx += 1
    retval.append('|')
    retval.append("{0:08b}".format(c))
    total_bits -= 8

  if (bits % 8) != 0:
    retval.append('|')
    retval.append("{0:08b}".format(output[idx])[0:(bits % 8)])
  retval.extend([' [%d]' % bits])
  return ''.join(retval)

def FormatAsHTTP1(frame):
  out_frame = []
  fl = ""
  avoid_list = []
  if ":method" in frame:
    fl = "%s %s HTTP/%s\r\n" % (
        frame[":method"],frame[":path"],frame[":version"])
    avoid_list = [":method", ":path", ":version"]
  else:
    fl = "HTTP/%s %s %s\r\n" % (
        frame[":version"],frame[":status"],frame[":status-text"])
    avoid_list = [":version", ":status", ":status-text"]
  out_frame.append(fl)
  for (key, val) in frame.iteritems():
    if key in avoid_list:
      continue
    if key == ":host":
      key = "host"
    for individual_val in val.split('\x00'):
      out_frame.append(key)
      out_frame.append(": ")
      out_frame.append(individual_val)
      out_frame.append("\r\n")
  return ''.join(out_frame)
