#!/usr/bin/python3.6
# -*- coding: utf-8 -*-

"""! @file meplayer.py - Multi-File Player based on UriDecodeBin
@brief Source for Userful's UmePlayer.

@copyright Copyright ⓒ 2021-2022 Userful @n

@defgroup PyElements Userful GStreamer Elements in Python

The Chonos project (formerly the Userful Media Engine project) contains a
number of subprojects and this distribution (UGP – The Userful GStreamer
Python Elements) is one such subproject. Its purpose it to provide a set of
easily maintained elements written in Python which provide functionality
needed by our Media Engine.

FIXME:

1) Negotiations are somewhat broken in that not all component elements see the
   caps restrictions they should work under. This can lead to someone asking
   for memory:FVMemory buffers and getting memory:system buffers. For now,
   since fvmem is the preferred decoding, we've got a flag to disable fvdec.

"""
import json
import os
import sys
import threading
import traceback

# from dataclasses  import dataclass, field
from enum         import IntEnum
from os.path      import abspath, dirname, isfile, join, normpath
from urllib.parse import urlsplit, urlunsplit

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
gi.require_version('GstRtsp', '1.0')
gi.require_version('GstRtspServer', '1.0')
# pylint: disable=wrong-import-position
from gi.repository import GLib, GObject, Gst  # noqa: E402


__author__ = """\
Yang Wang <yang.wang@userful.com>, \
Reza Rezavi <reza.razavi@userful.com>, \
Stirling Westrup <stirling.westrup@userful.com>
"""

UGP_VERS    = "1.5"
VERBOSE     = True
TRACE_LOCKS = False

THIS_DIR = abspath(dirname(__file__))
TOP_DIR  = abspath(THIS_DIR + "/..")

GObject.threads_init()
Gst.init(None)

LATENCY = 0.05 * Gst.SECOND

OUTPUTS = ("audio", "video")

CAPS = \
  { "audio": Gst.Caps.from_string("audio/x-raw")
  , "video": Gst.Caps.from_string("video/x-raw")
# , "video": Gst.Caps.from_string\
#     ( "video/x-raw(memory:MEMemory); "
#     + "video/x-raw(memory:FVMemory); "
#     + "video/x-raw;
#     )
  }

TPL = \
  { out: Gst.PadTemplate.new
      ( out
      , Gst.PadDirection.SRC
      , Gst.PadPresence.ALWAYS
      , CAPS[out]
      )
    for out in OUTPUTS
  }

AUDIO_CAPS = CAPS['audio']
AUDIO_TPL  = Gst.PadTemplate.new\
  ( "audio"
  , Gst.PadDirection.SRC
  , Gst.PadPresence.ALWAYS
  , AUDIO_CAPS
  )


VIDEO_CAPS = CAPS['video']

VIDEO_TPL  = Gst.PadTemplate.new\
  ( "video"
  , Gst.PadDirection.SRC
  , Gst.PadPresence.ALWAYS
  , VIDEO_CAPS
  )


############################################
# Debugging and Utility Code
############################################

def generate_dot_file(elm):
  "Generate a .dot file for the given element"
  dot = Gst.debug_bin_to_dot_data(elm, Gst.DebugGraphDetails.VERBOSE)
  i = 0
  ftpl = TOP_DIR + "/out.%s.dot"
  while True:
    fil = ftpl % i
    if not os.path.exists(fil):
      break
    i += 1
  log(f"Dot File: writing to {fil}")
  with open(fil, "w") as f:
    f.write(dot)


def timestr(time):
  "Convert a GstClockTime to a string"
  hours = int( time / (Gst.SECOND  * 60   * 60))
  mins  = int((time / (Gst.SECOND  * 60)) % 60)
  secs  = int((time / (Gst.SECOND) % 60))
  sub   = int( time % (Gst.SECOND / 100))
  ret = f"{hours:d}:{mins:02d}:{secs:02d}:{sub:02d}"
  return ret


def enum_nick(enum_val):
  """Convert a GstEnum value to its nick"""
  return enum_val.value_nick.upper()


