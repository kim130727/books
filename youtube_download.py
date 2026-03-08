import os
import re
import subprocess
from pathlib import Path


def safe_filename(name: str) -> str:
    # Windows 파일명 금지문자 제거
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip()


def download_youtube_mp4(url: str, out_dir: str = "downloads") -> Path:
    os.makedirs(out_dir, exist_ok=True)

    # 파일명 템플릿: 제목 [id].ext
    outtmpl = str(Path(out_dir) / "%(title)s [%(id)s].%(ext)s")

    cmd = [
        "yt-dlp",
        "--js-runtimes", "node",
        "--extractor-args", "youtube:player_client=android,web",
        "-x",
        "--audio-format", "wav",
        "-o", str(Path(out_dir) / "%(title)s [%(id)s].%(ext)s"),
    url,
]

    print("유튜브 다운로드 시작")
    print("CMD:", " ".join(cmd))

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    last_line = ""
    for line in p.stdout:
        last_line = line.rstrip()
        print(last_line)

    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"다운로드 실패 (exit={p.returncode}). 마지막 로그: {last_line}")

    # 다운로드된 파일 찾기(가장 최근 mp4)
    mp4s = sorted(Path(out_dir).glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
    if not mp4s:
        raise FileNotFoundError("다운로드는 성공했는데 mp4 파일을 찾지 못했습니다.")
    return mp4s[0]


def main():
    url = input("유튜브 URL 입력: ").strip()
    out_dir = input("저장 폴더(기본 downloads): ").strip() or "downloads"

    mp4_path = download_youtube_mp4(url, out_dir=out_dir)
    print("\n✅ 완료:", mp4_path)


if __name__ == "__main__":
    main()