# split_read_1800.py
from __future__ import annotations
import argparse
from pathlib import Path

def split_text(text: str, chunk_size: int) -> list[str]:
    # BOM 제거 + 통일된 줄바꿈
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    chunks: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        end = min(i + chunk_size, n)

        # 너무 어색하게 중간에서 끊기지 않게: 가능한 경우 마지막 줄바꿈에서 끊기
        # (단, 너무 짧아지면 그냥 chunk_size로 자름)
        if end < n:
            last_nl = text.rfind("\n", i, end)
            if last_nl != -1 and (last_nl - i) >= int(chunk_size * 0.6):
                end = last_nl + 1

        chunks.append(text[i:end])
        i = end

    return chunks

def main():
    parser = argparse.ArgumentParser(description="Split a txt into 1800-char chunks and read sequentially.")
    parser.add_argument("file", help="input txt file path")
    parser.add_argument("--size", type=int, default=1800, help="chunk size in characters (default: 1800)")
    parser.add_argument("--no-wait", action="store_true", help="do not wait for Enter between chunks")
    parser.add_argument("--outdir", default="", help="optional: save chunks as separate files into this folder")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    text = path.read_text(encoding="utf-8")
    chunks = split_text(text, args.size)

    # 저장 옵션
    if args.outdir:
        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        stem = path.stem
        for idx, chunk in enumerate(chunks, start=1):
            (outdir / f"{stem}_{idx:03}.txt").write_text(chunk, encoding="utf-8")

    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        print(f"\n===== [{idx}/{total}] ({len(chunk)} chars) =====\n")
        print(chunk, end="" if chunk.endswith("\n") else "\n")
        if not args.no_wait and idx != total:
            input("\n(Enter를 누르면 다음 1800자 출력) ")

if __name__ == "__main__":
    main()