class TracedLock():
  """Debugging Class to Trace Lock Usage"""
  def __init__(self, lock):
    self.count = 0
    self.lock  = lock

  def __enter__(self):
    tb = traceback.extract_stack(f=sys._getframe(1), limit=1)[0]
    self.count += 1
    prefix = "»" * self.count
    loc = f"{tb.name}:{tb.lineno}"
    log(f"{prefix}{loc}:Lock Entry")
    self.lock.__enter__()

  def __exit__(self, *args):
    tb = traceback.extract_stack(f=sys._getframe(1), limit=1)[0]
    postfix = "«" * self.count
    self.count -= 1
    loc = f"{tb.name}:{tb.lineno}"
    log(f"{postfix}:{loc}:Lock Exit")
    self.lock.__exit__()


def log(*args):
  """Simple logging routine. Set VERBOSE to also print to screen"""
  msg = ''
  for m in args:
    msg += str(m) + ' '
  Gst.debug(msg)
  if VERBOSE:
    print(msg)
    sys.stdout.flush()



############################################
# Start of our Element
############################################
# pylint: disable=too-many-instance-attributes
class UmePlayer(Gst.Bin):
  """
  UmePlayer is the Class of the meplayer element.
  """
  __gtype_name__ = "UmePlayer"

  __gstmetadata__ = \
      ( 'UmePlayer'
      , 'Decoder/Player/MultiFile'
      , 'Upgrade to UriDecodeBin that can take a playlist'
      , __author__
      )

  __gsignals__ = \
    { "end-of-playlist" :
        ( GObject.SIGNAL_RUN_FIRST
        , None
        , ()
        )
    , "now-playing" :
        ( GObject.SIGNAL_RUN_FIRST
        , None
        , (str, int, int)
        )
    }

  __gsttemplates__ = (AUDIO_TPL, VIDEO_TPL)

  __gproperties__ = \
    { "gpu-slot-no" :
         ( GObject.TYPE_INT
         , "GPU PCI Slot"
         , "The GPU's PCI Slot number, if using GPU decoding"
         , 0, 255
         , 0
         , GObject.ParamFlags.READWRITE
         )
    , "playlist" :
         ( str
         , "JSON string of playlist, or @filepath of file containing JSON"
         , "Provides list of source uri with the time duration of each source"
         , ""
         , GObject.ParamFlags.READWRITE
         )
    , "playthroughs" :
         ( int
         , "Play times"
         , "Sets the the number of loops a playlist goes through"
         , -1, GObject.G_MAXINT
         , 1
         , GObject.ParamFlags.READWRITE
         )
    , "playlist-size" :
         ( GObject.TYPE_UINT
         , "Playlist size"
         , "Gets the size of current playlist"
         , 0, GObject.G_MAXUINT
         , 0
         , GObject.ParamFlags.READABLE
         )
    , "playlist-index" :
         ( GObject.TYPE_UINT
         , "Index of current playing source"
         , "Gets the index of current uri in the playlist"
         , 0, GObject.G_MAXUINT
         , 1
         , GObject.ParamFlags.READABLE
         )
     , "fvmem" :
         ( bool
         , "fv memory"
         , "Whether to allow (memory:FVMemory) output?"
         , True
         , GObject.ParamFlags.READWRITE
         )
    }

  version = UGP_VERS
  element_name = __gtype_name__

  class _Select(IntEnum):
    """
    FIXME: The Gst.AutoplugSelect enum has no bindings in gst-python,
    so for now we use this Enum
    """
    TRY    = 0
    EXPOSE = 1
    SKIP   = 2

  class Output(object):
    "Class for keeping track of UmePlayer's output pads"

    def __init__(self, parent:Gst.Bin, media:str, template:str):
      ghost = Gst.GhostPad.new_no_target_from_template(media, template)
 #    ghost.set_query_function_full(self._cb_query)
 #    ghost.set_event_function_full(self._cb_event)
      self.media    = media
      self.template = template
      self.ghost    = ghost
      self.linked   = None
      self.null     = None
      self.parent   = parent

    def inject(self, dest: Gst.Bin, ghost=True, null=True):
      "install component elements into a GstBin or GstPipeline"
      if ghost and self.ghost is not None:
        dest.add_pad(self.ghost)
      if null and self.null is not None:
        dest.add(self.null)

    def set_null(self, obj: Gst.Element):
      "set the null media generator for this output"
      self.null = obj

    def _reset_null(self):
      '''Reset the null media generator

      To prevent deadlock in gobject mainloop, it's good idea to call this
      method using idle_add() or timeout_add()
      '''
      self.null.set_state(Gst.State.NULL)

      while True:
        (sts,state,pending) = self.null.get_state(Gst.CLOCK_TIME_NONE)
        if state == Gst.State.NULL:
          break
          log("waiting...")
      self.null.set_locked_state(True)

    def unlink(self):
      "Handle unlinking of an output pad from its source"
      if self.linked is not None:
        log(f"Unlinking out[{self.media}] from {self.linked.name}")
        if self.linked == self.null:
          self.null.set_state(Gst.State.NULL)

          while True:
            (sts,state,pending) = self.null.get_state(Gst.CLOCK_TIME_NONE)
            if state == Gst.State.NULL:
              break
              log("waiting...")
          self.null.set_locked_state(True)

        self.ghost.set_target(None)
        self.linked = None
      else:
        log(f"out[{self.media}] already unlinked")



  # WARNING: when you have an element which is derived from Gst.Bin
  # (as we do) and you store a member element such as
  #
  #   self.element = Gst.ElementFactory.make("element",None)
  #
  # Then that element gets automagically added to the bin and linked
  # to something. This is almost NEVER what you want. So, we try not to
  # let it happen.

  def __init__(self):
    Gst.Bin.__init__(self)

    self.fvmem           = True
    self.playlist        = None
    self.plays           = 0
    self.playthroughs    = 1
    self.gpu_slot_no     = 0       # visible property
    self._gpu_slot_no    = None    # None    # actual property
    self._index          = 0
    self._playing        = False
    self._rtsp_playback  = False

    self._pad_offset     = 0
    self._timer          = None
    self._timer_start    = 0
    self._finished       = False     # are we shutting down?
    self._dirname        = THIS_DIR  # relative URLs resolved relative to this

    if TRACE_LOCKS:
      self._lock = TracedLock(threading.Lock())
    else:
      self._lock = threading.Lock()
    self._pl     = []
    self._probe  = {}
    self._padcat = {}

    # track our outputs
    self._out    = \
      { media: self.Output(self, media, TPL[media]) for media in OUTPUTS
      }

    # Because pipeline and element clocks can come and go and have different
    # properties (sometimes they'll be GstAudioClocks), we get our own system
    # clock handle for the duration.
    self._system_clock = Gst.SystemClock.obtain()

    # setting the null output elements has to be done individually for now:
    null = Gst.ElementFactory.make("audiotestsrc", "null_audio")
    null.set_property("wave", "silence")
    null.set_locked_state(True)
    out = self._out['audio'].set_null(null)

    null = Gst.ElementFactory.make("videotestsrc", "null_video")
    null.set_property("pattern", "black")
    null.set_locked_state(True)
    self._out['video'].set_null(null)

    # construct and add ghost pads
    # We create the ghost pads first because when we later add the
    # elements to connect to the ghost pads, pygst will automatically
    # link them to ghostpads, creating anonymous ones if they don't
    # already exist.
    for out in OUTPUTS: self._out[out].inject(self)

    self.decoder = Gst.ElementFactory.make("uridecodebin", "decoder")
    self.decoder.set_property("use-buffering", True)

    # message and signal set up
    self.decoder.connect('drained',            self._cb_drained)
    self.decoder.connect('no-more-pads',       self._cb_no_more_pads)
    self.decoder.connect('pad-added',          self._cb_pad_added)
    self.decoder.connect('pad-removed',        self._cb_pad_removed)
    self.decoder.connect('autoplug-select',    self._cb_autoplug_select)
    self.decoder.connect('autoplug-query',     self._cb_autoplug_query)
    self.decoder.connect('element-added',      self._cb_element_added)
    self.decoder.connect('deep-element-added', self._cb_deep_element_added)

    self.add(self.decoder)   # Decodes a media file

  def object_set_state(self, obj, state):
    "set an element state in an async manner"
    def _cb_state_set(self, obj, state):
      obj.set_state(state)
