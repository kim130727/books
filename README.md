# books

유튜브 자막을 텍스트로 추출하고, LLM으로 문장을 다듬은 뒤, 책처럼 읽기 좋은 문체로 정리하는 파이프라인 프로젝트입니다.

## 기능

- 유튜브 한국어 자막(`.vtt`) 다운로드
- 자막 텍스트 정리 및 중복 제거 후 `.txt` 변환
- LLM 기반 문장 교정(의미/정보/순서 최대한 유지)
- LLM 기반 책 문체 스타일 정리(내용 변경 없이 가독성 개선)
- 파일/전체 진행률 및 예상 소요 시간(ETA) 출력

## 요구 사항

- Python 3.10 이상
- OpenAI API Key
- `uv` (권장) 또는 `pip`

## 설치

### 1) 의존성 설치

`uv` 사용 시:

```bash
uv sync
```

`pip` 사용 시:

```bash
python -m pip install -e .
```

### 2) 환경 변수 설정

프로젝트 루트에 `.env` 파일을 만들고 아래를 추가합니다.

```env
OPENAI_API_KEY=your_api_key_here
```

## 사용 방법

기본 파이프라인은 아래 순서로 실행합니다.

## `txt_llm_percent` vs `book_llm`

두 스크립트는 모두 텍스트를 다듬지만, 목적이 다릅니다.

### 1) `txt_llm_percent.py` (1차 정제)

- 핵심 목적: 자막 텍스트를 자연스럽게 읽히도록 문장 흐름/문법을 정리
- 입력 기본 폴더: `input_txt/`
- 출력 기본 폴더: `output_txt/`
- 기본 분할: `target=1000`, `min=700`, `max=1200`
- 특징: 원문 의미/정보/순서를 최대한 유지하면서 자막 특유의 끊김을 완화

### 2) `book_llm.py` (2차 책 문체화)

- 핵심 목적: 1차 정제 결과를 책처럼 읽기 좋은 문체/문단으로 재정리
- 입력 기본 폴더: `output_txt/`
- 출력 기본 폴더: `book_txt/`
- 기본 분할: `target=1200`, `min=900`, `max=1600`
- 특징: 내용 추가/삭제 없이 가독성을 높이는 스타일 정리 단계

요약하면, `txt_llm_percent`는 정제 단계이고 `book_llm`는 독서용 스타일링 단계입니다.

### 1) 유튜브 자막 다운로드 및 텍스트 변환

`youtube_script_down.py`의 `YOUTUBE_URLS` 리스트에 URL을 넣고 실행합니다.

```bash
uv run python youtube_script_down.py
```

결과:
- `input_txt/`에 자막 기반 `.txt` 파일 생성

### 2) 자막 텍스트 1차 정제

```bash
uv run python txt_llm_percent.py --in_dir input_txt --out_dir output_txt --model gpt-4o-mini
```

기본 분할 옵션:
- `target_chars=1000`
- `min_chars=700`
- `max_chars=1200`

결과:
- `output_txt/`에 정제된 `.txt` 파일 생성

### 3) 책 문체로 2차 정리

```bash
uv run python book_llm.py --in_dir output_txt --out_dir book_txt --model gpt-4o-mini
```

기본 분할 옵션:
- `target_chars=1200`
- `min_chars=900`
- `max_chars=1600`

결과:
- `book_txt/`에 최종 텍스트 생성

## 디렉터리 구조

```text
.
├─ youtube_script_down.py
├─ txt_llm_percent.py
├─ book_llm.py
├─ input_txt/      # 자막 추출/변환 결과
├─ output_txt/     # 1차 LLM 정제 결과
└─ book_txt/       # 최종 책 문체 결과
```

## 참고

- 세 스크립트 모두 `OPENAI_API_KEY`가 필요합니다.
- 출력 파일은 UTF-8 인코딩으로 저장됩니다.
- URL을 여러 개 넣으면 순차 처리됩니다.
