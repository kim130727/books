import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from faster_whisper import WhisperModel
from openai import OpenAI


# -----------------------------
# data
# -----------------------------
@dataclass
class Segment:
    idx: int
    start: float
    end: float
    text: str


# -----------------------------
# whisper
# -----------------------------
def transcribe_whisper(wav_path: Path):

    print(f"\nWhisper 시작: {wav_path.name}")

    model = WhisperModel(
        "medium",
        device="cpu",
        compute_type="int8"
    )

    segments, info = model.transcribe(str(wav_path))

    total = info.duration
    result = []

    for i, seg in enumerate(segments, start=1):

        text = seg.text.strip()

        result.append(Segment(i, seg.start, seg.end, text))

        pct = (seg.end / total) * 100
        print(f"\rWhisper 진행률: {pct:6.2f}%", end="")

        print(f"\n[{i:04d}] {text}")

    print("\nWhisper 완료")

    return result


# -----------------------------
# chatgpt refine
# -----------------------------
def refine_with_chatgpt(segments: List[Segment], batch=20):

    print("\nChatGPT 문장 정리 시작")

    load_dotenv()
    client = OpenAI()

    refined = {s.idx: s.text for s in segments}

    total_batches = math.ceil(len(segments) / batch)

    for bi in range(total_batches):

        group = segments[bi*batch:(bi+1)*batch]

        payload = [{"idx": s.idx, "text": s.text} for s in group]

        prompt = f"""
다음 자막을 자연스럽게 정리하세요.

규칙
- 의미 변경 금지
- 말버릇 제거
- JSON만 출력

형식
{{"items":[{{"idx":1,"text":"..."}}]}}

입력
{json.dumps(payload, ensure_ascii=False)}
"""

        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        data = json.loads(resp.output_text)

        for item in data["items"]:
            refined[item["idx"]] = item["text"]
            print(f"정리[{item['idx']}]: {item['text']}")

        pct = ((bi+1)/total_batches)*100
        print(f"ChatGPT 진행률 {pct:.2f}%")

    return [Segment(s.idx, s.start, s.end, refined[s.idx]) for s in segments]


# -----------------------------
# save
# -----------------------------
def save_txt(segments, path):

    with open(path, "w", encoding="utf8") as f:

        for s in segments:
            f.write(s.text + "\n")

    print("저장:", path)


# -----------------------------
# main
# -----------------------------
def main():

    work = Path("work")

    wav_files = list(work.glob("*.wav"))

    if not wav_files:
        print("work 폴더에 wav 파일이 없습니다")
        return

    for wav in wav_files:

        print("\n=================================")
        print("처리중:", wav.name)

        segments = transcribe_whisper(wav)

        segments = refine_with_chatgpt(segments)

        out = wav.with_suffix(".txt")

        save_txt(segments, out)


if __name__ == "__main__":
    main()