#!/usr/bin/python

class Sender:
  def __init__(self):
    self.flow_control_default_size = 64*1024
    self.group_info = {0: {"window": self.flow_control_default_size} }
    self.stream_info = {0: {"window": self.flow_control_default_size,
                            "group": 0}}

################################################################################

  def OnWindowUpdate(stream_id, stream_update, group_update):
    if stream_id == 0:
      if group_update == 0:
        # that is a meaningless message then. Actively discourage such.
        self.SendProtocolErrorAndTerminate()
      else:
        # update to stream zero
        self.group_info[0].window += group_update
      return
    try:
      self.stream_info[stream_id].window += stream_update
      self.stream_info[stream_id].ok_to_send_am_blocked = true
      self.group_info[self.stream_info[stream_id].group].window += group_update
    except KeyError:
      pass;

  def OnSynStream(stream_id):
    self.stream_info[stream_id] = {"window": self.flow_control_default_size,
                                   "group": 0,
                                   "ok_to_send_am_blocked": true}

  def OnFinStreamOrRstStream(stream_id):
    self.remove(stream_id)

################################################################################

  def MaxBytesToSend(stream_id):
    try:
      stream_info = self.stream_info[stream_id]
      return min(stream_info.window, self.group_info[stream_info.group].window)
    except KeyError:
      return 0

  def UpdateFlowControl(stream_id, bytes_sent, bytes_remaining):
    stream_info = self.stream_info[stream_id]
    group_info = self.group_info[stream_id.group]
    stream_info.window -= bytes_sent
    group_info.window -= bytes_sent
    if bytes_remaining and (stream_info.window == 0 or group_info.window == 0):
      SendBlockedByFlowControlFrame(stream_id,
                                    stream_info.window == 0,
                                    group_info.window == 0)

  # data is assumed to be a sequence of bytes
  def SendBytes(socket, stream_id, data):
    if (IsNotWritable(socket)):
      return;
    max_bytes_to_send = self.MaxBytesToSend(stream_id)
    if (len(data) > max_bytes_to_send):
      self.MaybeSendBlockedByFlowControlFrame(stream_id)
    bytes_to_send = min(len(data), max_bytes_to_send)
    bytes_sent = 0
    try:
      socket.setblocking(0)  # ensure non-blocking
      bytes_sent = socket.send(data[:bytes_to_send])
    except:
      self.SocketNotWritable(socket)
      pass
    self.UpdateFlowControl(stream_id, bytes_sent)
    return bytes_sent


  def MaybeSendBlockedByControlFrame(stream_id):
    try:
      stream_info = self.stream_info[stream_id]
      if not stream_info.ok_to_send_am_blocked:
        return
      blocked_by_stream_window = stream_info.window == 0
      blocked_by_group_window = self.group_info[stream_info.group].window == 0
      SendBlockedByFlowControl(stream_id,
                               blocked_by_stream_window,
                               blocked_by_group_window)
    except:
      pass


