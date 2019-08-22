import struct
import sys
import lzma
from time import time

"""
from enum import Enum


class GameMode(Enum):
    osu       = 0
    osu_taiko = 1
    osu_catch = 2
    osu_mania = 3


class Mod(Enum):
    NoMod          = 0
    NoFail         = 1
    Easy           = 2
    NoVideo        = 4
    Hidden         = 8
    HardRock       = 16
    SuddenDeath    = 32
    DoubleTime     = 64
    Relax          = 128
    HalfTime       = 256
    Nightcore      = 512
    Flashlight     = 1024
    Autoplay       = 2048
    SpunOut        = 4096
    Autopilot      = 8192
    Perfect        = 16384
    Key4           = 32768
    Key5           = 65536
    Key6           = 131072
    Key7           = 262144
    Key8           = 524288
    keyMod         = 1015808
    FadeIn         = 1048576
    Random         = 2097152
    LastMod        = 4194304
    TargetPractice = 8388608
    Key9           = 16777216
    Coop           = 33554432
    Key1           = 67108864
    Key3           = 134217728
    Key2           = 268435456
    """


class ReplayAction(object):
    """
    Defines a replay action event.

    :param w: Time in milliseconds since the previous action.
    :param x: x-coordinate of the cursor from 0 - 512.
    :param y: y-coordinate of the cursor from 0 - 384.
    :param z: Bitwise combination of keys/mouse buttons pressed.
              (
                M1 = 1,
                M2 = 2,
                K1 = 4,
                K2 = 8,
                Smoke = 16
              )
              (
                K1 is always used with M1;
                K2 is always used with M2:
                1+4=5;
                2+8=10
              )
    """
    # Note: On replays set on version 20130319 or later,
    # the 32-bit integer RNG seed used for the score will be encoded into an additional replay frame at the end of the LZMA stream,
    # under the format -12345|0|0|seed.
    def __init__(self, w, x, y, z):
        self.time_since_previous_action = w
        self.x = x
        self.y = y
        self.keys_pressed = z


    def edit_action(self, w=None, x=None, y=None, z=None):
        """
        if w: self.time_since_previous_action = w
        if x: self.x = x
        if y: self.y = y
        if z: self.keys_pressed = z
        """
        pass


