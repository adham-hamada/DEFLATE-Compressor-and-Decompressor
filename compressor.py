import sys
import os

# Add the stages directory to the path so we can import stage modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stages'))

from stage1 import stage1compress
from stage2 import stage2_compress
from stage3 import stage3_compress
from stage4 import stage4_compress
from utilities.util_3 import get_frequencies, get_huffman_codes
from utilities.util_4 import get_code_length_tables, compute_bit_width


def compress(data):
    """
    Run all four DEFLATE compression stages and return the final compressed bytes.

    Pipeline: Raw bytes → LZ77 → DEFLATE Symbols → Huffman Coding → Bitstream
    """
    # Stage 1: LZ77 — find repeated sequences
    s1_compressed = stage1compress(data)

    # Stage 2: Convert raw lengths/distances to DEFLATE symbols + extra bits
    s2_compressed = stage2_compress(s1_compressed)

    # Stage 3: Build canonical Huffman codes and attach them to tokens
    lit_freq, dist_freq = get_frequencies(s2_compressed)
    lit_codes = get_huffman_codes(lit_freq)
    dist_codes = get_huffman_codes(dist_freq)
    s3_compressed = stage3_compress(s2_compressed)

    # Stage 4: Pack header + payload into final byte sequence
    return stage4_compress(s3_compressed, lit_codes, dist_codes)


