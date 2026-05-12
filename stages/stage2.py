# ======== Stage 2: DEFLATE Symbols and Extra Bits =========
#
# This stage converts the LZ77 output (literals and raw length/distance matches)
# into DEFLATE-standard symbol codes with extra bits.
#
# WHY IS THIS NEEDED?
# Stage 1 (LZ77) produces matches like ('match', length=15, distance=100).
# But DEFLATE doesn't store "15" and "100" directly — that would waste bits on
# rare large values. Instead, it uses a clever two-part encoding:
#
#   1. A SYMBOL — a small code representing a range (e.g., "lengths 15–16").
#      Symbols are what get Huffman-coded in Stage 3 for maximum compression.
#
#   2. EXTRA BITS — raw binary bits that narrow down the exact value within
#      that range. These are NOT Huffman-coded; they're appended as-is.
#
# This means common small values get compact codes, and rare large values
# use more bits — a form of variable-length encoding.

import os
from utilities.util_2 import *
from stage1 import stage1compress

def stage2_compress(data):
    """
    Run Stage 1 (LZ77) on raw data, then convert the output into
    DEFLATE symbol codes with extra bits.

    Args:
        data: Raw byte sequence to compress.

    Returns:
        A list of tuples, where each tuple is one of:
          - ('literal', byte_value)
                A raw byte (0–255), passed through unchanged.

          - ('match', length_symbol, length_extra, distance_symbol, distance_extra)
                length_symbol:  DEFLATE symbol 257–285 representing the match length
                length_extra:   Binary string with extra precision bits (e.g., '01')
                distance_symbol: DEFLATE symbol 0–29 representing the match distance
                distance_extra:  Binary string with extra precision bits

          - ('end', 256)
                End-of-block marker. Symbol 256 tells the decompressor to stop.
    """
    # Run LZ77 compression first to get literals and matches
    s1_compressed = stage1compress(data)
    s2_compressed = []

    for item in s1_compressed:
        if item[0] == 'literal':
            # Literals pass through unchanged — they're already valid DEFLATE
            # symbols (byte values 0–255 map directly to symbols 0–255).
            s2_compressed.append(('literal', item[1]))

        elif item[0] == 'match':
            # Convert the raw length (3–258) into a symbol (257–285) + extra bits
            length_symbol, length_extra_bits = get_length_symbol(item[1])
            # Convert the raw distance (1–32768) into a symbol (0–29) + extra bits
            distance_symbol, distance_extra_bits = get_distance_symbol(item[2])
            s2_compressed.append(('match', length_symbol, length_extra_bits, distance_symbol, distance_extra_bits))

    # Append the end-of-block marker (DEFLATE symbol 256).
    s2_compressed.append(('end', 256))
    return s2_compressed


if __name__ == "__main__":

    # Path to the sample test data
    data_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'data', 'data_1.txt'
    )

    with open(data_path, 'rb') as f:
        data = f.read()

    print(f"=== Stage 2: DEFLATE Symbols and Extra Bits ===")
    print(f"Input file : {os.path.basename(data_path)}")
    print(f"Input size : {len(data)} bytes")
    print()

    # Run Stage 2 (which internally runs Stage 1 first)
    compressed = stage2_compress(data)

    # Count each token type
    num_literals = sum(1 for item in compressed if item[0] == 'literal')
    num_matches  = sum(1 for item in compressed if item[0] == 'match')
    num_end      = sum(1 for item in compressed if item[0] == 'end')

    # Print each token
    for idx, item in enumerate(compressed):
        if item[0] == 'literal':
            byte_val = item[1]
            char = chr(byte_val) if 32 <= byte_val < 127 else f'\\x{byte_val:02x}'
            print(f"  [{idx:4d}] LITERAL   symbol={byte_val:3d}  char='{char}'")

        elif item[0] == 'match':
            len_sym, len_extra, dist_sym, dist_extra = item[1], item[2], item[3], item[4]
            extra_info = ""
            if len_extra:
                extra_info += f"  len_extra='{len_extra}'"
            if dist_extra:
                extra_info += f"  dist_extra='{dist_extra}'"
            print(f"  [{idx:4d}] MATCH     len_sym={len_sym:3d}  dist_sym={dist_sym:2d}{extra_info}")

        elif item[0] == 'end':
            print(f"  [{idx:4d}] END       symbol={item[1]}")

    print()
    print(f"--- Summary ---")
    print(f"  Total tokens : {len(compressed)}")
    print(f"  Literals     : {num_literals}  (symbols 0–255)")
    print(f"  Matches      : {num_matches}  (length symbols 257–285, distance symbols 0–29)")
    print(f"  End marker   : {num_end}  (symbol 256)")