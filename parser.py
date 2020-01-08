from typing import Any, Optional, List
import struct
import sys
import lzma
from time import time, sleep

class ReplayAction(object):
    """
    Defines a replay action event.

    :param w: Time in milliseconds since the previous action.
    :param x: x-coordinate of the cursor from 0 - 512.
    :param y: y-coordinate of the cursor from 0 - 384.
    :param z: Bitwise combination of keys/mouse buttons pressed.

    K1 & K2 are used with M1 & M2 respectively.
    M1:     1
    M2:     2
    K1:     4
    K2:     8
    Smoke: 16
    """
    # Note: on replays set on version 20130319 or later,
    # the 32-bit integer rng seed used for the score will be
    # encoded into an additional replay frame at the end of
    # the lzma stream, under the format -12345|0|0|seed.
    def __init__(self, w: int, x: int, y: int, z: int) -> None:
        self.time_since_previous_action = w
        self.x = x
        self.y = y
        self.keys_pressed = z


    def edit_action(self, time_since_previous_action: Optional[int] = None, x: Optional[int] = None, y: Optional[int] = None, keys_pressed: Optional[int] = None):
        """
        if w: self.time_since_previous_action = w
        if x: self.x = x
        if y: self.y = y
        if z: self.keys_pressed = z
        """
        pass


class Replay(object):
    _BOOL:   int = 0
    _BYTE:   int = 1
    _SHORT:  int = 2
    _INT:    int = 4
    _LONG:   int = 8
    _USHORT: int = 16
    _UINT:   int = 32
    _ULONG:  int = 64


    def __init__(self, replay_data: bytes) -> None:
        self.compressed_data = replay_data
        self.decompressed: Optional[bytes]  = None
        self.offset: int = 0

        self.gamemode: Optional[int]  = None
        self.osu_version: Optional[int] = None
        self.beatmap_md5: Optional[str] = None
        self.username: Optional[str] = None
        self.osu_replay_md5: Optional[str] = None

        self.num_300s: int = 0
        self.num_100s: int = 0
        self.num_50s: int = 0
        self.num_gekis: int = 0
        self.num_katus: int = 0
        self.num_misses: int = 0
        self.total_score: int = 0
        self.max_combo: int = 0
        self.full_combo: bool = False
        self.mods: int = 0

        self.hp_graph_data: List[str] = []

        self.timestamp: int = 0
        self.sizeof_lzma: int = 0

        self.online_score_id: int = 0

        self.play_data: List[ReplayAction] = []

        self.parse_replay()


    def parse_replay(self) -> None:
        self.parse_replay_headers()
        self.parse_lzma_replay() # Actual replay data
        self.create_replay_objects()


    def parse_replay_headers(self) -> None:
        self.gamemode = self.unpack_value(self._BYTE)
        if self.gamemode < 0 or self.gamemode > 3: raise Exception(f'Invalid gamemode {self.gamemode}')

        self.osu_version = self.unpack_value(self._UINT)

        # Strings
        self.beatmap_md5 = self.parse_string()
        self.username = self.parse_string()
        self.osu_replay_md5 = self.parse_string()

        # Score related vars.
        # TODO: calcsize properly style?
        self.num_300s = self.unpack_value(self._USHORT)
        self.num_100s = self.unpack_value(self._USHORT)
        self.num_50s = self.unpack_value(self._USHORT)
        self.num_gekis = self.unpack_value(self._USHORT)
        self.num_katus = self.unpack_value(self._USHORT)
        self.num_misses = self.unpack_value(self._USHORT)

        self.total_score = self.unpack_value(self._INT)

        self.max_combo = self.unpack_value(self._USHORT)
        self.full_combo = self.unpack_value(self._BOOL)

        self.mods = self.unpack_value(self._UINT)

        # NOTE: This section is KNOWN to be very broke.
        _hp_graph_data: str = self.parse_string()
        if _hp_graph_data:
            for i in _hp_graph_data.split('|'):
                self.hp_graph_data.append(i.split(','))

        self.timestamp = self.unpack_value(self._ULONG)
        self.sizeof_lzma = self.unpack_value(self._UINT)


    def unpack_value(self, data_type: int) -> Any:
        _e = None

        if not data_type: _e, data_type = '?', self._BYTE # bool
        elif data_type == self._BYTE: _ = self.compressed_data[self.offset]; self.offset += data_type; return _
        elif data_type == self._SHORT: _e = 'h'
        elif data_type == self._INT: _e = 'l'
        elif data_type == self._LONG: _e = 'q'
        else: raise Exception(f'Invalid datatype {data_type}')

        if data_type in [self._USHORT, self._UINT, self._ULONG]: _e = _e.upper()

        resp = struct.unpack('<' + _e, self.compressed_data[self.offset:self.offset + data_type])[0]
        self.offset += data_type
        return resp


    def parse_lzma_replay(self) -> None:
        #if self.sizeof_lzma != len(self.compressed_data[self.offset:-8]): return 1 # Fuck

        self.decompressed = lzma.decompress(self.compressed_data[self.offset:-8], format = lzma.FORMAT_ALONE)
        self.online_score_id = struct.unpack('<q', self.compressed_data[-self._LONG:])[0]
        return

    def decode_uleb(self, s: bytes) -> int:
        """
        This is the exact same as kszlim's __decode function in his osrparse program.

        Which can be found here:
        https://github.com/kszlim/osu-replay-parser/blob/master/osrparse/replay.py#L86-L96.
        """

        val: int = 0
        shift: int = 0

        while True:
            b: str = s[self.offset]
            self.offset += 1
            val: int = val |((b & 0b01111111) << shift)
            if (b & 0b10000000) == 0x00: break
            shift += 7

        return val


    def parse_string(self) -> Optional[bytes]:
        if self.compressed_data[self.offset] == 0:
            self.offset += self._BYTE
            return

        elif self.compressed_data[self.offset] == 11:
            self.offset += self._BYTE

            string_length: int = self.decode_uleb(self.compressed_data)
            offset_end: int = self.offset + string_length

            val: str = self.compressed_data[self.offset:offset_end].decode('utf-8', 'ignore')
            self.offset = offset_end
            return val
        else:
            raise Exception(f'Failed to parse string. {bytes([self.compressed_data[self.offset]])}')


    def create_replay_objects(self) -> None:
        for replay_action in self.decompressed.decode('ascii').split(',')[:-1]:

            _split: List[int] = [int(i) for i in replay_action.split('|')]
            w: int = _split[0]
            x: int = _split[1]
            y: int = _split[2]
            z: int = _split[3]

            self.play_data.append(ReplayAction(w, x, y, z))


    def save_replay_headerless(self, replay_file: str) -> None:
        with open('NH - [' + replay_file.split('\\')[-1].split('.osr')[0] + '].osr', 'wb+') as f:
            f.write(self.compressed_data[self.offset:-self._LONG])


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        raise Exception("Invalid syntax.\npython3.6 parser.py <list of replay files, separated by a space>")

    for replay_file in sys.argv[1:]:
        _start = time()

        with open(replay_file, 'rb') as f:
            replay = Replay(f.read())

        replay.save_replay_headerless(replay_file)
        print(f'{1000. * (time() - _start):.2f}')
