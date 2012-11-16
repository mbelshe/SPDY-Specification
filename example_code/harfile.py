#!/usr/bin/python

# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import json
import sys

def MakeDefaultHeaders(list_o_dicts, items_to_ignore=[]):
  retval = {}
  for kvdict in list_o_dicts:
    key = kvdict["name"].lower()
    val = kvdict["value"]
    if key == "host":
      key = ":host"
    if key in items_to_ignore:
      continue
    if key in retval:
      retval[key] = retval[key] + '\0' + val
    else:
      retval[key] = val
  return retval

def EncodeStringsAsUTF8(x):
  retval = {}
  for k,v in x.iteritems():
    n_k = k
    if isinstance(k, unicode):
      n_k = k.encode("utf8")
    n_v = v
    if isinstance(v, unicode):
      n_v = v.encode("utf8")
    retval[n_k] = n_v
  return retval

def ReadHarFile(filename):
  f = open(filename)
  try:
    o = json.loads(f.read(), object_hook=EncodeStringsAsUTF8)
    # and now lets convert all strings to utf8.
  except Exception as x:
    print x
    sys.exit("unable to parse: " + filename)

  request_headers = []
  response_headers = []
  for entry in o["log"]["entries"]:
    request = entry["request"]
    header = MakeDefaultHeaders(request["headers"], ["connection"])
    header[":method"] = request["method"].lower()
    header[":path"] = re.sub("^[^:]*://[^/]*/","/", request["url"])
    header[":version"] = re.sub("^[^/]*/","", request["httpVersion"])
    header[":scheme"] = re.sub("^([^:]*):.*$", '\\1', request["url"]).lower()
    if not ":host" in request_headers:
      header[":host"] = re.sub("^[^:]*://([^/]*)/.*$","\\1", request["url"])
    if not header[":scheme"] in ["http", "https"]:
      continue
    request_headers.append(header)

    response = entry["response"]
    header = MakeDefaultHeaders(response["headers"],
        ["connection", "status", "status-text", "version"])
    header[":status"] = re.sub("^([0-9]*).*","\\1", str(response["status"]))
    header[":status-text"] = response["statusText"]
    header[":version"] = re.sub("^[^/]*/","", response["httpVersion"])
    response_headers.append(header)
  return (request_headers, response_headers)


