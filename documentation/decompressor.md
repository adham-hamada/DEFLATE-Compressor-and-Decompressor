# DEFLATE Decompressor

A single-pass decompressor that reverses the 4-stage DEFLATE compression pipeline, reconstructing the original data from a `.sdfl` compressed file. Fully documented for educational purposes.

---

## How Decompression Works

The compressor transforms data through 4 stages:

```
Raw bytes → LZ77 → DEFLATE Symbols → Huffman Coding → Bitstream
```

The decompressor **reverses the entire pipeline in a single pass** — it reads the bitstream left-to-right, rebuilds the Huffman tables from the header, and decodes symbols back into the original bytes on the fly:

```
Bitstream → Huffman Decoding → Symbol Interpretation → LZ77 Replay → Raw bytes
```

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Decompression Pipeline                             │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐        │
│  │ Step 1   │───▶│ Step 2-3 │───▶│ Step 4   │───▶│ Step 5   │        │
│  │ Read     │    │ Read     │    │ Rebuild  │    │ Decode   │        │
│  │ Header   │    │ Code     │    │ Huffman  │    │ Payload  │        │
│  │ Widths   │    │ Lengths  │    │ Tables   │    │ Symbols  │        │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘        │
│                                                                      │
│  Compressed bytes ──▶ Code lengths ──▶ Lookup tables ──▶ Raw bytes   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Breakdown

### Step 1 — Read Header Bit-Widths

**Goal:** Learn how many bits each code-length entry uses.

The first byte of the compressed stream contains two 4-bit values packed together:

| Field | Bits | Meaning |
|---|---|---|
| `LIT_BW` | 4 | Bits per literal/length code-length entry |
| `DIST_BW` | 4 | Bits per distance code-length entry |

These tell the decompressor the fixed width used to store each entry in the code-length tables that follow.

```
Byte 0:  [ LIT_BW (4 bits) | DIST_BW (4 bits) ]
```

**Example:** If `LIT_BW = 4` and `DIST_BW = 3`, then each literal code-length is stored in 4 bits and each distance code-length in 3 bits.

---

### Steps 2–3 — Read Code-Length Tables

**Goal:** Reconstruct the Huffman code lengths for every symbol.

Immediately after the header, the bitstream contains two tables of code lengths:

| Table | Entries | Purpose |
|---|---|---|
| Literal/Length | 286 | Code lengths for symbols 0–285 (literals 0–255, end-of-block 256, length codes 257–285) |
| Distance | 30 | Code lengths for distance symbols 0–29 |

Each entry is read as a fixed-width integer using `LIT_BW` or `DIST_BW` bits respectively. A code length of 0 means that symbol does not appear in the compressed data.

```
Header:  [LIT_BW][DIST_BW]
         ├── 286 × LIT_BW bits ──┤── 30 × DIST_BW bits ──┤
         │   lit_lengths[0..285]  │  dist_lengths[0..29]   │
```

**Special case:** If `DIST_BW = 0`, the compressed data contains only literal bytes (no LZ77 matches were found).

---

### Step 4 — Rebuild Canonical Huffman Tables

**Goal:** Turn code lengths into a lookup table for bit-by-bit decoding.

Because the compressor uses **canonical Huffman codes**, the code lengths alone are sufficient to reconstruct the exact same codes — no tree structure needs to be transmitted. The algorithm:

1. **Count** how many symbols have each code length
2. **Compute** the first code value for each length (starting from the shortest)
3. **Assign** codes to symbols in ascending symbol order within each length group

The result is a lookup dictionary mapping `(code_integer, num_bits) → symbol`.

| What the compressor stored | What the decompressor rebuilds |
|---|---|
| `lengths = [0, 0, ..., 3, 4, 3, ...]` | `{(0b010, 3): 32, (0b0110, 4): 101, ...}` |

**Why canonical codes work:** Given the same set of code lengths, there is exactly one valid assignment of binary codes. Both compressor and decompressor independently produce identical codes from the same lengths — no explicit code table needs to be transmitted.

**Files:** `stages/utilities/util_decompressor.py` → `build_decode_table()`

---

### Step 5 — Decode Payload Symbols

**Goal:** Read Huffman-coded symbols from the bitstream and reconstruct the original data.

The decompressor reads bits one at a time, accumulating them into a code. After each bit, it checks the Huffman lookup table — prefix-free codes guarantee the first match is always correct.

Each decoded symbol falls into one of three cases:

