# DEFLATE Compressor and Decompressor

A 4-stage implementation of the DEFLATE compression algorithm, built from scratch for educational purposes. Each stage is fully documented with detailed explanations for someone with no prior background.

---

## What is DEFLATE?

DEFLATE is a **lossless compression algorithm** defined in [RFC 1951](https://tools.ietf.org/html/rfc1951). It combines two complementary techniques — **LZ77** (pattern matching) and **Huffman coding** (entropy coding) — to compress data efficiently. It is the core algorithm behind **gzip**, **ZIP**, and **PNG**.

---

## The Pipeline

Data flows through 4 stages, each transforming it into a more compact representation:

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

---

## Stage Summaries

### Stage 1 — LZ77 Compression

**Goal:** Eliminate repeated sequences in the data.

LZ77 slides a window over the input and asks: *"Have I seen these bytes before?"* If yes, it emits a **back-reference** `(length, distance)` instead of storing the bytes again. If no, it emits the raw byte as a **literal**.

| Input | Output |
|---|---|
| `ABCABCABC` (9 bytes) | `L(A) L(B) L(C) M(6,3)` (3 literals + 1 match) |

**Key parameters:** 32 KB sliding window, minimum match length = 3, max match length = 258.

**Files:** `stages/stage1.py`, `stages/utilities/util_1.py`

📖 [Full documentation →](documentation/stage1.md)

---

### Stage 2 — DEFLATE Symbols and Extra Bits

**Goal:** Convert raw lengths and distances into compact symbol codes.

DEFLATE doesn't store raw length/distance values directly — there are too many possible values (256 lengths × 32,768 distances). Instead, it groups similar values into **ranges**, assigns each range a small **symbol code**, and uses a few **extra bits** to pinpoint the exact value within that range.

| What | Before (raw) | After (symbol + extra bits) |
|---|---|---|
| Length 15 | `15` | Symbol 267 + extra `'0'` |
| Distance 100 | `100` | Symbol 13 + extra `'00011'` |

**Result:** 29 length symbols (257–285) and 30 distance symbols (0–29) — small enough for Huffman coding to work efficiently.

**Files:** `stages/stage2.py`, `stages/utilities/util_2.py`

📖 [Full documentation →](documentation/stage2.md)

---

### Stage 3 — Canonical Huffman Coding

**Goal:** Assign shorter binary codes to more frequent symbols.

Huffman coding builds a binary tree from symbol frequencies: frequent symbols get **short codes** (2–4 bits), rare symbols get **long codes** (6–7 bits). DEFLATE uses **canonical** Huffman codes so that the decompressor only needs the code **lengths** (not the full tree) to reconstruct the codes.

| Symbol | Frequency | Fixed (9 bits) | Huffman |
|---|---|---|---|
| `' '` (space) | 14 | 9 bits | 3 bits |
| `'e'` | 8 | 9 bits | 4 bits |
| `'T'` | 1 | 9 bits | 7 bits |

**Two separate trees:** One for the literal/length alphabet (286 symbols) and one for distances (30 symbols).

**Files:** `stages/stage3.py`, `stages/utilities/util_3.py`

📖 [Full documentation →](documentation/stage3.md)

---

### Stage 4 — Bitstream Packing

**Goal:** Pack everything into a final compressed byte sequence.

Writes a **header** (containing the Huffman code lengths so the decompressor can rebuild the trees) followed by the **payload** (Huffman codes + extra bits packed tightly bit-by-bit). Variable-length codes are packed across byte boundaries with no gaps.

```
┌───────────┬───────────┬─────────────────────┬──────────────────────┐
│ LIT_BW    │ DIST_BW   │ LIT_TABLE           │ DIST_TABLE           │
│ (4 bits)  │ (4 bits)  │ (286 × LIT_BW bits) │ (30 × DIST_BW bits) │
└───────────┴───────────┴─────────────────────┴──────────────────────┘
                         ↑ HEADER
┌────────────────────────────────────────────────────────────────────┐
│ Huffman codes + extra bits packed tightly ... Huffman(256) [pad]   │
└────────────────────────────────────────────────────────────────────┘
                         ↑ PAYLOAD
```

**Files:** `stages/stage4.py`, `stages/utilities/util_4.py`

📖 [Full documentation →](documentation/stage4.md)

---

## Project Structure

```
DEFLATE-Compressor-and-Decompressor/
├── README.md                 ← You are here
├── documentation/
│   ├── stage1.md             ← Detailed Stage 1 docs
│   ├── stage2.md             ← Detailed Stage 2 docs
│   ├── stage3.md             ← Detailed Stage 3 docs
│   └── stage4.md             ← Detailed Stage 4 docs
├── data/
│   └── data_1.txt            ← Sample test data
└── stages/
    ├── stage1.py             ← LZ77 compression
    ├── stage2.py             ← DEFLATE symbol encoding
    ├── stage3.py             ← Canonical Huffman coding
    ├── stage4.py             ← Bitstream packing
    └── utilities/
        ├── util_1.py         ← Sliding window, constants
        ├── util_2.py         ← Length/distance lookup tables
        ├── util_3.py         ← Huffman tree building, canonical codes
        └── util_4.py         ← BitWriter, header helpers
```

---

## Quick Start

Each stage can be run independently to see its output:

```bash
cd stages/

# Run Stage 1 — see LZ77 literals and matches
python3 stage1.py

# Run Stage 2 — see DEFLATE symbol codes
python3 stage2.py

# Run Stage 3 — see Huffman code assignments
python3 stage3.py

# Run Stage 4 — see final compressed output
python3 stage4.py
```

---

## Compression Results

On the sample `data_1.txt` (377 bytes):

| Metric | Value |
|---|---|
| Original size | 377 bytes |
| Compressed size | 229 bytes |
| Compression ratio | 60.7% |
| Space saved | 148 bytes (39.3%) |
| Header overhead | 120 bytes |
| Payload | 109 bytes |

---
