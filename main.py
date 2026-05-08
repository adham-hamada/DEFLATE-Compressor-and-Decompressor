#==============================================
#========Stage 1: LZ77 Compression=============
#==============================================

WINDOW_SIZE = 32768
MIN_MATCH = 3
MAX_MATCH = 258
MAX_CANDIDATES = 64

import math
import sys
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

                if length > best_length or (length == best_length and distance < best_distance):
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
    if not heap:
        return []
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

#==============================================================
#========Stage 4: Custom Header and Payload===================
#==============================================================
class BitWriter:
    """Accumulates bits (MSB-first) and exposes them as a bytearray."""

    def __init__(self):
        self.buffer = bytearray()
        self.current_byte = 0
        self.bits_in_byte = 0  # how many bits have been written into current_byte

    def write_bits(self, value, num_bits):
        """Write `num_bits` bits of `value`, MSB first."""
        for i in range(num_bits - 1, -1, -1):
            bit = (value >> i) & 1
            self.current_byte = (self.current_byte << 1) | bit
            self.bits_in_byte += 1
            if self.bits_in_byte == 8:
                self.buffer.append(self.current_byte)
                self.current_byte = 0
                self.bits_in_byte = 0
    def write_bit_string(self, bit_string):
        """Write a string of '0'/'1' characters (used for raw extra bits)."""
        for ch in bit_string:
            self.write_bits(int(ch), 1)
    def flush(self):        
        """Pad the last byte with zeros and flush it."""
        if self.bits_in_byte > 0:
            self.current_byte <<= (8 - self.bits_in_byte)
            self.buffer.append(self.current_byte)
            self.current_byte = 0
            self.bits_in_byte = 0
    def get_bytes(self):        return bytes(self.buffer)
def compute_bit_width(code_lengths):
    """BW = 0          if max(code_lengths) == 0
         floor(log2(M)) + 1   otherwise
    """
    M = max(code_lengths) if code_lengths else 0
    if M == 0:
        return 0
    return math.floor(math.log2(M)) + 1
def get_code_length_tables(lit_codes, dist_codes):
    lit_lengths = [0] * 286
    for symbol, (code, length) in lit_codes.items():
        lit_lengths[symbol] = length

    dist_lengths = [0] * 30
    for symbol, (code, length) in dist_codes.items():
        dist_lengths[symbol] = length

    return lit_lengths, dist_lengths
    
def stage4_compress(s3_compressed, lit_codes, dist_codes):
    """
    Produce the final compressed byte string.

    Parameters
    ----------
    s3_compressed : list
        Output of stage3_compress().
        Each element is one of:
          ('literal', symbol, huff_code, huff_len)
          ('match',   len_sym, len_extra_str,
                      dist_sym, dist_extra_str,
                      len_huff_code,  len_huff_len,
                      dist_huff_code, dist_huff_len)
          ('end',     256, huff_code, huff_len)
    lit_codes  : dict  { symbol -> (code_int, length) }
    dist_codes : dict  { symbol -> (code_int, length) }

    Returns
    -------
    bytes
    """
    lit_lengths, dist_lengths = get_code_length_tables(lit_codes, dist_codes)

    lit_bw  = compute_bit_width(lit_lengths)
    dist_bw = compute_bit_width(dist_lengths)

    bw = BitWriter()

    # ── Header ────────────────────────────────────────────────
    # LIT_BW  (4 bits)
    bw.write_bits(lit_bw, 4)
    # DIST_BW (4 bits)
    bw.write_bits(dist_bw, 4)

    # LIT_TABLE: 286 entries, each lit_bw bits wide
    for length in lit_lengths:
        bw.write_bits(length, lit_bw)

    # DIST_TABLE: 30 entries, each dist_bw bits wide (omitted when dist_bw == 0)
    if dist_bw > 0:
        for length in dist_lengths:
            bw.write_bits(length, dist_bw)

    # ── Payload ───────────────────────────────────────────────
    for item in s3_compressed:
        if item[0] == 'literal':
            _, symbol, huff_code, huff_len = item
            bw.write_bits(huff_code, huff_len)

        elif item[0] == 'match':
            (_, len_sym,  len_extra_str,
                dist_sym, dist_extra_str,
                len_huff_code,  len_huff_len,
                dist_huff_code, dist_huff_len) = item

            # Huffman(len_sym)
            bw.write_bits(len_huff_code, len_huff_len)
            # len_extra  (raw bits, may be empty string)
            bw.write_bit_string(len_extra_str)
            # Huffman(dist_sym)
            bw.write_bits(dist_huff_code, dist_huff_len)
            # dist_extra (raw bits, may be empty string)
            bw.write_bit_string(dist_extra_str)

        elif item[0] == 'end':
            _, symbol, huff_code, huff_len = item
            bw.write_bits(huff_code, huff_len)

    # Pad the last byte with zeros
    bw.flush()

    return bw.get_bytes()