#   self.call_async(_cb_state_set, obj, state)
    GLib.idle_add(_cb_state_set, self, obj, state)

  def object_sync(self, obj):
    "sync an element state in an async manner"
    def _cb_state_sync(self, obj):
      obj.sync_state_with_parent()
#   self.call_async(_cb_state_sync, obj)
    GLib.idle_add(_cb_state_sync, self, obj)

  def _player_stop(self):
    "set player element to STOP state"
    self._playing = False
    self.object_set_state(self, Gst.State.NULL)

  def _player_ready(self):
    "set player element to READY state"
    self.object_set_state(self, Gst.State.READY)

  def _player_start(self):
    "set player element to PLAYING state"
    self._playing = True
    self.object_set_state(self, Gst.State.PLAYING)

  def _player_sync(self):
    "sync player element with parent bin"
    self.object_sync(self)

  def _player_restart(self):
    "Stop player, load next item, and start again"
    log(f"Restart: Pausing Play")
    self._player_stop()
    item = self._get_current_item()
    log(f"Restart: Playing with Current Item: {item['uri']}")
    self._player_start()
    log(f"Restarted")

  def _decoder_set_state(self, state):
    "Set a state on the decoder element (UriDecodeBin)"
    log(f"Ensure Decoder in state {enum_nick(state)}")
    self.object_set_state(self.decoder, state)

  def _decoder_sync(self):
    "Sync decoder bin with its parent bin"
    log(f"Syncing decoder")
    self.object_sync(self.decoder)

  def do_set_property(self, prop, val):
    "property setter"
    log(f"Set property: {prop.name}")
    if prop.name == 'playlist':
      self.playlist = val
      self._load_playlist(val)
    elif prop.name == 'playthroughs':
      log(f"{prop.name} is {val}")
      self.playthroughs = val
    elif prop.name == 'fvmem':
      log(f"{prop.name} is {val}")
      self.fvmem = val
    elif prop.name == 'gpu-slot-no':
      self.gpu_slot_no = val
      if 0 <= val <= 255:
        self._gpu_slot_no = val
    else:
      log(f"Error: Invalid Property {prop}")

  def do_get_property(self, prop):
    "property getter"
    ret = None
    if prop.name == 'playlist':
      ret = self.playlist
    elif prop.name == 'playthroughs':
      ret = self.playthroughs
    elif prop.name == 'playlist-size':
      ret = len(self._pl)
    elif prop.name == 'playlist-index':
      ret = self._index
    elif prop.name == 'current-uri':
      ret = self._pl[self._index]['uri']
    elif prop.name == 'fvmem':
      ret = self.fvmem
    elif prop.name == 'gpu-slot-no':
      ret = self.gpu_slot_no
    else:
      log(f"Error: Invalid Property {prop}")
    return ret

  def do_change_state(self, transition):   # pylint disable=arguments-differ
    "state change handler"
    sts = True
    if transition == Gst.StateChange.READY_TO_PAUSED:
      sts = self._start()
    elif transition == Gst.StateChange.PAUSED_TO_PLAYING:
      sts = self._announce()
    elif transition == Gst.StateChange.PAUSED_TO_READY:
      sts = self._stop()
    if sts:
      ret = Gst.Bin.do_change_state(self, transition)
    else:
      ret = Gst.StateChangeReturn.FAILURE
    # log(f"State Change {transition} Returning {ret}")
    return ret

  def _cb_query(self, pad, parent, query):
    "query handler"
    qtyp = query.type
    log(f"got query {qtyp.get_name(qtyp)} for {parent.name}.{pad.get_name()}")
    tgt = pad.get_target()
    if tgt:
      log(f"delegate on internal link")
      ret = tgt.query(query)
    else:
      log(f"no target")
      ret = self.decoder.query(query)
    if qtyp == Gst.QueryType.LATENCY:
      parse = query.parse_latency()
      log(f"Parse: {parse}")
      query.set_latency\
        ( parse.live
        , parse.min_latency + LATENCY
        , parse.max_latency
        )
      log(f"Got {query.parse_latency()}")
    elif qtyp == Gst.QueryType.DURATION:
      parse = query.parse_duration()
      log(f"Parse: {parse}")
    return ret

  def _cb_event(self, pad, parent, event):
    "event handler"
    etyp = event.type
    log(f"got event {etyp.get_name(etyp)} for {parent.name}.{pad.get_name()}")
    tgt = pad.get_target()
    if tgt:
      log(f"delegate on internal link")
      ret = tgt.send_event(event)
    else:
      log(f"no target")
      ret = self.decoder.send_event(event)
    return ret

  def _normalize_uri(self, uri):
    "resolve URI scheme and convert to absolute if relative"
    split = urlsplit(uri, scheme='file')
    abstr = normpath(join(self._dirname, split.path))
    split = split._replace(path=abstr)
    uri = urlunsplit(split)
    print(f"URI: {uri}")
    return uri

  def _start(self):
    "Get the current item, and start playing it"
    log(f"Start function called, index is {self._index}")
    item = self._get_current_item()
    if item:
      log(f"Got item {item}")
      uri = self._normalize_uri(item['uri'])
      log(f"Got URI {uri}")
      self.decoder.set_property("uri", uri)
      timeout = float(item.get('timeout', "-1"))
      if timeout > 0.0:
        self._set_timer(timeout)
    else:
      log(f"No Item. Was playlist set?")
    return item is not None

  def _announce(self):
    "Send Signal announcing start of play."
    item = self._get_current_item()
    self.emit("now-playing", item['uri'], self._index, len(self._pl))
    return True

  def _load_playlist(self, jstr):
    "Load the playlist into a dict, handling file refs if need be"
    log(f"Loading: {jstr}")
    pl = None
    if self._playing == True:
      self._player_stop()
    # convert json string to dictionary, or read it from json file
    if jstr[0:1] == '@':
      filename = os.path.abspath(jstr[1:])
      if isfile(filename):
        self._dirname = os.path.dirname(filename)
        log(f"dirname is now {self._dirname}")
        with open(filename) as f:
          pl = json.load(f)
      else:
        log(f"ERROR: playlist file \"{filename}\" not found.")
    else:
      try:
        pl = json.loads(jstr)
      except ValueError:
        log(f"ERROR: Playlist is not valid")
    log(f"Playlist is now length {len(self._pl)}")
    with self._lock:
      self._pl    = pl
      self._index = 0
      self.plays = 0
    if self._pl[0]["uri"].startswith("rtsp://"):
      self._rtsp_playback = True
    else:
      self._rtsp_playback = False
    self._player_sync()

  def _stop(self):
    "Stop playing the current media item"
    log(f"Stop function called, index is {self._index}")
    with self._lock:
      if self._timer:
        self._system_clock.id_unschedule(self._timer)
        self._timer = None
      for media in OUTPUTS: self._out[media].unlink()
    log("Stopped")
    return True

  def _get_current_item(self):
    "return the current media item, or None"
    log("fetch current item")
    ret = None
    if self._index < len(self._pl):
      ret = self._pl[self._index]
    return ret

  def _get_next_item(self):
    "advance to next item and return it, or None on failure"
    log("advance to next item")
    with self._lock:
      ok = False
      num = len(self._pl)
      if num < 1:
        log("Error, no playlist!")
      else:
        ok = True
        self._index += 1
        if self._index >= num:
          self._index  = 0
          self.plays += 1
          if self.playthroughs < 0 or self.plays < self.playthroughs:
            log(f"Starting Playthough #{self.plays+1}")
          else:
            ok = False
      if ok:
        ret = self._get_current_item()
      else:
        ret = None
      return ret

  def _cb_timeout(self, clock, time, timer):
    "timer timeout callback"
    start = self._timer_start
    elapsed = time - start
    log(f"Timeout on {clock.name} at {timestr(elapsed)}")
    self._timer = None
    self.end_this_segment()

  def _set_timer(self, secs):
    "set a timer with a timeout of <secs> seconds"
    now = self._system_clock.get_time()
    deadline = now + secs * Gst.SECOND
    self._timer_start = now
    self._timer = self._system_clock.new_single_shot_id(deadline)
    ret = Gst.Clock.id_wait_async(self._timer, self._cb_timeout)
    if ret == Gst.ClockReturn.EARLY:
      log("Early Timeout?")  # we timed out before we could set timer...
      self._cb_timeout(self._system_clock, deadline, self._timer)
    elif ret != Gst.ClockReturn.OK:
      log("Clock Error!")
      raise Exception(f"Clock Error Gst.ClockReturn = {ret}")

  def _set_pad_offset(self, pad):
    "handle new media created pads and apply any necessery time offset"
    clock  = self.get_clock()

    if clock :
      base_time = self.get_base_time()
      runtime = clock.get_time() - base_time + LATENCY
      # Use the existing pad_offset if the difference is less than .1 seconds
      # as there could be multiple streams (ie video and audio) added a short
      # time apart, but there could also be a sequence of very short streams. I
      # doubt we'd ever play a stream shorter than .5 seconds, and even a fast
      # image flip would probably give more than .1 seconds per image.
      if runtime - self._pad_offset < 100000000:
        runtime = self._pad_offset
      log(f"Set pad offset to {timestr(runtime)}")
      if self._rtsp_playback == False:
        pad.set_offset(runtime)
      self._pad_offset = runtime
    else:
      log(f"Missing clock {clock}")

  def _cb_pad_probe(self, pad, info, cat):
    "filter output of EOS to prevent early pipeline shut down"
    ret = Gst.PadProbeReturn.PASS
    if info.type & Gst.PadProbeType.EVENT_DOWNSTREAM:
      event = info.get_event()
      if event.type == Gst.EventType.EOS and not self._finished:
        log(f"pad probe: {self.name}.{pad.name} with {cat}: EOS Dropped")
        ret = Gst.PadProbeReturn.DROP
    return ret

  def _cb_autoplug_select(self, elm, pad, caps, factory):
    "check for FVMemory output"
    fname  = factory.get_name()
    if not self.fvmem and fname.startswith("fv"):
      ret = UmePlayer._Select.SKIP
    else:
      ret = UmePlayer._Select.TRY
    res = "accepted" if ret == UmePlayer._Select.TRY else "denied"
    log(f"Autoplug Select: {fname} {res}")
    return ret

  # pylint: disable=no-self-use   # it will get used eventually
  def _cb_autoplug_query(self, bin_, pad, elm, query):
    "handle queries from unplugged elements"
    log(f"{bin_.name} Saw Query {query} from {elm.name}.{pad.name}")
    return False  # didn't handle query

  def _cb_deep_element_added(self, bin_, subbin, elm):
    "configure a new element in uridecodebin"
    typename = type(elm).__name__
