import os
import re
import subprocess
from pathlib import Path

# URL 1개 또는 여러 개 입력 가능
YOUTUBE_URLS = [
    "https://youtu.be/gMTNPms9Q88",
]

OUT_DIR = "input_txt"


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip()


def vtt_to_txt(vtt_path: Path, txt_path: Path):
    lines = vtt_path.read_text(encoding="utf-8", errors="replace").splitlines()

    result = []
    prev = None

    for line in lines:
        line = line.strip()

        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\{.*?\}", "", line)
        line = (
            line.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
        )

        if line and line != prev:
            result.append(line)
            prev = line

    txt_path.write_text("\n".join(result).strip() + "\n", encoding="utf-8")


def run_cmd(cmd):
    print("CMD:", " ".join(cmd))
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    logs = []
    for line in p.stdout:
        line = line.rstrip()
        logs.append(line)
        print(line)

    p.wait()
    return p.returncode, logs


def build_base_cmd(url: str, outtmpl: str):
    return [
        "yt-dlp",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--skip-download",
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "ko-orig,ko",
        "--sub-format", "vtt",
        "-o", outtmpl,
        url,
    ]


def find_best_vtt(out_dir: str, video_id: str | None = None) -> Path | None:
    candidates = list(Path(out_dir).glob("*.vtt"))

    if video_id:
        candidates = [p for p in candidates if f"[{video_id}]" in p.name]

    if not candidates:
        return None

    # 우선순위: ko-orig > ko > 기타
    def priority(p: Path):
        name = p.name.lower()
        if ".ko-orig.vtt" in name:
            return (0, -p.stat().st_mtime)
        if ".ko.vtt" in name:
            return (1, -p.stat().st_mtime)
        return (9, -p.stat().st_mtime)

    candidates.sort(key=priority)
    return candidates[0]


def extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def download_subtitle(url: str, out_dir: str = "input_txt") -> Path:
    os.makedirs(out_dir, exist_ok=True)
    outtmpl = str(Path(out_dir) / "%(title)s [%(id)s].%(ext)s")
    video_id = extract_video_id(url)

    cmd = build_base_cmd(url, outtmpl)
    code, logs = run_cmd(cmd)

    found_vtt = find_best_vtt(out_dir, video_id=video_id)
    if found_vtt:
        if code != 0:
            print("\n주의: yt-dlp가 오류 코드를 반환했지만, 자막 파일이 이미 생성되어 계속 진행합니다.")
        return found_vtt

    last_line = logs[-1] if logs else "(로그 없음)"
    raise RuntimeError(f"자막 다운로드 실패\n마지막 로그: {last_line}")


def normalize_urls(urls) -> list[str]:
    """
    문자열 1개 또는 리스트/튜플 모두 허용
    """
    if isinstance(urls, str):
        return [urls.strip()] if urls.strip() else []

    result = []
    for u in urls:
        if not isinstance(u, str):
            continue
        u = u.strip()
        if u:
            result.append(u)
    return result


def process_one_url(url: str, out_dir: str = "input_txt") -> tuple[Path, Path]:
    vtt_path = download_subtitle(url, out_dir)

    txt_path = vtt_path.with_suffix(".txt")
    txt_path = txt_path.with_name(safe_filename(txt_path.name))

    vtt_to_txt(vtt_path, txt_path)
    return vtt_path, txt_path


def main():
    urls = normalize_urls(YOUTUBE_URLS)

    if not urls:
        raise SystemExit("YOUTUBE_URLS에 유효한 URL이 없습니다.")

    success = []
    failed = []

    total = len(urls)

    for idx, url in enumerate(urls, start=1):
        print("\n" + "=" * 80)
        print(f"[{idx}/{total}] 처리 시작")
        print("URL:", url)
        print("=" * 80)

        try:
            vtt_path, txt_path = process_one_url(url, OUT_DIR)

            print("\n✅ 완료")
            print("VTT:", vtt_path)
            print("TXT:", txt_path)

            success.append({
                "url": url,
                "vtt": str(vtt_path),
                "txt": str(txt_path),
            })

        except Exception as e:
            print(f"\n❌ 실패: {url}")
            print("사유:", e)
            failed.append({
                "url": url,
                "error": str(e),
            })

    print("\n" + "=" * 80)
    print("전체 처리 결과")
    print("=" * 80)
    print(f"총 URL 수 : {total}")
    print(f"성공      : {len(success)}")
    print(f"실패      : {len(failed)}")

    if success:
        print("\n성공 목록")
        for i, item in enumerate(success, start=1):
            print(f"{i}. {item['url']}")
            print(f"   VTT: {item['vtt']}")
            print(f"   TXT: {item['txt']}")

    if failed:
        print("\n실패 목록")
        for i, item in enumerate(failed, start=1):
            print(f"{i}. {item['url']}")
            print(f"   오류: {item['error']}")


if __name__ == "__main__":
    main()