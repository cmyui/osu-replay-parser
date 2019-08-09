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


class ReplayAction(object):
    ###
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
    ###
    # Note: On replays set on version 20130319 or later,
    # the 32-bit integer RNG seed used for the score will be encoded into an additional replay frame at the end of the LZMA stream,
    # under the format -12345|0|0|seed.
    def __init__(self, w, x, y, z):
        self.time_since_previous_action = w
        self.x = x
        self.y = y
        self.keys_pressed = z

    def edit_action(self, w=None, x=None, y=None, z=None):
        if w: self.time_since_previous_action = w
        if x: self.x = x
        if y: self.y = y
        if z: self.keys_pressed = z
"""

class Replay(object):
    __BYTE  = 1
    __SHORT = 2
    __INT   = 4
    __LONG  = 8

    def __init__(self, replay_data, replay_file):
        self.compressed_data = replay_data
        self.replay_file = "NH - [" + str(replay_file.split('\\')[-1].split('.osr')[0]) + "].osr"
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

        self.initialize_fields()


    def initialize_fields(self):
        from time import time

        self.parse_main_variables() # gamemode & osu_version
        self.parse_main_strings() # beatmap_md5 - osu_replay_md5
        self.parse_score_variables() # num300 - mods
        self.parse_secondary_variables() # HP

        self.parse_lzma_replay() # Actual replay data

    def parse_main_variables(self):
        import struct

        # Set gamemode.
        _gamemode = self.compressed_data[self.offset]
        if _gamemode < 0 or _gamemode > 3: raise Exception(f"Invalid gamemode {_gamemode}.")
        self.gamemode = _gamemode
        self.offset += self.__BYTE

        # Unpack osu version.
        _osu_version = struct.unpack('<l', self.compressed_data[self.offset:self.offset + self.__INT])[0]
        if type(_osu_version) is not int: raise Exception(f"Invalid osu! version {_osu_version}.")
        self.osu_version = _osu_version
        self.offset += self.__INT


    def parse_main_strings(self):
        import struct

        self.beatmap_md5 = self.parse_string()
        self.username = self.parse_string()
        self.osu_replay_md5 = self.parse_string()


    def parse_score_variables(self):
        import struct

        # TODO: unsafe?
        self.num_300s = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.num_100s = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.num_50s = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.num_gekis = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.num_katus = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.num_misses = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.total_score = struct.unpack('<l', self.compressed_data[self.offset:self.offset + self.__INT])[0]; self.offset += self.__INT
        self.max_combo = struct.unpack('<h', self.compressed_data[self.offset:self.offset + self.__SHORT])[0]; self.offset += self.__SHORT
        self.full_combo = self.compressed_data[self.offset]; self.offset += self.__BYTE
        self.mods = struct.unpack('<l', self.compressed_data[self.offset:self.offset + self.__INT])[0]; self.offset += self.__INT


    def parse_secondary_variables(self):
        import struct

        # NOTE: This section is KNOWN to be very broke.
        _hp_graph_data = self.parse_string()
        if _hp_graph_data:
            for _ in _hp_graph_data.split("|"): self.hp_graph_data.append(_) # Cursed line? also definitely improvable with some [for] magic

        self.timestamp = struct.unpack('<q', self.compressed_data[self.offset:self.offset + self.__LONG])[0]; self.offset += self.__LONG
        self.sizeof_lzma = struct.unpack('<l', self.compressed_data[self.offset:self.offset + self.__INT])[0]; self.offset += self.__INT


    def parse_lzma_replay(self):
        import struct, lzma

        #if self.sizeof_lzma != len(self.compressed_data[self.offset:-8]): return 1 # Fuck

        self.decompressed = lzma.decompress(self.compressed_data[self.offset:-8], format=lzma.FORMAT_ALONE)

        self.online_score_id = struct.unpack('<q', self.compressed_data[-8:])[0]


    def parse_string(self):
        exists = False
        if bytes([self.compressed_data[self.offset]]) == b'\x0b': exists = True
        self.offset += self.__BYTE
        if not exists: return
        offset_end = self.offset + self.compressed_data[self.offset] + self.__BYTE; self.offset += self.__BYTE

        val = self.compressed_data[self.offset:offset_end].decode("utf-8", "ignore")
        self.offset = offset_end
        return val

    def save_replay_headerless(self):
        import lzma
        with open(self.replay_file, "wb+") as f:
            f.write(lzma.compress(self.decompressed, format=lzma.FORMAT_ALONE)) # SUBOPTIMAL AS FUCK! we don't need to re-lzma.. this is literally making the program x10 slower

if __name__ == "__main__":
    import sys
    from time import time

    debug = False

    for replay in sys.argv[1:]:
        start_time = time()
        with open(replay, "rb") as f:
            r = Replay(f.read(), replay)

        # getch?
        end_time = time()

        r.save_replay_headerless()
        if debug: print(f"{r.__dict__}\n\n")

        print('%.2fms' % round(end_time - start_time * 1000, 2))