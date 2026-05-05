#==============================================
#========Stage 1: LZ77 Compression=============
#==============================================

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

def stage1compress(data):
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


#==============================================================
#========Stage 2: DEFLATE Symbols and Extra Bits===============
#==============================================================


length_base = [
3, 4, 5, 6, 7, 8, 9, 10,
11, 13, 15, 17,
19, 23, 27, 31,
35, 43, 51, 59,
67, 83, 99, 115,
131, 163, 195, 227,
258
]

length_extra = [
0, 0, 0, 0, 0, 0, 0, 0,
1, 1, 1, 1,
2, 2, 2, 2,
3, 3, 3, 3,
4, 4, 4, 4,
5, 5, 5, 5,
0
]

def get_length_symbol(length):
    for i in range(len(length_base)):
        if length >= length_base[i] and length <= length_base[i] + pow(2,length_extra[i]) - 1:
            length_symbol = i + 257
            return length_symbol, encode_extra_bits(length - length_base[i], length_extra[i])
        
distance_base = [
1, 2, 3, 4,
5, 7,
9, 13,
17, 25,
33, 49,
65, 97,
129, 193,
257, 385,
513, 769,
1025, 1537,
2049, 3073,
4097, 6145,
8193, 12289,
16385, 24577
]

distance_extra = [
0, 0, 0, 0,
1, 1,
2, 2,
3, 3, 
4, 4,
5, 5, 
6, 6,
7, 7, 
8, 8,
9, 9, 
10, 10,
11, 11, 
12, 12,
13, 13
]

def get_distance_symbol(distance):
    for i in range(len(distance_base)):
        if distance <= (distance_base[i] + pow(2,distance_extra[i]) - 1) and distance >= distance_base[i]:
            distance_symbol = i
            return distance_symbol, encode_extra_bits(distance - distance_base[i], distance_extra[i])
        
def encode_extra_bits(bits , num_bits):
    if num_bits == 0:
        return ''
    return format(bits, '0' + str(num_bits) + 'b')

def stage2_compress(data):
    s1_compressed = stage1compress(data)
    s2_compressed = []
    for item in s1_compressed:
        if item[0] == 'literal':
            s2_compressed.append(('literal', item[1]))
        elif item[0] == 'match':
            length_symbol, length_extra_bits = get_length_symbol(item[1])
            distance_symbol, distance_extra_bits = get_distance_symbol(item[2])
            s2_compressed.append(('match', length_symbol, length_extra_bits, distance_symbol, distance_extra_bits))
    s2_compressed.append(('end',256))
    return s2_compressed

# Example usage
if __name__ == "__main__":
    data = b"abcabcabcabc"
    s1_compressed = stage1compress(data)
    print("Stage 1 Compressed Data:")
    for item in s1_compressed:
        if item[0] == 'literal':
            print(f"Literal({item[1]})")
        elif item[0] == 'match':
            print(f"Match(length={item[1]}, distance={item[2]})")
    s2_compressed = stage2_compress(data)
    print("\nStage 2 Compressed Data:")
    for item in s2_compressed:
        if item[0] == 'literal':
            print(f"LiteralEvent({item[1]})")
        elif item[0] == 'match':
            print(f"MatchEvent({item[1]}, \"{item[2]}\", {item[3]}, \"{item[4]}\")")
        elif item[0] == 'end':
            print(f"EndEvent({item[1]})")