#    if bin_ is subbin:
#      log(f"{bin_.name} added ({typename}){elm.name}")
#    else:
#      log(f"{bin_.name}.{subbin.name} added ({typename}){elm.name}")
    #hardware decoder type extended to GstFvDec, GstFvH264Dec and GstFvH265Dec
    if typename.startswith("GstFv") and typename.endswith("Dec") and self._gpu_slot_no is not None:
      # log(f"Set gpu-slot-no to {self._gpu_slot_no}")
      elm.set_property("gpu-slot-no", self._gpu_slot_no)

  def _cb_element_added(self, bin_, elm):
    "defer to previous to configure a new element in uridecodebin"
    self._cb_deep_element_added(bin_, bin_, elm)

  def _cb_pad_added(self, element, pad):
    "handle a new pad as it is created by the decoder"
    caps   = pad.get_current_caps()
    capstr = caps.to_string()
    caphead = capstr[0:capstr.index(',')]
    padcat = capstr[0:capstr.index('/')]
    elmnam = element.name
    nam    = f"{elmnam}.{pad.name}"
    log(f"on_pad_added: {nam} carrying {padcat}, CAPS HEAD: {caphead}")

    if padcat in OUTPUTS:
      self._padcat[nam] = padcat
      output = self._out[padcat]
      self._probe[nam] = output.ghost.add_probe\
        ( Gst.PadProbeType.BLOCK_DOWNSTREAM
        , self._cb_pad_probe
        , padcat
        )

      if output.linked is None:
        output.ghost.set_target(pad)
        self._set_pad_offset(pad)
        output.linked = element
        log(f"{padcat} linked from {elmnam}")
      else:
        log(f"Warning - Multiple {padcat} streams")

  def _cb_no_more_pads(self, elm):
    "Ensure all static pads have output"
    log("No More Pads - Setup NULL Outputs")
    for media in OUTPUTS:
      out = self._out[media]
      if out.linked is None:
        pad = out.null.get_static_pad("src")
        out.ghost.set_target(pad)
        self._set_pad_offset(pad)
        out.null.set_locked_state(False)
        self.object_sync(out.null)
        out.linked = out.null
        log(f"null {media} linked")
      else:
        self.object_set_state(out.null, Gst.State.NULL)
        out.null.set_locked_state(True)
        self.emit("end-of-playlist")
    log("No More Pads - All Setup")

  def _cb_pad_removed(self, obj, pad):
    "deal with a pad being removed"
    objnam = obj.name
    padnam = pad.name
    nam    = f"{objnam}.{padnam}"
    cat    = self._padcat[nam]
    out    = self._out[cat]

    log(f"Pad Removed: {nam} with {cat}")
    out.unlink()  # just in case
    out.ghost.remove_probe(self._probe[nam])
    self._probe[nam]  = None
    self._padcat[nam] = None

  def end_this_segment(self):
    "end this segment NOW"
    log("Ending Segment")
    for media in OUTPUTS: self._out[media].unlink()
    item = self._get_next_item()
    if item:
      log("Advanced to Next")
      self._player_restart()
    else:
      log("Finished Playthroughs")
      self._finished = True
      for media in OUTPUTS:
        out = self._out[media]
        out.null.set_locked_state(False)
        out.ghost.push_event(Gst.Event.new_eos())
      self.send_event(Gst.Event.new_eos())

  def end_early(self, element):
    "abort playing media"
    with self._lock:
      log(f"Stopping {element.name} early")
      element.set_state(Gst.State.NULL)

  def swap_out_media(self):
    "replace audio output with silence. video keeps last shown image"
    log("Swapping to Null Outputs")
    with self._lock:
      for media in ['audio']:  # turn out we only want to swap out audio
        out = self._out[media]
        if out.linked is not None:
          if out.linked != out.null:
            pad = out.null.get_static_pad("src")
            out.ghost.set_target(pad)
            self._set_pad_offset(pad)
            out.null.set_locked_state(False)
            out.null.sync_state_with_parent()
            out.linked = out.null
    self.decoder.call_async(self.end_early)

  def _cb_drained(self, elm):
    "handle end of media"
    log("On Drained")
    if self._timer:
      log("Timer Running - Delay end")
      self.swap_out_media()  # switch to null audio/video
    else:
      log("No Timer - We're done.")
      self.end_this_segment()


