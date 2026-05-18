import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stages'))

from utilities.util_decompressor import *
from utilities.util_2 import *


def decompress(compressed_data):
    """
    Decompress bytes produced by compress().

    Mirrors the compressor in reverse:
      1. Read LIT_BW and DIST_BW  (first 8 bits = 1 byte)
      2. Read 286 literal/length code lengths
      3. Read 30 distance code lengths
      4. Rebuild Huffman lookup tables from those lengths
      5. Decode payload symbols until EndEvent(256)
         - symbol 0-255   -> emit that byte directly
         - symbol 256     -> stop
         - symbol 257-285 -> read extra bits + distance symbol + extra bits,
                             then copy bytes from earlier in the output
    """
    reader = BitReader(compressed_data)

    # ── Step 1: Read the two 4-bit bit-widths from the header ─
    lit_bw  = reader.read_bits(4)
    dist_bw = reader.read_bits(4)

    # ── Step 2: Read literal/length code-length table ─────────
    # 286 entries; entry i = how many bits the code for symbol i uses
    lit_lengths = []
    for _ in range(286):
        if lit_bw == 0:
            lit_lengths.append(0)          # no lit codes at all (shouldn't happen)
        else:
            lit_lengths.append(reader.read_bits(lit_bw))

    # ── Step 3: Read distance code-length table ───────────────
    # 30 entries; if dist_bw == 0 there are no distance symbols (pure literals)
    dist_lengths = []
    for _ in range(30):
        if dist_bw == 0:
            dist_lengths.append(0)
        else:
            dist_lengths.append(reader.read_bits(dist_bw))

    # ── Step 4: Rebuild canonical Huffman lookup tables ────────
    # The compressor stored only lengths.  Because canonical Huffman is
    # deterministic, the same lengths always produce the same codes.
    lit_codes  = build_decode_table(lit_lengths)
    dist_codes = build_decode_table(dist_lengths)

    # ── Step 5: Decode the payload ────────────────────────────
    output = bytearray()

    while True:

        # Read one literal/length symbol
        symbol = decode_symbol(reader, lit_codes)

        if 0 <= symbol <= 255:
            # ── Case A: literal byte ──────────────────────────
            # The symbol value IS the byte — write it straight out
            output.append(symbol)

        elif symbol == 256:
            # ── Case B: end marker ────────────────────────────
            break

        else:
            # ── Case C: match — symbol 257-285 ───────────────

            # Decode the exact match length
            # symbol 257 = index 0, symbol 258 = index 1, etc.
            idx              = symbol - 257
            base_len         = length_base[idx]
            num_len_extra    = length_extra[idx]
            len_extra_val    = reader.read_bits(num_len_extra) if num_len_extra > 0 else 0
            actual_length    = base_len + len_extra_val

            # Decode the exact match distance
            dist_symbol      = decode_symbol(reader, dist_codes)
            base_dist        = distance_base[dist_symbol]
            num_dist_extra   = distance_extra[dist_symbol]
            dist_extra_val   = reader.read_bits(num_dist_extra) if num_dist_extra > 0 else 0
            actual_distance  = base_dist + dist_extra_val

            # LZ77 copy — byte by byte so overlapping matches work correctly
            # e.g. distance=1, length=9 repeats the last byte 9 times
            for _ in range(actual_length):
                copy_pos = len(output) - actual_distance
                output.append(output[copy_pos])

    return bytes(output)


if __name__ == "__main__":

    # ── Locate the compressed file ────────────────────────────────────
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'data_2.txt')
    compressed_path = data_path + '.sdfl'

    if not os.path.exists(compressed_path):
        print(f"Error: compressed file not found: {compressed_path}")
        print("Run compressor.py first to generate the .sdfl file.")
        sys.exit(1)

    # ── Read the compressed bytes ─────────────────────────────────────
    with open(compressed_path, 'rb') as f:
        compressed_data = f.read()

    print(f"{'='*60}")
    print(f"  DEFLATE Decompression Demo — {os.path.basename(compressed_path)}")
    print(f"  Compressed size: {len(compressed_data):,} bytes ({len(compressed_data)/1024:.1f} KB)")
    print(f"{'='*60}")

    # ── Decompress ────────────────────────────────────────────────────
    decompressed = decompress(compressed_data)

    # ── Verify against original ───────────────────────────────────────
    if os.path.exists(data_path):
        with open(data_path, 'rb') as f:
            original = f.read()
        match = decompressed == original
        status = "PASS" if match else "FAIL"
    else:
        original = None
        match = None
        status = "? (original not found)"

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  Decompression Results")
    print(f"{'─'*60}")
    print(f"  Compressed   : {len(compressed_data):,} bytes")
    print(f"  Decompressed : {len(decompressed):,} bytes")
    if original is not None:
        print(f"  Original     : {len(original):,} bytes")
    print(f"  Integrity    : {status}")
    print(f"{'='*60}")