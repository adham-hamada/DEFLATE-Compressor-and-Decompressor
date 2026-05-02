WINDOW_SIZE = 32768
MIN_MATCH = 3
MAX_MATCH = 258
MAX_CANDIDATES = 64

import numpy as np

sliding_window = np.zeros(WINDOW_SIZE, dtype=np.uint8)
current_pos = 0

def reset_state():
    global sliding_window, current_pos
    sliding_window[:] = 0
    current_pos = 0

def literal(byte):
    global current_pos
    sliding_window[current_pos] = byte
    current_pos = (current_pos + 1) % WINDOW_SIZE
    return byte

def match(length, distance):
    global current_pos
    match_data = []
    for _ in range(length):
        byte = sliding_window[(current_pos - distance) % WINDOW_SIZE]
        match_data.append(byte)
        sliding_window[current_pos] = byte
        current_pos = (current_pos + 1) % WINDOW_SIZE
    return match_data

def compress(data):
    reset_state()
    table = {}
    def add_to_table(pos):
        if pos + MIN_MATCH <= len(data):
                key = (data[pos], data[pos + 1], data[pos + 2])
                if key not in table:
                    table[key] = []
                table[key].append(pos)
    compressed_data = []
    i = 0

    while i < len(data):
        best_length = 0
        best_distance = 0
        if i + MIN_MATCH <= len(data):
            key = (data[i], data[i + 1], data[i + 2])
            candidates = table.get(key, [])
            for candidate in candidates[-MAX_CANDIDATES:]:
                distance = i - candidate
                if distance <= 0 or distance > WINDOW_SIZE:
                    continue
                length = 0
                max_len = min(MAX_MATCH, len(data) - i)
                while length < max_len and data[candidate + length] == data[i + length]:
                    length += 1

                if length > best_length:
                    best_length = length
                    best_distance = distance

        if best_length >= MIN_MATCH:
            compressed_data.append(('match', best_length, best_distance))
            for j in range(best_length):
                add_to_table(i + j)
                literal(data[i + j])
            i += best_length
        else:
            compressed_data.append(('literal', data[i]))
            add_to_table(i)
            literal(data[i])
            i += 1

    return compressed_data

def decompress(compressed_data):
    reset_state()
    decompressed_data = []
    for item in compressed_data:
        if item[0] == 'literal':
            decompressed_data.append(item[1])
            literal(item[1])
        elif item[0] == 'match':
            length, distance = item[1], item[2]
            match_data = match(length, distance)
            decompressed_data.extend(match_data)
    return bytes(decompressed_data)

