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

#==============================================================
#========Stage 3: Canonical Huffman Coding=====================
#==============================================================

def get_frequencies(s2_compressed):
    lit_freq = [0] * 286
    dist_freq = [0] * 30
    for item in s2_compressed:
        if item[0] == 'literal':
            lit_freq[item[1]] += 1
        elif item[0] == 'match':
            lit_freq[item[1]] += 1   
            dist_freq[item[3]] += 1  
        elif item[0] == 'end':
            lit_freq[item[1]] += 1
    return lit_freq, dist_freq

def build_huffman_tree(freq):
    import heapq
    heap = [(w, s, [[s, ""]]) for s, w in enumerate(freq) if w > 0]
    heapq.heapify(heap)
    while len(heap) > 1:
        w1, m1, p1 = heapq.heappop(heap)
        w2, m2, p2 = heapq.heappop(heap)
        for pair in p1: pair[1] = '0' + pair[1]
        for pair in p2: pair[1] = '1' + pair[1]
        heapq.heappush(heap, (w1 + w2, min(m1, m2), p1 + p2))
    return sorted(heap[0][2], key=lambda x: (len(x[1]), x[0]))

def get_huffman_lengths(freq):
    tree = build_huffman_tree(freq)
    if not tree:
        return [0] * len(freq)
    lengths = [0] * len(freq)
    for symbol, code in tree:
        lengths[symbol] = max(len(code), 1)
    return lengths

def get_huffman_codes(freq):
    lengths = get_huffman_lengths(freq)
    count = [0] * 16
    for length in lengths:
        count[length] += 1
    count[0] = 0
    next_code = [0] * 16
    code = 0
    for bits in range(1, 16):
        code = (code + count[bits - 1]) << 1
        next_code[bits] = code
    symbol_code = {}
    for symbol in range(len(lengths)):
        length = lengths[symbol]
        if length != 0:
            symbol_code[symbol] = (next_code[length], length)  # return (code, length)
            next_code[length] += 1
    return symbol_code

def stage3_compress(s2_compressed):
    lit_freq, dist_freq = get_frequencies(s2_compressed)
    lit_codes = get_huffman_codes(lit_freq)
    dist_codes = get_huffman_codes(dist_freq)
    s3_compressed = []
    for item in s2_compressed:
        if item[0] == 'literal':
            code, length = lit_codes[item[1]]
            s3_compressed.append(('literal', item[1], code, length))
        elif item[0] == 'match':
            len_sym, len_extra, dist_sym, dist_extra = item[1], item[2], item[3], item[4]
            length_huff_code, length_huff_len = lit_codes[len_sym]
            dist_huff_code, dist_huff_len = dist_codes[dist_sym]
            s3_compressed.append((
                'match',
                len_sym, len_extra,
                dist_sym, dist_extra,
                length_huff_code, length_huff_len,
                dist_huff_code, dist_huff_len
            ))
        elif item[0] == 'end':
            code, length = lit_codes[item[1]]
            s3_compressed.append(('end', item[1], code, length))
    return s3_compressed

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
    s3_compressed = stage3_compress(s2_compressed)
    print("\nStage 3 Compressed Data:")
    for item in s3_compressed:
        if item[0] == 'literal':
            print(f"LiteralEvent({item[1]}, code={item[2]}, length={item[3]})")
        elif item[0] == 'match':
            print(f"MatchEvent(len_sym={item[1]}, len_extra=\"{item[2]}\", dist_sym={item[3]}, dist_extra=\"{item[4]}\", length_code={item[5]}, length_bits={item[6]}, dist_code={item[7]}, dist_bits={item[8]})")
        elif item[0] == 'end':
            print(f"EndEvent({item[1]}, code={item[2]}, length={item[3]})")