# DEFLATE Compressor & Decompressor

A from-scratch implementation of the DEFLATE compression algorithm (RFC 1951), built as a modular 4-stage pipeline for educational purposes. Compresses any file into a custom `.sdfl` format and decompresses it back to the original.

---

## Usage

```bash
# Compress a file → creates <filename>.sdfl
python3 main.py -c <filename>

# Decompress a .sdfl file → restores the original
python3 main.py -d <filename>.sdfl
```

**Example:**

```bash
python3 main.py -c data/data_2.txt        # → data/data_2.txt.sdfl
python3 main.py -d data/data_2.txt.sdfl   # → data/data_2.txt
```

No external dependencies — runs on Python 3 standard library only.

---

## How It Works

DEFLATE combines **LZ77** (pattern matching) and **Huffman coding** (entropy coding) to compress data losslessly. This implementation splits the algorithm into 4 clear stages:

```
Raw bytes ──▶ Stage 1 ──▶ Stage 2 ──▶ Stage 3 ──▶ Stage 4 ──▶ Compressed bytes
              LZ77       DEFLATE     Huffman     Bitstream
                         Symbols     Coding      Packing
```

Decompression reverses the entire pipeline in a single pass.

---

## Compression Pipeline

### Stage 1 — LZ77 Compression

Slides a 32 KB window over the input, replacing repeated byte sequences with back-references `(length, distance)`. Unique bytes pass through as literals.

| Input | Output |
|---|---|
| `ABCABCABC` (9 bytes) | `L(A) L(B) L(C) M(6,3)` — 3 literals + 1 match |

**Files:** `stages/stage1.py`, `stages/utilities/util_1.py`

### Stage 2 — DEFLATE Symbol Encoding

Converts raw lengths (3–258) and distances (1–32768) into compact symbol codes + extra bits, reducing the alphabet to 29 length symbols and 30 distance symbols.

**Files:** `stages/stage2.py`, `stages/utilities/util_2.py`

### Stage 3 — Canonical Huffman Coding

Builds frequency-optimal binary codes: frequent symbols get short codes, rare ones get long codes. Uses canonical form so only code *lengths* are needed to reconstruct the codes.

**Files:** `stages/stage3.py`, `stages/utilities/util_3.py`

### Stage 4 — Bitstream Packing

Writes a header (Huffman code-length tables) followed by the payload (Huffman codes + extra bits) packed tightly into bytes.

```
Header:  [LIT_BW 4b][DIST_BW 4b][286 × LIT_BW bits][30 × DIST_BW bits]
Payload: [Huffman codes + extra bits ... Huffman(256) end marker] [padding]
```

**Files:** `stages/stage4.py`, `stages/utilities/util_4.py`

---

## Decompression

The decompressor reads the `.sdfl` bitstream in a single pass:

1. Read `LIT_BW` and `DIST_BW` from the header (8 bits)
2. Read 286 literal/length code lengths + 30 distance code lengths
3. Rebuild canonical Huffman lookup tables from the lengths
4. Decode symbols until end-of-block (256): literals are emitted directly, matches copy from the output buffer

**Files:** `decompressor.py`, `stages/utilities/util_decompressor.py`

---

## Project Structure

```
DEFLATE-Compressor-and-Decompressor/
├── main.py                       ← CLI entry point (-c / -d)
├── compressor.py                 ← 4-stage compression pipeline
├── decompressor.py               ← Single-pass decompression
├── README.md                     ← This file
├── documentation/
│   ├── compressor.md             ← Compressor architecture overview
│   ├── decompressor.md           ← Decompressor architecture overview
│   ├── stage1.md                 ← LZ77 detailed documentation
│   ├── stage2.md                 ← DEFLATE symbols documentation
│   ├── stage3.md                 ← Huffman coding documentation
│   └── stage4.md                 ← Bitstream packing documentation
├── stages/
│   ├── stage1.py                 ← LZ77 compression
│   ├── stage2.py                 ← DEFLATE symbol encoding
│   ├── stage3.py                 ← Canonical Huffman coding
│   ├── stage4.py                 ← Bitstream packing
│   └── utilities/
│       ├── util_1.py             ← Sliding window, constants
│       ├── util_2.py             ← Length/distance lookup tables
│       ├── util_3.py             ← Huffman tree building
│       ├── util_4.py             ← BitWriter, header helpers
│       └── util_decompressor.py  ← BitReader, Huffman decode helpers
└── data/
    ├── data_1.txt                ← Small test file (377 B)
    └── data_2.txt                ← Larger test file (~1 MB)
```

---

## Documentation

Each stage has a dedicated document with full explanations, diagrams, and worked examples:

| Document | Topic |
|---|---|
| [compressor.md](documentation/compressor.md) | Compressor pipeline overview |
| [decompressor.md](documentation/decompressor.md) | Decompressor pipeline overview |
| [stage1.md](documentation/stage1.md) | LZ77 — sliding window, match finding |
| [stage2.md](documentation/stage2.md) | DEFLATE symbols — length/distance tables, extra bits |
| [stage3.md](documentation/stage3.md) | Canonical Huffman — tree building, code assignment |
| [stage4.md](documentation/stage4.md) | Bitstream — header format, bit packing |

---

## Results

Tested on `data_2.txt` (~1 MB):

| Metric | Value |
|---|---|
| Original size | 1,009,152 B |
| Compressed size | 57,277 B |
| Compression ratio | 5.7% |
| Compression time | ~3.8 s |
| Decompression time | ~0.2 s |
