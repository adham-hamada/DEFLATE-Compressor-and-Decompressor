import sys
import os
import time
from compressor import compress
from decompressor import decompress

EXTENSION = ".sdfl"


def do_compress(filepath):
    """Compress a file and write <filepath>.sdfl alongside it."""
    with open(filepath, 'rb') as f:
        data = f.read()

    start = time.time()
    compressed = compress(data)
    elapsed = time.time() - start

    out_path = filepath + EXTENSION
    with open(out_path, 'wb') as f:
        f.write(compressed)

    ratio = len(compressed) / len(data) * 100 if data else 0
    print(f"Compressed: {len(data)} B -> {len(compressed)} B ({ratio:.1f}%)")
    print(f"Compression time: {elapsed:.3f}s")
    print(f"Output: {out_path}")


def do_decompress(filepath):
    """Decompress a .sdfl file and restore the original."""
    if not filepath.endswith(EXTENSION):
        print(f"Error: expected a {EXTENSION} file.")
        sys.exit(1)

    with open(filepath, 'rb') as f:
        compressed = f.read()

    start = time.time()
    decompressed = decompress(compressed)
    elapsed = time.time() - start

    out_path = filepath[:-len(EXTENSION)]
    with open(out_path, 'wb') as f:
        f.write(decompressed)

    print(f"Decompressed: {len(compressed)} B -> {len(decompressed)} B")
    print(f"Decompression time: {elapsed:.3f}s")
    print(f"Output: {out_path}")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('-c', '-d'):
        print("Usage:")
        print("  python main.py -c <filename>   Compress")
        print("  python main.py -d <filename>   Decompress")
        sys.exit(1)

    mode = sys.argv[1]
    filepath = sys.argv[2]

    if not os.path.isfile(filepath):
        print(f"Error: file not found: {filepath}")
        sys.exit(1)

    if mode == '-c':
        do_compress(filepath)
    else:
        do_decompress(filepath)


if __name__ == "__main__":
    main()