#### Case A: Literal (symbol 0–255)

The symbol value **is** the byte. Write it directly to the output buffer.

```
Symbol 65  →  output.append(65)  →  byte 'A'
```

#### Case B: End-of-Block (symbol 256)

Stop decoding. The compressed stream is complete.

#### Case C: LZ77 Match (symbol 257–285)

The symbol encodes a **back-reference**: copy bytes from earlier in the output buffer.

Decoding a match requires reading 4 pieces of information:

| Piece | Source | Purpose |
|---|---|---|
| Length symbol | Huffman-decoded from lit/length table | Base index into length lookup table |
| Length extra bits | Raw bits from stream | Fine-tune the exact length within the range |
| Distance symbol | Huffman-decoded from distance table | Base index into distance lookup table |
| Distance extra bits | Raw bits from stream | Fine-tune the exact distance within the range |

```
length  = length_base[symbol - 257]  + read_bits(length_extra[symbol - 257])
distance = distance_base[dist_symbol] + read_bits(distance_extra[dist_symbol])
```

Then copy `length` bytes starting from `output[-distance]`:

```
output = "ABCABC"
Match: length=3, distance=6  →  copy output[-6], output[-5], output[-4]  →  "ABC"
Result: "ABCABCABC"
```

**Overlapping matches:** The copy is done byte-by-byte so that matches with `distance < length` work correctly. For example, `distance=1, length=5` repeats the last byte 5 times — each copied byte becomes available for the next copy.

**Files:** `stages/utilities/util_decompressor.py` → `decode_symbol()`, `stages/utilities/util_2.py` → `length_base`, `length_extra`, `distance_base`, `distance_extra`

---

## Utilities

### `util_decompressor.py`

| Component | Purpose |
|---|---|
| `BitReader` | Reads bits one at a time from a byte string (MSB first). Mirror of the compressor's `BitWriter`. |
| `build_decode_table(lengths)` | Rebuilds canonical Huffman codes from code lengths. Returns `{(code, bits): symbol}` lookup dict. |
| `decode_symbol(reader, table)` | Reads bits from the stream, accumulating into a code, until a valid Huffman symbol is matched. |

### `util_2.py` (shared with compressor)

| Component | Purpose |
|---|---|
| `length_base[29]` | Base match length for each length symbol (257–285). E.g. symbol 257 → length 3. |
| `length_extra[29]` | Number of extra bits for each length symbol. E.g. symbol 265 → 1 extra bit. |
| `distance_base[30]` | Base distance for each distance symbol (0–29). E.g. symbol 0 → distance 1. |
| `distance_extra[30]` | Number of extra bits for each distance symbol. E.g. symbol 4 → 1 extra bit. |

---

## Project Structure

```
DEFLATE-Compressor-and-Decompressor/
├── compressor.py                 ← 4-stage compression pipeline
├── decompressor.py               ← Single-pass decompression (this README)
├── README_compressor.md          ← Compressor documentation
├── README_decompressor.md        ← You are here
├── data/
│   └── data_2.txt                ← Sample test data
└── stages/
    └── utilities/
        ├── util_2.py             ← Length/distance lookup tables (shared)
        └── util_decompressor.py  ← BitReader, Huffman decode helpers
```

---

## Quick Start

```bash
# Step 1: Compress a file first (creates data_2.txt.sdfl)
python3 compressor.py

# Step 2: Decompress and verify integrity
python3 decompressor.py
```

Expected output:

```
============================================================
  DEFLATE Decompression Demo — data_2.txt.sdfl
  Compressed size: XXX bytes (X.X KB)
============================================================

────────────────────────────────────────────────────────────
  Decompression Results
────────────────────────────────────────────────────────────
  Compressed   : XXX bytes
  Decompressed : XXX bytes
  Original     : XXX bytes
  Integrity    : PASS
============================================================
```

---

## Compressor vs. Decompressor

| Aspect | Compressor | Decompressor |
|---|---|---|
| Stages | 4 separate stages | Single pass |
| Huffman | Builds tree from frequencies | Rebuilds from stored code lengths |
| LZ77 | Searches for matches in sliding window | Replays matches from output buffer |
| Output | Compressed `.sdfl` bytes | Original raw bytes |
| Complexity | O(n × w) where w = window size | O(n) linear scan |

The decompressor is simpler because it doesn't need to search — the compressor already did the hard work of finding patterns and building optimal codes. The decompressor just follows the instructions encoded in the bitstream.

---
