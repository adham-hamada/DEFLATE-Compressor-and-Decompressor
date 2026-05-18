# ======== Stage 1: LZ77 Compression =========
#
# LZ77 is a lossless data compression algorithm. Instead of storing every byte
# as-is, it looks for repeated sequences of bytes that already appeared earlier
# in the data. When it finds a repeat, it stores a short "pointer" back to the
# earlier occurrence (as a distance + length pair) rather than the bytes
# themselves. This is the first stage of the DEFLATE compression pipeline.

import os
from utilities.util_1 import *

def stage1compress(data):
    """
    Compress a byte sequence using the LZ77 algorithm.

    Args:
        data: A sequence of bytes (e.g. a bytes object or list of ints 0-255).

    Returns:
        A list of tuples, where each tuple is either:
          - ('literal', byte_value)  — a single byte stored as-is
          - ('match', length, distance) — a back-reference meaning
              "go back 'distance' bytes and copy 'length' bytes from there"
    """

    # Reset the global sliding window 
    reset_state()

    # Hash table for fast lookups: maps a 3-byte tuple to a list of positions
    table = {}

    def add_to_table(pos):
        if pos + MIN_MATCH <= len(data):
            # Use the next 3 bytes as a hash key (MIN_MATCH == 3)
            key = (data[pos], data[pos + 1], data[pos + 2])
            if key not in table:
                table[key] = []
            table[key].append(pos)

    # The output list: will contain ('literal', ...) and ('match', ...) tuples.
    compressed_data = []
    i = 0

    while i < len(data):
        best_length = 0
        best_distance = 0

        # Only try to find a match if there are at least MIN_MATCH (3) bytes
        if i + MIN_MATCH <= len(data):
            key = (data[i], data[i + 1], data[i + 2])
            candidates = table.get(key, [])

            # Check the most recent candidates (up to MAX_CANDIDATES).
            for candidate in candidates[-MAX_CANDIDATES:]:

                # Distance = how far back the candidate is from current position
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

        # --- Emit output ---
        if best_length >= MIN_MATCH:
            compressed_data.append(('match', best_length, best_distance))

            for j in range(best_length):
                add_to_table(i + j)
                literal(data[i + j])

            # Advance past the entire matched region
            i += best_length

        else:
            # No match found — emit the byte as a literal (stored as-is).
            compressed_data.append(('literal', data[i]))
            add_to_table(i)
            literal(data[i])  # Feed the byte into the sliding window
            i += 1

    return compressed_data

if __name__ == "__main__":

    # Path to the sample test data
    data_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'data', 'data_1.txt'
    )

    with open(data_path, 'rb') as f: 
        data = f.read()

    print(f"=== Stage 1: LZ77 Compression ===")
    print(f"Input file : {os.path.basename(data_path)}")
    print(f"Input size : {len(data)} bytes")
    print()

    # Run the compressor
    compressed = stage1compress(data)

    # Count literals vs matches
    num_literals = sum(1 for item in compressed if item[0] == 'literal')
    num_matches  = sum(1 for item in compressed if item[0] == 'match')

    # Print each token
    for idx, item in enumerate(compressed):
        if item[0] == 'literal':
            byte_val = item[1]
            char = chr(byte_val) if 32 <= byte_val < 127 else f'\\x{byte_val:02x}'
            print(f"  [{idx:4d}] LITERAL  byte={byte_val:3d}  char='{char}'")
        else:
            print(f"  [{idx:4d}] MATCH    length={item[1]:3d}  distance={item[2]:5d}")

    print()
    print(f"--- Summary ---")
    print(f"  Total tokens : {len(compressed)}")
    print(f"  Literals     : {num_literals}")
    print(f"  Matches      : {num_matches}")

    # Estimate: each literal = 1 byte stored, each match = (length, distance) pointer
    original_size = len(data)
    # A rough estimate of compressed size (not the real bitstream, just for intuition)
    estimated_size = num_literals * 1 + num_matches * 3  # ~1 byte per literal, ~3 bytes per match
    print(f"  Original size       : {original_size} bytes")
    print(f"  Estimated output    : {estimated_size} bytes (rough)")
    print(f"  Estimated ratio     : {estimated_size / original_size:.2%}")