__gstelementfactory__ = ("meplayer", Gst.Rank.NONE, UmePlayer)

##############################
## END of UmePlayer Element ##
##############################
SWAP  = False
FVMEM = True

if all (k in os.environ for k in ("DISP_10", "DISP_11")):
  DISP_10 = os.environ['DISP_10']
  DISP_11 = os.environ['DISP_11']
  DISP = [ DISP_10, DISP_11 ]
else:
  if "DISPLAY" in os.environ:
    DISPLAY = os.environ['DISPLAY']
  else:
    DISPLAY = ":0"
  DISP = [DISPLAY, DISPLAY]


# pylint: disable=too-many-locals, too-many-statements
def test():
  "Run a self-test of the UmePlayer class"
  player = UmePlayer()
  pn = player.element_name
  pv = player.version
  tb = '#' * 5
  nl = "\n"
  log(f"{nl}{tb} {pn} {pv}: Self Test {tb}{nl}")

  setvol = .33
  log(f"Self-Test: Starting - Volume is at {int(setvol*100)}%")
  failed   = False
  playlist = \
    [ { "uri" : "../tests/media/Caminandes03.mp4",  "timeout" :  "20"   }
    , { "uri" : "../tests/media/Image_HD_S02.jpg",  "timeout" :  "2"   }
    , { "uri" : "../tests/media/whats_up_doc.wav",  "timeout" : "-1"   }
    , { "uri" : "../tests/media/Image_HD_S01.jpg",  "timeout" :  "2"   }
    , { "uri" : "../tests/media/logo-bounce.mp4",   "timeout" :  "7"   }
    , { "uri" : "../tests/media/PerfectCar.mkv",    "timeout" :  "2.5" }
    , { "uri" : "../tests/media/logo-rotating.mp4", "timeout" : "-1"   }
    ]
  playlist2 = [{ "uri" : "../tests/media/Caminandes03.mp4", "timeout" : "30" }]
  playstr   = json.dumps(playlist)
  playstr2  = json.dumps(playlist2)

  mainloop = GLib.MainLoop()

  def cb_swap_playlists():
    nonlocal player
    nonlocal playstr2
    log("Swapping Playlist!")
    player.set_property("playlist", playstr2)

  def _cb_message(bus, message):
    nonlocal mainloop
    nonlocal failed
    mtype = message.type
    log(f"got message of type {mtype}")
    if mtype == Gst.MessageType.WARNING:
      log(f"WARN: {message.parse_warning()}")
      failed = True
    elif mtype == Gst.MessageType.ERROR:
      err = message.parse_error()
      det = message.parse_error_details()
      log(f"ERROR: {err[1]},{det}")
      failed = True
      mainloop.quit()
    elif mtype == Gst.MessageType.STATE_CHANGED:
      pass
    elif mtype == Gst.MessageType.STREAM_STATUS:
      pass
    elif mtype == Gst.MessageType.EOS:
      mainloop.quit()
    else:
      pass
