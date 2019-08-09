def remove_replay_headers(replayFile, debug=False):
    """
    A function used to remove a replay's headers, and take just the LZMA data.

    :param replayFile: The directory to the replay file.
    :return 1: Failed to remove replay headers.
    :return 0: Successfully removed replay headers.
    """
    import lzma, struct

    # Constant data types.
    __BYTE  = 1
    __SHORT = 2
    __INT   = 4
    __LONG  = 8

    # Variable types.
    offset  = 0

    with open(replayFile, "rb") as replay_with_headers:
        data = replay_with_headers.read()
        #data = replay_with_headers.read()[:-8] # ScoreID is stored at the end of the of replay file, as a long.

    game_mode = data[offset]
    offset += __BYTE

    #if Gamemode > 4 or Gamemode < 0: return 1 # Broke gamemode?

    osu_version = struct.unpack('<l', data[offset:offset + __INT])[0]; offset += __INT

    _exists = data[offset]; offset += __BYTE

    if _exists == 11: # Beatmap MD5 exists. Process it then add to offset.
        offset_end = offset + data[offset] + __BYTE
        offset += __BYTE

        beatmap_md5 = data[offset:offset_end].decode('utf-8', 'ignore')
        if debug: print(f"Beatmap MD5: {beatmap_md5}")
        offset = offset_end
        del offset_end
    elif not _exists:
        pass
    else:
        return 1
    del _exists

    _exists = data[offset]
    offset += __BYTE
    if _exists == 11: # Username
        offset_end = offset + data[offset] + __BYTE
        offset += __BYTE

        username = data[offset:offset_end].decode('utf-8', 'ignore') # Set the username
        if debug: print(f"Username: {username}")

        offset = offset_end
        del offset_end
    elif not _exists:
        pass
    else:
        return 1
    del _exists

    _exists = data[offset]
    offset += __BYTE
    if _exists == 11: # osu! replay MD5 hash.
        offset_end = offset + data[offset] + __BYTE; offset += __BYTE

        osu_replay_md5 = data[offset:offset_end].decode('utf-8', 'ignore')
        offset = offset_end
        del offset_end
    elif not _exists:
        pass
    else:
        return 1
    del _exists

    # Unpack a lot of 2/4 byte vars.
    num300s   = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    num100s   = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    num50s    = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    numGekis  = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    numKatus  = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    numMisses = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    TotalScore = struct.unpack('<L', data[offset:offset + __INT])[0]; offset += __INT
    GreatestCombo = struct.unpack('<H', data[offset:offset + __SHORT])[0]; offset += __SHORT
    FullCombo = bool(data[offset]); offset += __BYTE
    Mods = struct.unpack('<L', data[offset:offset + __INT])[0]; offset += __INT

    # Debug print.
    if debug: print(f"300s: {num300s}\n100s: {num100s}\n50s: {num50s}\nGekis: {numGekis}\nKatus: {numKatus}\nMisses: {numMisses}\nTotal score: {TotalScore}\nGreatest combo: {GreatestCombo}\nFC: {FullCombo}\nMods:{Mods}")

    #TODO: stuck lol
    #print(f"\nWHERE THE FUCK ARE WE CHECK!\n\n{data[offset-20:offset+20]}\n\n")
    #for why in data[offset:offset+100]:print(why)
    #return

    _exists = data[offset]; offset += __BYTE

    print(f"HP BAR EXISTENCE???? : {_exists}")
    if _exists == 11: # Life bar graph
        print(f"STEP 2??? {data[offset]}")
        # this one is tricky
        offset_end = offset + data[offset] + __BYTE; offset += __BYTE
        print(data[offset])

        _HP = data[offset:offset_end].decode('utf-8', 'ignore')
        print(f"HP: {_HP}")
        offset = offset_end
        del offset_end
    elif not _exists:
        pass
    else:
        return 1
    del _exists
    print(f"F OFFSET: {offset}")

    timestamp = struct.unpack('<Q', data[offset:offset + __LONG])[0]; offset += __LONG
    if debug: print(f"time_stamp: {timestamp}")

    # TODO: this im eager to moveon to re[lay data yeah]
    replay_data_length = struct.unpack('<L', data[offset:offset + __INT])[0];offset += __INT
    if debug: print(f"sizeof_lzma: {replay_data_length}")

    online_score_id = struct.unpack('<Q', data[-8:])[0];#offset += __LONG
    if debug: print(f"online_score_id: {online_score_id}")

    if replay_data_length != len(data[offset:-8]): return 1 # Fuck

    decompressed = lzma.decompress(data[offset:-8])

    """
    #print(data)

    print(f"Using offset: {offset}")

    for i in range(offset, len(data) // 5): # I dont wanna learn uleb rn im too high
        try: decompressed = lzma.decompress(data[i:])
        except lzma.LZMAError: continue
        break
    """

    if not decompressed: return 1

    # TODO: check replay name for scoreid.
    # if scoreid just overwrite the old file to keep the name.
    with open("NH - [{}].osr".format(replayFile.split('\\')[-1]), "wb") as replay_without_headers:
        replay_without_headers.write(lzma.compress(decompressed))

    return 0

if __name__ == "__main__":
    """
    If we're running our program directly, let's take argv[1:] (all params passed by user after calling script).
    This will allow the user to drag files into replay.py, and let it iterate through all params given.
    """
    import sys
    from time import time

    for replay in sys.argv[1:]:
        start_time = time()

        if remove_replay_headers(replay, True): print("Failed - " + str(replay.split('\\')[-1]))
        else: print(f"Success - {int((time() - start_time) * 1000)}ms")

    input("Press enter to exit..")