if __name__ == "__main__":

    # Use data_2.txt as the demo file
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'data_2.txt')
    with open(data_path, 'rb') as f:
        data = f.read()

    print(f"{'='*60}")
    print(f"  DEFLATE Compression Demo — {os.path.basename(data_path)}")
    print(f"  Original size: {len(data):,} bytes ({len(data)/1024:.1f} KB)")
    print(f"{'='*60}")

    # ── Stage 1: LZ77 ──
    print(f"\n{'─'*60}")
    print(f"  Stage 1: LZ77 Pattern Detection")
    print(f"{'─'*60}")
    s1 = stage1compress(data)
    num_literals = sum(1 for x in s1 if x[0] == 'literal')
    num_matches = sum(1 for x in s1 if x[0] == 'match')
    print(f"  Tokens     : {len(s1):,}")
    print(f"  Literals   : {num_literals:,}")
    print(f"  Matches    : {num_matches:,}")
    # Show first 5 tokens as sample
    print(f"  Sample tokens:")
    for item in s1[:5]:
        if item[0] == 'literal':
            byte_val = item[1]
            char = chr(byte_val) if 32 <= byte_val < 127 else f'\\x{byte_val:02x}'
            print(f"    Literal({byte_val}) = '{char}'")
        else:
            print(f"    Match(length={item[1]}, distance={item[2]})")
    if len(s1) > 5:
        print(f"    ... ({len(s1) - 5} more tokens)")

    # ── Stage 2: DEFLATE Symbols ──
    print(f"\n{'─'*60}")
    print(f"  Stage 2: DEFLATE Symbols and Extra Bits")
    print(f"{'─'*60}")
    s2 = stage2_compress(s1)
    s2_literals = sum(1 for x in s2 if x[0] == 'literal')
    s2_matches = sum(1 for x in s2 if x[0] == 'match')
    s2_end = sum(1 for x in s2 if x[0] == 'end')
    print(f"  Events     : {len(s2):,}")
    print(f"  Literals   : {s2_literals:,} (symbols 0–255)")
    print(f"  Matches    : {s2_matches:,} (length symbols 257–285, distance symbols 0–29)")
    print(f"  End marker : {s2_end} (symbol 256)")
    # Show first 5 events as sample
    print(f"  Sample events:")
    for item in s2[:5]:
        if item[0] == 'literal':
            print(f"    LiteralEvent({item[1]})")
        elif item[0] == 'match':
            print(f"    MatchEvent({item[1]}, \"{item[2]}\", {item[3]}, \"{item[4]}\")")
        elif item[0] == 'end':
            print(f"    EndEvent({item[1]})")
    if len(s2) > 5:
        print(f"    ... ({len(s2) - 5} more events)")

    # ── Stage 3: Huffman Coding ──
    print(f"\n{'─'*60}")
    print(f"  Stage 3: Canonical Huffman Coding")
    print(f"{'─'*60}")
    lit_freq, dist_freq = get_frequencies(s2)
    lit_codes = get_huffman_codes(lit_freq)
    dist_codes = get_huffman_codes(dist_freq)
    s3 = stage3_compress(s2)

    print(f"  Lit/Length symbols used : {len(lit_codes)}")
    print(f"  Distance symbols used  : {len(dist_codes)}")

    # Show Huffman code table
    print(f"  Literal/Length Huffman codes:")
    sorted_lit = sorted(lit_codes.keys())
    for sym in sorted_lit[:10]:
        code, bits = lit_codes[sym]
        code_bin = format(code, f'0{bits}b')
        freq = lit_freq[sym]
        if sym < 256:
            char = chr(sym) if 32 <= sym < 127 else f'\\x{sym:02x}'
            label = f"literal '{char}'"
        elif sym == 256:
            label = "end-of-block"
        else:
            label = "length code"
        print(f"    sym={sym:3d} ({label:16s}) freq={freq:5d}  code={code_bin} ({bits} bits)")
    if len(sorted_lit) > 10:
        print(f"    ... ({len(sorted_lit) - 10} more symbols)")

    if dist_codes:
        print(f"  Distance Huffman codes:")
        sorted_dist = sorted(dist_codes.keys())
        for sym in sorted_dist[:8]:
            code, bits = dist_codes[sym]
            code_bin = format(code, f'0{bits}b')
            freq = dist_freq[sym]
            print(f"    sym={sym:2d}  freq={freq:5d}  code={code_bin} ({bits} bits)")
        if len(sorted_dist) > 8:
            print(f"    ... ({len(sorted_dist) - 8} more symbols)")

    # Compute Huffman bit cost
    total_huff_bits = 0
    for item in s3:
        if item[0] == 'literal':
            total_huff_bits += item[3]
        elif item[0] == 'match':
            total_huff_bits += item[6]
            total_huff_bits += len(item[2]) if item[2] else 0
            total_huff_bits += item[8]
            total_huff_bits += len(item[4]) if item[4] else 0
        elif item[0] == 'end':
            total_huff_bits += item[3]
    fixed_bits = len(s2) * 9
    print(f"  Huffman payload bits : {total_huff_bits:,} ({(total_huff_bits+7)//8:,} bytes)")
    print(f"  Fixed 9-bit encoding: {fixed_bits:,} ({(fixed_bits+7)//8:,} bytes)")
    print(f"  Huffman savings     : {fixed_bits - total_huff_bits:,} bits")

    # ── Stage 4: Bitstream Packing ──
    print(f"\n{'─'*60}")
    print(f"  Stage 4: Custom Header and Bitstream Packing")
    print(f"{'─'*60}")
    compressed = stage4_compress(s3, lit_codes, dist_codes)

    lit_lengths, dist_lengths = get_code_length_tables(lit_codes, dist_codes)
    lit_bw = compute_bit_width(lit_lengths)
    dist_bw = compute_bit_width(dist_lengths)
    header_bits = 4 + 4 + (286 * lit_bw) + (30 * dist_bw if dist_bw > 0 else 0)

    print(f"  LIT_BW  = {lit_bw} bits per code length")
    print(f"  DIST_BW = {dist_bw} bits per code length")
    print(f"  Header  : {header_bits:,} bits ({(header_bits+7)//8:,} bytes)")
    print(f"  Output  : {len(compressed):,} bytes")

    # Write the compressed file
    output_path = data_path + '.sdfl'
    with open(output_path, 'wb') as f:
        f.write(compressed)

    # ── Final Summary ──
    ratio = len(compressed) / len(data) * 100
    print(f"\n{'='*60}")
    print(f"  COMPRESSION SUMMARY")
    print(f"{'='*60}")
    print(f"  Original    : {len(data):,} bytes ({len(data)/1024:.1f} KB)")
    print(f"  Compressed  : {len(compressed):,} bytes ({len(compressed)/1024:.1f} KB)")
    print(f"  Ratio       : {ratio:.1f}%")
    print(f"  Space saved : {len(data) - len(compressed):,} bytes ({100 - ratio:.1f}%)")
    print(f"  Output file : {os.path.basename(output_path)}")
    print(f"{'='*60}")