def compress(data):
    """
    Run all four stages and return the final compressed bytes.

    Placeholder calls for stage functions that live in other modules:
        stage2_compress(data)       -- defined in stage 1/2 file
        stage3_compress(s2)         -- defined in stage 3 file
        get_huffman_codes(freq)     -- defined in stage 3 file
        get_frequencies(s2)         -- defined in stage 3 file
    """
    s2_compressed = stage2_compress(data)           # PLACEHOLDER: import from stage 2
    s3_compressed = stage3_compress(s2_compressed)  # PLACEHOLDER: import from stage 3

    # Rebuild the code dicts so stage4 can build the header tables
    lit_freq, dist_freq = get_frequencies(s2_compressed)   # PLACEHOLDER
    lit_codes  = get_huffman_codes(lit_freq)                # PLACEHOLDER
    dist_codes = get_huffman_codes(dist_freq)               # PLACEHOLDER

    return stage4_compress(s3_compressed, lit_codes, dist_codes)


#==============================================================
#========CLI Entry Point=======================================
#==============================================================
 
# FIX Bug 3: The original __main__ only ran a hardcoded test and had no
# argument handling.  The spec requires:
#   python main.py -c <file>   → compress, write <file>.sdfl
#   python main.py -d <file>   → decompress, write original filename
 
if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == '-c':
        input_path  = sys.argv[2]
        output_path = input_path + '.sdfl'
        with open(input_path, 'rb') as f:
            data = f.read()
        compressed = compress(data)
        with open(output_path, 'wb') as f:
            f.write(compressed)
        print(f"Compressed '{input_path}' → '{output_path}' "
              f"({len(data)} bytes → {len(compressed)} bytes)")
 
    elif len(sys.argv) == 3 and sys.argv[1] == '-d':
        input_path = sys.argv[2]
        if not input_path.endswith('.sdfl'):
            print("Error: file to decompress must have .sdfl extension", file=sys.stderr)
            sys.exit(1)
        output_path = input_path[:-5]   # strip '.sdfl'
        with open(input_path, 'rb') as f:
            data = f.read()
        # Decompressor will be implemented in a later stage
        raise NotImplementedError("Decompression (Stage 5) not yet implemented.")
 
    else:
        # ── Developer smoke-test (no arguments) ──────────────
        print("Usage: python main.py -c <file>  |  python main.py -d <file>.sdfl")
        print()
 
        data = b"abcabcabcabc"
        s1 = stage1compress(data)
        print("Stage 1:")
        for item in s1:
            if item[0] == 'literal':
                print(f"  Literal({item[1]})")
            else:
                print(f"  Match(length={item[1]}, distance={item[2]})")
 
        s2 = stage2_compress(data)
        print("\nStage 2:")
        for item in s2:
            if item[0] == 'literal':
                print(f"  LiteralEvent({item[1]})")
            elif item[0] == 'match':
                print(f"  MatchEvent({item[1]}, \"{item[2]}\", {item[3]}, \"{item[4]}\")")
            elif item[0] == 'end':
                print(f"  EndEvent({item[1]})")
 
        s3 = stage3_compress(s2)
        print("\nStage 3:")
        for item in s3:
            if item[0] == 'literal':
                print(f"  LiteralEvent({item[1]}, code={item[2]}, len={item[3]})")
            elif item[0] == 'match':
                print(f"  MatchEvent(len_sym={item[1]}, len_extra=\"{item[2]}\", "
                      f"dist_sym={item[3]}, dist_extra=\"{item[4]}\", "
                      f"len_code={item[5]}, len_bits={item[6]}, "
                      f"dist_code={item[7]}, dist_bits={item[8]})")
            elif item[0] == 'end':
                print(f"  EndEvent({item[1]}, code={item[2]}, len={item[3]})")
 
        lit_freq, dist_freq = get_frequencies(s2)
        lit_codes  = get_huffman_codes(lit_freq)
        dist_codes = get_huffman_codes(dist_freq)
        compressed = stage4_compress(s3, lit_codes, dist_codes)
 
        print(f"\nStage 4:")
        print(f"  Input : {data}")
        print(f"  Output: {compressed.hex()}")
        print(f"  Bytes : {len(compressed)} (input was {len(data)})")
 
        lit_lengths, dist_lengths = get_code_length_tables(lit_codes, dist_codes)
        print(f"  LIT_BW={compute_bit_width(lit_lengths)}, "
              f"DIST_BW={compute_bit_width(dist_lengths)}")