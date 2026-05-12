# Stage 4: Custom Header and Bitstream Packing

## Table of Contents

1. [What Problem Does This Solve?](#what-problem-does-this-solve)
2. [The Core Idea — Packing Bits into Bytes](#the-core-idea--packing-bits-into-bytes)
3. [The Compressed File Format](#the-compressed-file-format)
4. [Worked Example — Writing a Compressed File](#worked-example--writing-a-compressed-file)
5. [The BitWriter — How Bits Become Bytes](#the-bitwriter--how-bits-become-bytes)
6. [How the Code Works — Line by Line](#how-the-code-works--line-by-line)
7. [Decompression — How to Read It Back](#decompression--how-to-read-it-back)
8. [Header Overhead and Efficiency](#header-overhead-and-efficiency)
9. [Where This Fits in DEFLATE](#where-this-fits-in-deflate)

---

## What Problem Does This Solve?

After Stage 3, we have a stream of tokens with Huffman codes attached. For example:

```
('literal', 101, 0b0010, 4)    → 'e' encoded as 4 bits: 0010
('match', 257, '', 3, '', 0b0101, 4, 0b1100, 4)  → 8 bits total
('end', 256, 0b1111000, 7)     → end marker as 7 bits: 1111000
```

But these are still Python objects in memory. **We need to turn them into actual bytes** — a sequence of 0s and 1s packed into a file that can be saved to disk and later decompressed.

There are two challenges:

1. **The decompressor needs the Huffman trees.** The Huffman codes were built from the frequency distribution of *this specific file*. The decompressor hasn't seen the original file, so it doesn't know the frequencies. We need to include the tree information in the file itself — this is the **header**.

2. **Huffman codes don't align with bytes.** A code might be 3 bits, 5 bits, or 7 bits long. But files are made of 8-bit bytes. We need to pack these variable-length codes tightly, with no gaps, and handle the leftover bits at the end.

---

## The Core Idea — Packing Bits into Bytes

Consider three Huffman codes: `0010` (4 bits), `0101` (4 bits), and `1111000` (7 bits). Written sequentially:

```
Bits:  0 0 1 0 | 0 1 0 1 | 1 1 1 1 0 0 0
       ------    ------    -----------
       code 1    code 2    code 3
```

That's 15 bits total. But a file stores 8-bit bytes. So we pack them like this:

```
Byte 1: 0 0 1 0 0 1 0 1    = 0x25
Byte 2: 1 1 1 1 0 0 0 [0]  = 0xF0  (last bit is padding)
```

The `[0]` at the end is **padding** — we add zero bits to fill the last byte. The decompressor knows to stop when it reads the end-of-block marker (symbol 256), so the padding bits are never interpreted as data.

---

## The Compressed File Format

Our compressed file has two sections: a **header** and a **payload**.

```
┌────────────────────────────────────────────────────────────┐
│                    COMPRESSED FILE                         │
│                                                            │
│  ┌──────────────────────────────────────┐                  │
│  │              HEADER                  │                  │
│  │                                      │                  │
│  │  ┌──────────┬──────────┐             │                  │
│  │  │ LIT_BW   │ DIST_BW  │  (4+4 bits) │                  │
│  │  └──────────┴──────────┘             │                  │
│  │  ┌───────────────────────────┐       │                  │
│  │  │ LIT_TABLE (286 entries)   │       │                  │
│  │  │ each LIT_BW bits wide     │       │                  │
│  │  └───────────────────────────┘       │                  │
│  │  ┌───────────────────────────┐       │                  │
│  │  │ DIST_TABLE (30 entries)   │       │                  │
│  │  │ each DIST_BW bits wide    │       │                  │
│  │  └───────────────────────────┘       │                  │
│  └──────────────────────────────────────┘                  │
│                                                            │
│  ┌──────────────────────────────────────┐                  │
│  │              PAYLOAD                 │                  │
│  │                                      │                  │
│  │  Huffman codes + extra bits          │                  │
│  │  packed tightly, bit by bit          │                  │
│  │  ...ends with Huffman(256)...        │                  │
│  │                               [pad]  │                  │
│  └──────────────────────────────────────┘                  │
└────────────────────────────────────────────────────────────┘
```

### The Header

The header stores everything the decompressor needs to rebuild the Huffman trees:

| Field | Size | Purpose |
|---|---|---|
| LIT_BW | 4 bits | Bit width of each literal/length code length entry |
| DIST_BW | 4 bits | Bit width of each distance code length entry |
| LIT_TABLE | 286 × LIT_BW bits | Code lengths for all 286 literal/length symbols |
| DIST_TABLE | 30 × DIST_BW bits | Code lengths for all 30 distance symbols (omitted if DIST_BW = 0) |

**Why store code lengths instead of the full tree?**

Because of **canonical Huffman codes** (Stage 3). As long as the compressor and decompressor agree on the code lengths, they can both independently generate the exact same codes using the canonical algorithm. Lengths are much more compact than a full tree structure.

**Why LIT_BW and DIST_BW?**

Code lengths are small integers (typically 3–7). Instead of using a full 8-bit byte per length, we compute the minimum bit width needed. If the longest code is 7 bits, LIT_BW = 3 (since 3 bits can represent 0–7). This saves significant space: 286 × 3 = 858 bits instead of 286 × 8 = 2,288 bits.

### The Payload

After the header, the actual compressed data follows — a continuous stream of Huffman codes and extra bits:

| Token Type | What is Written |
|---|---|
| Literal | `Huffman(symbol)` |
| Match | `Huffman(len_sym)` + `len_extra` + `Huffman(dist_sym)` + `dist_extra` |
| End | `Huffman(256)` |

No separators, no alignment — everything is packed tightly. The decompressor reads bit by bit, using the Huffman tree to determine where each code ends.

---

## Worked Example — Writing a Compressed File

Let's trace the compression of a simple token stream using these Huffman codes:

**Lit/Length codes:** `'e'(101) → 0010 (4 bits)`, `256 → 1111000 (7 bits)`, `257 → 0101 (4 bits)`

**Distance codes:** `3 → 1100 (4 bits)`

**Code lengths:** lit max = 7, so LIT_BW = 3. dist max = 4, so DIST_BW = 3.

### Step 1: Write the Header

```
LIT_BW  = 3 → write 4 bits: 0011
DIST_BW = 3 → write 4 bits: 0011
```

Then write 286 lit/length code lengths, each 3 bits:
```
sym 0:   000 (length 0, not used)
sym 1:   000
...
sym 101: 100 (length 4, for 'e')
...
sym 256: 111 (length 7, end marker)
sym 257: 100 (length 4, length code)
...
sym 285: 000
```

Then write 30 distance code lengths, each 3 bits:
```
sym 0: 000
...
sym 3: 100 (length 4)
...
sym 29: 000
```

### Step 2: Write the Payload

For input tokens: `('literal', 'e')`, `('match', len=3, dist=3)`, `('end')`:

```
Literal 'e':  write Huffman code 0010           (4 bits)
Match:        write Huffman(257) = 0101         (4 bits)
              write len_extra = '' (empty)      (0 bits)
              write Huffman(dist 3) = 1100      (4 bits)
              write dist_extra = '' (empty)     (0 bits)
End:          write Huffman(256) = 1111000      (7 bits)
```

### Step 3: Flush

Total payload bits: 4 + 4 + 4 + 7 = 19 bits. Needs 3 bytes. Last byte gets 5 bits of padding:

```
Byte 1: 0010 0101  (literal 'e' + first half of match)
Byte 2: 1100 1111  (distance + first 4 bits of end)
Byte 3: 000 00000  (remaining 3 bits of end + 5 padding zeros)
```

---

## The BitWriter — How Bits Become Bytes

The `BitWriter` class in `utilities/util_4.py` handles all the bit-level packing. It works like a funnel — bits pour in one at a time and complete bytes pour out.

```
Input:  write_bits(0b0010, 4)   write_bits(0b0101, 4)   write_bits(0b11, 2)
                ↓                       ↓                       ↓
Internal:  [0,0,1,0]  →  [0,0,1,0,0,1,0,1]  →  FLUSH byte!  →  [1,1, ...]
                              ↓
Output:  buffer = [0x25, ...]
```

**Key methods:**

| Method | What It Does |
|---|---|
| `write_bits(value, num_bits)` | Writes `num_bits` bits of `value`, MSB first. Automatically flushes complete bytes. |
| `write_bit_string(bit_string)` | Writes a string like `'01101'` as individual bits. Used for extra bits from Stage 2. |
| `flush()` | Pads the current partial byte with zeros on the right and pushes it to the buffer. |
| `get_bytes()` | Returns the final byte sequence. |

**MSB-first order:** When writing the value `5` (binary `101`) with 3 bits, the `1` is written first, then `0`, then `1`. This is the standard reading order — most significant bit first.

---

## How the Code Works — Line by Line

### Helper Functions in `utilities/util_4.py`

#### `compute_bit_width(code_lengths)`

```python
M = max(code_lengths)      # Find the longest code length
return floor(log2(M)) + 1  # Minimum bits to represent M
```

Example: if the longest Huffman code is 7 bits, M = 7, log₂(7) ≈ 2.81, floor = 2, +1 = **3 bits** per entry.

#### `get_code_length_tables(lit_codes, dist_codes)`

Converts the Huffman code dictionaries (sparse — only symbols with freq > 0) into flat arrays (dense — all 286 or 30 entries, with 0 for absent symbols). The header needs the flat format because the decompressor reads entries by position.

### Main Function: `stage4_compress()` in `stage4.py`

#### Writing the Header

```python
bw.write_bits(lit_bw, 4)      # 4 bits: how wide each lit code length is
bw.write_bits(dist_bw, 4)     # 4 bits: how wide each dist code length is

for length in lit_lengths:     # 286 entries
    bw.write_bits(length, lit_bw)

if dist_bw > 0:               # Only if there are distance codes
    for length in dist_lengths:  # 30 entries
        bw.write_bits(length, dist_bw)
```

The `if dist_bw > 0` check handles the case where the input has no matches (pure literals). If DIST_BW is 0, the decompressor knows there's no distance table.

#### Writing the Payload

```python
if item[0] == 'literal':
    bw.write_bits(huff_code, huff_len)          # Just the Huffman code

elif item[0] == 'match':
    bw.write_bits(len_huff_code, len_huff_len)  # Huffman(length symbol)
    bw.write_bit_string(len_extra_str)          # Length extra bits (raw)
    bw.write_bits(dist_huff_code, dist_huff_len) # Huffman(distance symbol)
    bw.write_bit_string(dist_extra_str)          # Distance extra bits (raw)

elif item[0] == 'end':
    bw.write_bits(huff_code, huff_len)          # Huffman(256)
```

A match is **always** 4 parts in this exact order. The decompressor knows this — when it reads a length symbol (257–285), it immediately reads the extra bits, then the distance code, then the distance extra bits.

#### Finalizing

```python
bw.flush()              # Pad the last byte
return bw.get_bytes()   # Return the compressed bytes
```

---

## Decompression — How to Read It Back

The decompressor does the exact reverse:

### Step 1: Read the Header

```
1. Read 4 bits → LIT_BW
2. Read 4 bits → DIST_BW
3. Read 286 × LIT_BW bits → lit_lengths array
4. If DIST_BW > 0: read 30 × DIST_BW bits → dist_lengths array
5. Rebuild Huffman trees from the lengths using canonical code generation
```

### Step 2: Decode the Payload

```
Loop:
  1. Read bits from the lit/length Huffman tree until a valid code is found
  2. If symbol is 0–255 → output the literal byte
  3. If symbol is 256 → stop (end of block)
  4. If symbol is 257–285 → it's a match:
     a. Read the extra bits for the length (from the length_extra table)
     b. Read bits from the distance Huffman tree until a valid code
     c. Read the extra bits for the distance
     d. Copy `length` bytes from `distance` bytes ago in the output
```

The decompressor doesn't need to know the file size in advance — it keeps reading until it encounters symbol 256 (end-of-block).

---

## Header Overhead and Efficiency

The header is a fixed cost — it doesn't grow with the input size. Let's look at the numbers:

| Component | Formula | Our Example |
|---|---|---|
| LIT_BW | 4 bits | 4 bits |
| DIST_BW | 4 bits | 4 bits |
| LIT_TABLE | 286 × LIT_BW | 286 × 3 = 858 bits |
| DIST_TABLE | 30 × DIST_BW | 30 × 3 = 90 bits |
| **Total Header** | | **956 bits (120 bytes)** |

For our 377-byte test file, the header is 120 bytes — that's 52% of the total compressed file (229 bytes). The payload is only 109 bytes.

**This is why DEFLATE doesn't compress small files well.** The header overhead is fixed, so for small files it dominates. For larger files (kilobytes or megabytes), the header becomes negligible.

### Ways to Reduce Header Size

Our header format is simple but not optimal. Real DEFLATE uses several tricks:

1. **Run-length encoding of code lengths** — many symbols have length 0 (not used), so consecutive zeros are compressed
2. **A third Huffman tree** — the code lengths themselves are Huffman-coded (a tree of trees!)
3. **HLIT/HDIST counters** — only store code lengths up to the last non-zero entry, not all 286/30

These optimizations can reduce the header from ~120 bytes to ~20-30 bytes, but add complexity. Our format prioritizes simplicity and clarity.

---

## Where This Fits in DEFLATE

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DEFLATE Pipeline                              │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│  │ Stage 1  │───▶│ Stage 2  │───▶│ Stage 3  │───▶│ Stage 4  │        │
│  │  LZ77    │    │ DEFLATE  │    │ Huffman  │    │ Bitstream│        │
│  │          │    │ Symbols  │    │ Coding   │    │ Packing  │        │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│                                                                      │
│  Raw bytes ──▶ Literals/Matches ──▶ Symbol codes ──▶ Huffman ──▶     │
│                                     + extra bits    codes     bits   │
└──────────────────────────────────────────────────────────────────────┘
```

- **Stage 1 (LZ77):** Finds repeated sequences → outputs literals and back-references
- **Stage 2 (Symbols):** Converts raw lengths/distances into compact symbol codes + extra bits
- **Stage 3 (Huffman):** Assigns variable-length binary codes based on frequency
- **Stage 4 (this stage):** Packs the header and coded data into the final byte sequence

Stage 4 is where the compression becomes *real* — everything before this stage was logical transformation (Python objects). This stage converts those objects into the actual bytes that make up the compressed file.

### End-to-End Example

```
Original:    "ABCABCABC"                              (9 bytes)
After LZ77:  [L(A), L(B), L(C), M(6,3)]              (4 tokens)
After S2:    [L(65), L(66), L(67), M(260,'',2,'')]    (4 tokens + end)
After S3:    [L(65,code,bits), ..., end(256,code,bits)] (tokens with Huffman codes)
After S4:    0x33 0x00 ... 0xE0 0x00                  (final compressed bytes)
```

The journey from 9 human-readable bytes to a compact binary blob is complete. The decompressor reads these bytes and perfectly reconstructs the original "ABCABCABC" — not a single byte lost.

---
