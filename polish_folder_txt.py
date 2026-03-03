# polish_folder_txt.py
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
client = OpenAI()  # OPENAI_API_KEY from env/.env


def normalize_text(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def chunk_1800_2200(text: str, min_chars: int = 1800, max_chars: int = 2200) -> List[str]:
    text = normalize_text(text)
    n = len(text)
    i = 0
    chunks: List[str] = []

    def find_break(start: int, hard_end: int) -> int:
        window = text[start:hard_end]

        idx = window.rfind("\n")
        if idx != -1 and (idx + 1) >= min_chars:
            return start + idx + 1

        m = list(re.finditer(r"(다\.|요\.|니다\.|[.!?…])(\s|\n|$)", window))
        if m:
            for mm in reversed(m):
                pos = mm.end()
                if pos >= min_chars:
                    return start + pos

        idx = window.rfind(" ")
        if idx != -1 and (idx + 1) >= min_chars:
            return start + idx + 1

        return hard_end

    while i < n:
        hard_end = min(i + max_chars, n)
        if hard_end == n:
            chunks.append(text[i:hard_end])
            break

        cut = find_break(i, hard_end)
        if (cut - i) < min_chars:
            cut = hard_end

        chunks.append(text[i:cut])
        i = cut

    return chunks


def polish_chunk(model: str, chunk_text: str, file_name: str, part_idx: int, part_total: int) -> str:
    instructions = f"""
당신은 한국어 글을 '문장만 다듬는' 전문 편집자입니다.

[필수 규칙]
1) 원문 내용(사실/정보/수치/고유명사/순서/의미)을 100% 유지하세요. 절대 삭제/누락/추가/각색하지 마세요.
2) 맞춤법/띄어쓰기/문장호흡/중복 표현 정리만 하세요. 의미를 바꾸지 마세요.
3) 전체 톤은 '존댓말'로, 독자에게 친절하게 설명하며 자연스럽게 대화하듯 이어지게 다듬어 주세요.
4) 목록/표/번호/강조표현(**, ### 등)이 원문에 있으면 구조를 유지하되, 문장만 자연스럽게 다듬으세요.
5) 결과는 '다듬은 본문'만 출력하세요. (제목, 해설, 요약, 코멘트 등 추가 금지)
6) 원문 길이와 정보량은 동일하게 유지하되, 문장만 매끄럽게 고치세요.

[작업 단위]
- 파일: {file_name}
- 구간: {part_idx}/{part_total}
""".strip()

    resp = client.responses.create(
        model=model,
        instructions=instructions,
        input=chunk_text,
    )
    return (resp.output_text or "").strip()


def fmt_secs(sec: float) -> str:
    sec = max(0.0, sec)
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}시간 {m}분 {s}초"
    if m:
        return f"{m}분 {s}초"
    return f"{s}초"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_dir", required=True, help="입력 txt 폴더")
    parser.add_argument("--out_dir", required=True, help="출력 txt 폴더")
    parser.add_argument("--model", default="gpt-4o-mini", help="사용 모델")
    parser.add_argument("--min_chars", type=int, default=1800)
    parser.add_argument("--max_chars", type=int, default=2200)
    parser.add_argument("--sleep", type=float, default=0.3, help="요청 사이 쉬는 시간(초)")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("환경변수 OPENAI_API_KEY가 설정되어 있지 않습니다. (.env 로드 확인)")

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(in_dir.glob("*.txt"))
    if not txt_files:
        raise SystemExit(f"입력 폴더에 txt 파일이 없습니다: {in_dir}")

    # 전체 구간 수(전체 진행률/ETA용)
    all_chunks_count = 0
    per_file_chunks: dict[Path, List[str]] = {}
    for fp in txt_files:
        raw = fp.read_text(encoding="utf-8")
        chunks = chunk_1800_2200(raw, min_chars=args.min_chars, max_chars=args.max_chars)
        per_file_chunks[fp] = chunks
        all_chunks_count += len(chunks)

    print(f"총 파일 {len(txt_files)}개, 총 구간 {all_chunks_count}개 처리 시작")
    start_all = time.time()

    done_chunks = 0
    avg_time_per_chunk = None  # 이동평균

    for f_idx, fp in enumerate(txt_files, start=1):
        chunks = per_file_chunks[fp]
        total = len(chunks)
        polished_parts: List[str] = []

        print(f"\n[{f_idx}/{len(txt_files)}] 파일 시작: {fp.name} (구간 {total}개)")

        for idx, chunk in enumerate(chunks, start=1):
            chunk_start = time.time()
            print(f"  - 구간 {idx}/{total} 요청중... (전체 {done_chunks+1}/{all_chunks_count})", flush=True)

            for attempt in range(1, 4):
                try:
                    polished = polish_chunk(
                        model=args.model,
                        chunk_text=chunk,
                        file_name=fp.name,
                        part_idx=idx,
                        part_total=total,
                    )
                    polished_parts.append(polished)
                    break
                except Exception as e:
                    print(f"    ! 오류(시도 {attempt}/3): {type(e).__name__}: {e}", flush=True)
                    if attempt == 3:
                        raise
                    time.sleep(1.5 * attempt)

            chunk_elapsed = time.time() - chunk_start
            done_chunks += 1

            # ETA 계산 (간단 이동평균)
            if avg_time_per_chunk is None:
                avg_time_per_chunk = chunk_elapsed
            else:
                avg_time_per_chunk = avg_time_per_chunk * 0.8 + chunk_elapsed * 0.2

            remain = all_chunks_count - done_chunks
            eta = (avg_time_per_chunk or 0) * remain

            print(f"    ✓ 완료: {fmt_secs(chunk_elapsed)} (예상 남은 시간: {fmt_secs(eta)})", flush=True)

            time.sleep(args.sleep)

        out_path = out_dir / f"{fp.stem}_polished.txt"
        joined = "\n".join(p.rstrip() for p in polished_parts).rstrip() + "\n"
        out_path.write_text(joined, encoding="utf-8")

        print(f"[{f_idx}/{len(txt_files)}] 저장 완료: {out_path.name}")

    elapsed_all = time.time() - start_all
    print(f"\n전체 완료! 총 소요: {fmt_secs(elapsed_all)}")


if __name__ == "__main__":
    main()