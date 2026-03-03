# polish_folder_txt.py
#uv run python polish_folder_txt_v2.py --in_dir ./input_txt --out_dir ./output_txt

from __future__ import annotations

import os
import re
import time
import argparse
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()


# -------------------------
# 텍스트 정규화
# -------------------------
def normalize_text(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


# -------------------------
# 문단 기반 1000자 최적 분할
# -------------------------
def paragraph_chunk_optimized(
    text: str,
    target: int = 1000,
    min_chars: int = 700,
    max_chars: int = 1200,
) -> List[str]:
    text = normalize_text(text)

    # 1️⃣ 문단 기준 분리
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # 2️⃣ 너무 짧은 문단 병합
    merged_paragraphs: List[str] = []
    buffer = ""

    for p in raw_paragraphs:
        if len(p) < 400:
            buffer += ("\n\n" if buffer else "") + p
        else:
            if buffer:
                merged_paragraphs.append(buffer)
                buffer = ""
            merged_paragraphs.append(p)

    if buffer:
        merged_paragraphs.append(buffer)

    # 3️⃣ 길이 조정
    final_chunks: List[str] = []

    for para in merged_paragraphs:
        if len(para) <= max_chars:
            final_chunks.append(para)
        else:
            # 긴 문단은 자연 분할
            start = 0
            n = len(para)

            while start < n:
                hard_end = min(start + max_chars, n)
                window = para[start:hard_end]

                # 줄바꿈 우선
                idx = window.rfind("\n")
                if idx != -1 and idx >= min_chars:
                    cut = start + idx + 1
                else:
                    # 문장 끝 우선
                    m = list(re.finditer(r"(다\.|요\.|니다\.|[.!?…])(\s|$)", window))
                    if m:
                        for mm in reversed(m):
                            if mm.end() >= min_chars:
                                cut = start + mm.end()
                                break
                        else:
                            cut = hard_end
                    else:
                        cut = hard_end

                final_chunks.append(para[start:cut].strip())
                start = cut

    return final_chunks


# -------------------------
# GPT 교정 요청
# -------------------------
def polish_chunk(model: str, chunk_text: str, file_name: str, part_idx: int, part_total: int) -> str:
    instructions = f"""
당신은 한국어 글을 '문장만 다듬는' 전문 편집자입니다.

[필수 규칙]
1) 원문 내용은 100% 유지하세요. 삭제/추가/각색 금지.
2) 맞춤법·띄어쓰기·문장 흐름만 개선하세요.
3) 존댓말로 친절한 대화체로 다듬으세요.
4) 구조(목록/번호/강조)는 그대로 유지하세요.
5) 다듬은 본문만 출력하세요.

[파일: {file_name} | 구간: {part_idx}/{part_total}]
""".strip()

    resp = client.responses.create(
        model=model,
        instructions=instructions,
        input=chunk_text,
    )

    return (resp.output_text or "").strip()


# -------------------------
# 시간 포맷
# -------------------------
def fmt_secs(sec: float) -> str:
    sec = max(0.0, sec)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}시간 {m}분 {s}초"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


# -------------------------
# 메인
# -------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_dir", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--sleep", type=float, default=0.3)
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(in_dir.glob("*.txt"))
    if not txt_files:
        raise SystemExit("입력 폴더에 txt 파일이 없습니다.")

    print(f"총 파일 {len(txt_files)}개 처리 시작")

    start_all = time.time()

    for f_idx, fp in enumerate(txt_files, start=1):
        raw = fp.read_text(encoding="utf-8")
        chunks = paragraph_chunk_optimized(raw)

        print(f"\n[{f_idx}/{len(txt_files)}] 파일: {fp.name}")
        print(f"구간 수: {len(chunks)}")

        polished_parts: List[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            print(f"  - {idx}/{len(chunks)} 처리중...", flush=True)

            polished = polish_chunk(
                model=args.model,
                chunk_text=chunk,
                file_name=fp.name,
                part_idx=idx,
                part_total=len(chunks),
            )

            polished_parts.append(polished)
            time.sleep(args.sleep)

        out_path = out_dir / f"{fp.stem}_polished.txt"
        out_path.write_text("\n\n".join(polished_parts), encoding="utf-8")

        print(f"저장 완료 → {out_path.name}")

    elapsed_all = time.time() - start_all
    print(f"\n전체 완료! 총 소요: {fmt_secs(elapsed_all)}")


if __name__ == "__main__":
    main()