#     log(f"Message: {mtype}")

  testplay = Gst.ElementFactory.make("pipeline", "testplay")
  bus = testplay.get_bus()
  bus.add_signal_watch()
  bus.connect("message", _cb_message)

  player.set_property("fvmem", FVMEM)
  player.set_property("playlist", playstr)
  player.set_property("playthroughs", 1)
  player.set_property("gpu-slot-no", 33)
  player.add_property_deep_notify_watch(None, True)

  testplay.add(player)

  vconv = Gst.ElementFactory.make("videoconvert",  None)
  vout  = Gst.ElementFactory.make("autovideosink", None)
  aconv = Gst.ElementFactory.make("audioconvert",  None)
  vol   = Gst.ElementFactory.make("volume",        None)
  aout  = Gst.ElementFactory.make("autoaudiosink", None)

  vol.set_property("volume", setvol)

  testplay.add(vconv)
  player.link(vconv)

  testplay.add(vout)
  vconv.link(vout)

  testplay.add(aconv)
  player.link(aconv)

  testplay.add(vol)
  aconv.link(vol)

  testplay.add(aout)
  vol.link(aout)

  log("Setting Playlist Swap Timer")
  if SWAP:
    GObject.timeout_add_seconds(6, cb_swap_playlists, 1)

  log("Self Test: Starting Pipeline")
  testplay.set_state(Gst.State.PLAYING)

  log("Self Test: Entering Pipeline Mainloop")
  mainloop.run()

  log(f"Self Test: Stopping Pipeline")
  testplay.set_state(Gst.State.NULL)

  log("Self Test: Ending")
  return not failed


if __name__ == '__main__':
  TEST_STATUS = test()
  RESULT = 'Succeeded' if TEST_STATUS else 'Failed'
  log(f"Self Test: {RESULT}")