class Replay(object):
    __BYTE  = 1
    __SHORT = 2
    __INT   = 4
    __LONG  = 8
    __BOOL  = 12


    def __init__(self, replay_data):
        self.compressed_data = replay_data
        self.decompressed = None
        self.offset = 0

        self.gamemode = None
        self.osu_version = None
        self.beatmap_md5 = None
        self.username = None
        self.osu_replay_md5 = None

        self.num_300s = 0
        self.num_100s = 0
        self.num_50s = 0
        self.num_gekis = 0
        self.num_katus = 0
        self.num_misses = 0
        self.total_score = 0
        self.max_combo = 0
        self.full_combo = False
        self.mods = 0

        self.hp_graph_data = []

        self.timestamp = 0
        self.sizeof_lzma = 0

        self.online_score_id = 0

        self.play_data = []

        self.parse_replay()


    def parse_replay(self):
        self.parse_replay_headers()
        self.parse_lzma_replay() # Actual replay data
        self.create_replay_objects()


    def parse_replay_headers(self):
        self.gamemode = self.unpack_value(self.__BYTE, False)
        if self.gamemode < 0 or self.gamemode > 3: raise Exception(f"Invalid gamemode {self.gamemode}.")

        self.osu_version = self.unpack_value(self.__INT, True)

        # Strings
        self.beatmap_md5 = self.parse_string()
        self.username = self.parse_string()
        self.osu_replay_md5 = self.parse_string()

        # Score related vars.
        # TODO: calcsize properly style?
        self.num_300s = self.unpack_value(self.__SHORT, True)
        self.num_100s = self.unpack_value(self.__SHORT, True)
        self.num_50s = self.unpack_value(self.__SHORT, True)
        self.num_gekis = self.unpack_value(self.__SHORT, True)
        self.num_katus = self.unpack_value(self.__SHORT, True)
        self.num_misses = self.unpack_value(self.__SHORT, True)

        self.total_score = self.unpack_value(self.__INT, False)

        self.max_combo = self.unpack_value(self.__SHORT, True)
        self.full_combo = self.unpack_value(self.__BOOL, False)

        self.mods = self.unpack_value(self.__INT, True)

        # NOTE: This section is KNOWN to be very broke.
        _hp_graph_data = self.parse_string()
        if _hp_graph_data:
            for _ in _hp_graph_data.split('|'):
                self.hp_graph_data.append(_.split(',')) # Cursed line? also definitely improvable with some [for] magic

        self.timestamp = self.unpack_value(self.__LONG, True)
        self.sizeof_lzma = self.unpack_value(self.__INT, True)


    def unpack_value(self, data_type, unsigned=False):
        _e = None

        if data_type == self.__BOOL: _e, data_type = '?', self.__BYTE
        elif data_type == self.__BYTE: _=self.compressed_data[self.offset];self.offset += data_type;return _ # why
        elif data_type == self.__SHORT: _e = 'h'
        elif data_type == self.__INT: _e = 'l'
        elif data_type == self.__LONG: _e = 'q'
        else: raise Exception(f"Invalid datatype {data_type}.")

        if unsigned: _e = _e.upper()

        resp = struct.unpack('<'+_e, self.compressed_data[self.offset:self.offset + data_type])[0]
        self.offset += data_type
        return resp


    def parse_lzma_replay(self): # TODO: stop fucking -8ing fuck
        #if self.sizeof_lzma != len(self.compressed_data[self.offset:-8]): return 1 # Fuck

        self.decompressed = lzma.decompress(self.compressed_data[self.offset:-8], format=lzma.FORMAT_ALONE)

        self.online_score_id = struct.unpack('<q', self.compressed_data[-8:])[0]


    def decode_uleb(self, s):
        """
        This is the exact same as kszlim's __decode function in his osrparse program.

        Which can be found here:
        https://github.com/kszlim/osu-replay-parser/blob/master/osrparse/replay.py#L86-L96.
        """

        val = 0
        shift = 0
        while True:
            b = s[self.offset]
            self.offset += 1
            val = val |((b & 0b01111111) << shift)
            if (b & 0b10000000) == 0x00: break
            shift += 7
        return val


    def parse_string(self):
        if bytes([self.compressed_data[self.offset]]) == b'\x00':
            self.offset += self.__BYTE
            return
        elif bytes([self.compressed_data[self.offset]]) == b'\x0b':
            self.offset += self.__BYTE

            string_length = self.decode_uleb(self.compressed_data)
            offset_end = self.offset + string_length

            val = self.compressed_data[self.offset:offset_end].decode("utf-8", "ignore")
            self.offset = offset_end
            return val
        else:
            raise Exception(f"Failed to parse string. {bytes([self.compressed_data[self.offset]])}")


    def create_replay_objects(self):
        for replay_action in self.decompressed.decode("ascii").split(',')[:-1]: # Last replayaction is cursed3
            w, x, y, z = replay_action.split('|')
            self.play_data.append(ReplayAction(w, x, y, z))


    def save_replay_headerless(self, replay_file):
        with open("NH - [" + str(replay_file.split('\\')[-1].split('.osr')[0]) + "].osr", "wb+") as f:
            f.write(self.compressed_data[self.offset:-8]) # TODO: -8 do properly yada yada


if __name__ == "__main__":
    # todo: move this debug? wtf?
    debug = True

    for replay in sys.argv[1:]:
        start_time = time()

        with open(replay, "rb") as f:
            _r = f.read()

        r = Replay(_r)

        r.save_replay_headerless(replay)
        end_time = time()
        if debug: print(f"{r.__dict__}\n\n")

        print('%.2fms' % round((end_time - start_time) * 1000, 2))