# output_txt 폴더에서 .txt 파일 읽기
# 내용은 원문 그대로 유지
# 책으로 더 잘 읽히는 문장/문단 흐름으로 다듬기
# 약 1200자 단위로 자연스럽게 분할
# 결과를 다시 합쳐 book_txt 폴더에 저장
# 진행률(현재 파일/전체 파일/ETA) 표시 버전
# uv run python book_llm.py --in_dir output_txt --out_dir book_txt --model gpt-4o-mini

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


def normalize_text(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def split_book_text(
    text: str,
    target_chars: int = 1200,
    min_chars: int = 900,
    max_chars: int = 1600,
) -> List[str]:
    """
    책 읽기용 편집을 위해 텍스트를 자연스럽게 분할합니다.
    우선순위:
    1) 빈 줄
    2) 줄바꿈
    3) 문장 끝
    4) 공백
    """
    text = normalize_text(text)
    n = len(text)
    i = 0
    chunks: List[str] = []

    def find_cut(start: int, hard_end: int) -> int:
        window = text[start:hard_end]

        # 1) 빈 줄
        idx = window.rfind("\n\n")
        if idx != -1 and idx >= min_chars:
            return start + idx + 2

        # 2) 줄바꿈
        idx = window.rfind("\n")
        if idx != -1 and idx >= min_chars:
            return start + idx + 1

        # 3) 문장 끝
        matches = list(re.finditer(r"(다\.|요\.|니다\.|까\.|죠\.|[.!?…])(\s|\n|$)", window))
        if matches:
            for m in reversed(matches):
                if m.end() >= min_chars:
                    return start + m.end()

        # 4) 공백
        idx = window.rfind(" ")
        if idx != -1 and idx >= min_chars:
            return start + idx + 1

        return hard_end

    while i < n:
        hard_end = min(i + target_chars, n)

        if hard_end == n:
            chunks.append(text[i:n])
            break

        hard_end = min(i + max_chars, n)
        cut = find_cut(i, hard_end)

        if cut - i < min_chars:
            cut = min(i + target_chars, n)

        chunks.append(text[i:cut])
        i = cut

    return chunks


def polish_book_chunk(
    chunk_text: str,
    file_name: str,
    part_idx: int,
    part_total: int,
    model: str,
) -> str:
    """
    자막처럼 다듬어진 텍스트를 책처럼 더 잘 읽히게 정리합니다.
    단, 내용 변경은 금지합니다.
    """
    instructions = f"""
당신은 한국어 원고를 '책처럼 읽기 좋게' 다듬는 전문 편집자입니다.

[목표]
- 원문 내용은 그대로 유지하면서,
  책으로 읽을 때 더 자연스럽고 매끄럽게 읽히도록 문장과 문단만 정리하세요.

[절대 규칙]
1. 원문의 의미, 사실, 정보, 숫자, 고유명사, 순서를 절대 바꾸지 마세요.
2. 삭제, 요약, 추가 설명, 해설, 각색, 재구성, 주장 보강을 하지 마세요.
3. 원문에 없는 제목, 소제목, 목록, 번호, 강조 표시를 새로 만들지 마세요.
4. 문장 흐름, 맞춤법, 띄어쓰기, 어색한 반복, 문단 호흡만 다듬으세요.
5. 자막체 느낌은 줄이되, '책처럼 읽기 좋은 문장'으로만 정리하세요.
6. 지나치게 문장을 길게 늘이지 말고, 필요하면 문장을 자연스럽게 나누세요.
7. 문단은 읽기 좋게 정리하되, 내용 순서가 바뀌면 안 됩니다.
8. 결과는 다듬어진 본문만 출력하세요. 설명, 주석, 코드블록 금지.

[편집 방향]
- 말로 옮겨 적은 느낌을 조금 줄이고, 글로 읽기 좋은 호흡으로 정리
- 군더더기 말버릇은 최소한으로만 정리
- 반복은 의미를 해치지 않는 범위에서만 최소 정리
- 지나친 구어체는 자연스러운 문어체에 가깝게 다듬되, 원문의 톤은 유지

[작업 정보]
- 파일명: {file_name}
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


def progress_bar(percent: float, width: int = 28) -> str:
    percent = max(0.0, min(100.0, percent))
    filled = int(width * percent / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def print_progress(
    file_idx: int,
    total_files: int,
    file_name: str,
    chunk_idx: int,
    total_chunks_in_file: int,
    done_chunks: int,
    all_chunks_count: int,
    avg_chunk_time: float | None,
):
    file_percent = (chunk_idx / total_chunks_in_file) * 100 if total_chunks_in_file else 100.0
    overall_percent = (done_chunks / all_chunks_count) * 100 if all_chunks_count else 100.0
    remain = max(0, all_chunks_count - done_chunks)
    eta = (avg_chunk_time or 0.0) * remain

    file_bar = progress_bar(file_percent)
    overall_bar = progress_bar(overall_percent)

    print()
    print(f"파일 진행률  : {file_bar} {file_percent:6.2f}%   [{chunk_idx}/{total_chunks_in_file}]")
    print(f"전체 진행률  : {overall_bar} {overall_percent:6.2f}%   [{done_chunks}/{all_chunks_count}]")
    print(f"현재 파일    : [{file_idx}/{total_files}] {file_name}")
    print(f"예상 남은 시간: {fmt_secs(eta)}")
    print("-" * 72, flush=True)


def main():
    parser = argparse.ArgumentParser(description="output_txt 폴더의 txt를 책 읽기용으로 다듬어 book_txt에 저장")
    parser.add_argument("--in_dir", default="output_txt", help="입력 txt 폴더")
    parser.add_argument("--out_dir", default="book_txt", help="출력 txt 폴더")
    parser.add_argument("--model", default="gpt-4o-mini", help="사용 모델")
    parser.add_argument("--target_chars", type=int, default=1200, help="목표 분할 글자수")
    parser.add_argument("--min_chars", type=int, default=900, help="최소 분할 글자수")
    parser.add_argument("--max_chars", type=int, default=1600, help="최대 분할 글자수")
    parser.add_argument("--sleep", type=float, default=0.3, help="요청 간 대기 시간")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인하세요.")

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(in_dir.glob("*.txt"))
    if not txt_files:
        raise SystemExit(f"입력 폴더에 txt 파일이 없습니다: {in_dir}")

    per_file_chunks: dict[Path, List[str]] = {}
    all_chunks_count = 0

    print("사전 분할 계산 중...\n")
    for fp in txt_files:
        raw = fp.read_text(encoding="utf-8")
        chunks = split_book_text(
            raw,
            target_chars=args.target_chars,
            min_chars=args.min_chars,
            max_chars=args.max_chars,
        )
        per_file_chunks[fp] = chunks
        all_chunks_count += len(chunks)
        print(f"- {fp.name}: {len(chunks)}개 구간")

    print()
    print("=" * 72)
    print(f"총 파일 {len(txt_files)}개, 총 구간 {all_chunks_count}개 처리 시작")
    print("=" * 72)

    start_all = time.time()
    done_chunks = 0
    avg_chunk_time: float | None = None

    for file_idx, fp in enumerate(txt_files, start=1):
        chunks = per_file_chunks[fp]
        polished_parts: List[str] = []

        print()
        print("=" * 72)
        print(f"[{file_idx}/{len(txt_files)}] 파일 시작: {fp.name}")
        print(f"구간 수: {len(chunks)}")
        print("=" * 72)

        for idx, chunk in enumerate(chunks, start=1):
            chunk_start = time.time()

            print_progress(
                file_idx=file_idx,
                total_files=len(txt_files),
                file_name=fp.name,
                chunk_idx=idx,
                total_chunks_in_file=len(chunks),
                done_chunks=done_chunks,
                all_chunks_count=all_chunks_count,
                avg_chunk_time=avg_chunk_time,
            )
            print(f"구간 처리중... ({idx}/{len(chunks)})", flush=True)

            polished = None
            for attempt in range(1, 4):
                try:
                    polished = polish_book_chunk(
                        chunk_text=chunk,
                        file_name=fp.name,
                        part_idx=idx,
                        part_total=len(chunks),
                        model=args.model,
                    )
                    break
                except Exception as e:
                    print(f"! 오류 (시도 {attempt}/3): {type(e).__name__}: {e}", flush=True)
                    if attempt == 3:
                        raise
                    time.sleep(1.5 * attempt)

            if not polished:
                polished = chunk

            polished_parts.append(polished)

            elapsed = time.time() - chunk_start
            done_chunks += 1

            if avg_chunk_time is None:
                avg_chunk_time = elapsed
            else:
                avg_chunk_time = avg_chunk_time * 0.8 + elapsed * 0.2

            file_percent_done = (idx / len(chunks)) * 100 if chunks else 100.0
            overall_percent_done = (done_chunks / all_chunks_count) * 100 if all_chunks_count else 100.0
            remain = all_chunks_count - done_chunks
            eta = (avg_chunk_time or 0.0) * remain

            print(
                f"✓ 구간 완료 | 파일 {file_percent_done:6.2f}% | 전체 {overall_percent_done:6.2f}% "
                f"| 소요 {fmt_secs(elapsed)} | 예상 남은 시간 {fmt_secs(eta)}",
                flush=True,
            )

            time.sleep(args.sleep)

        merged_text = "\n\n".join(part.rstrip() for part in polished_parts).rstrip() + "\n"

        out_path = out_dir / fp.name
        out_path.write_text(merged_text, encoding="utf-8")

        print(f"[{file_idx}/{len(txt_files)}] 저장 완료: {out_path}", flush=True)

    total_elapsed = time.time() - start_all
    print()
    print("=" * 72)
    print(f"전체 완료! 총 소요: {fmt_secs(total_elapsed)}")
    print("=" * 72)


if __name__ == "__main__":
    main()