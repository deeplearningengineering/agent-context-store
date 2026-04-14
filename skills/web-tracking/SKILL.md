---
name: web-tracking
description: _Inbox/web-tracking/!tracking list.md에 등록된 블로그/웹사이트들에서 지정한 날짜(인자 없으면 오늘) 발행된 새 글을 RSS/Atom 자동 탐색으로 수집하고, 한국어 불릿 요약으로 정리해 _Inbox/web-tracking/YYYY-MM-DD_{주요내용}.md에 통합 저장합니다. 사용자가 "web tracking", "웹 트래킹", "블로그 새 글 확인", "구독 블로그 체크", "/web-tracking", "/web-tracking 2026-04-10" 등을 말하거나 등록해 둔 사이트들의 업데이트를 특정 날짜 기준으로 확인하고 싶을 때 반드시 사용합니다.
allowed-tools: Bash(python3:*), Bash(date:*), Bash(nlm:*), mcp__mcp-obsidian__obsidian_get_file_contents, mcp__mcp-obsidian__obsidian_append_content, mcp__mcp-obsidian__obsidian_list_files_in_dir, mcp__mcp-obsidian__obsidian_delete_file, mcp__notebooklm-mcp__notebook_list, mcp__notebooklm-mcp__notebook_delete
---

# Web Tracking Skill

Obsidian `_Inbox/web-tracking/!tracking list.md`에 등록된 사이트 목록에서 **지정한 날짜(KST 기준 하루)**에 발행된 글을 찾아 요약해서 `_Inbox/web-tracking/YYYY-MM-DD.md` 한 파일에 모아 저장합니다.

## 호출 형식

```
/web-tracking [YYYY-MM-DD]
```

- `YYYY-MM-DD`: 수집 기준 날짜 (선택). 생략하면 **오늘(KST)** 을 사용합니다.
- 예: `/web-tracking 2026-04-10` → 2026-04-10 00:00 ~ 23:59:59 KST 사이에 발행된 글만 수집.

날짜 범위는 입력한 날짜의 **KST 0시부터 그 다음 날 0시 직전까지** 입니다. 즉 "그 하루 동안"입니다. 타임존 혼동을 줄이기 위해 필터는 항상 KST로 수행합니다.

## 왜 이 구조인가

이 스킬은 사용자가 직접 관리하는 tracking list(마크다운 테이블)를 단일 원천으로 사용합니다. 사이트를 하드코딩하지 않으므로 새 블로그를 추가할 때 스킬 코드를 고칠 필요가 없고, 대신 `fetch_site.py`가 사이트 URL과 날짜를 받아 RSS 피드를 자동으로 찾아냅니다. 대부분의 블로그는 `/rss/`, `/feed/`, `/feed.xml` 같은 관습적 경로나 HTML `<link rel="alternate">` 태그로 피드를 노출하기 때문에 이 경로들로 대부분을 처리할 수 있습니다. 피드를 찾지 못하면 홈페이지 HTML에서 `<article>`과 `<time datetime>` 태그를 긁어 fallback으로 동작합니다.

## 실행 절차

### 1단계: 기준 날짜 결정

- **인자가 있으면**: 그 값을 `DATE`로 사용 (`YYYY-MM-DD` 형식 검증).
- **인자가 없으면**: `date +%Y-%m-%d`로 오늘(KST) 날짜를 `DATE`로 사용.

잘못된 형식이면 "날짜는 YYYY-MM-DD 형식이어야 합니다. 예: /web-tracking 2026-04-10" 출력 후 종료.

### 2단계: tracking list 읽기

`mcp__mcp-obsidian__obsidian_get_file_contents`로 `_Inbox/web-tracking/!tracking list.md`를 읽어옵니다. 파일은 다음과 같은 마크다운 테이블입니다:

```markdown
| 이름                 | URL                         |
| ------------------ | --------------------------- |
| 제프리 헌틀리            | https://ghuntley.com/       |
| Mitchell Hashimoto | https://mitchellh.com/      |
| langchain blog     | https://blog.langchain.com/ |
```

테이블에서 각 행의 `이름`과 `URL` 쌍을 파싱합니다. 헤더 행과 구분선(`---`) 행은 건너뜁니다. URL이 없는 행, 주석 행(`<!--`)은 무시합니다. 사이트 목록이 비어 있으면 "tracking list가 비어 있습니다"를 출력하고 종료합니다.

### 3단계: 각 사이트별로 해당 날짜 글 수집

각 사이트에 대해 다음 스크립트를 실행합니다 — **반드시 `DATE`를 두 번째 인자로 전달**합니다:

```bash
python3 .claude/skills/web-tracking/scripts/fetch_site.py "<site-url>" "<DATE>"
```

**출력 형식:**

- 해당 날짜에 새 글이 없으면: `NO_ITEMS`
- 실패 시: 스크립트는 `NO_ITEMS`를 출력하고 stderr에 사유를 기록. 종료 코드 2는 피드와 HTML fallback 모두 실패했음을 의미합니다.
- 성공 시: 각 항목이 `---ITEM---`으로 구분되며 다음 필드를 가짐:

  ```
  TITLE: 글 제목
  LINK: https://example.com/post
  PUB: 2026-04-10 14:32
  CONTENT_START
  본문 텍스트 (HTML 태그 제거됨, 최대 5000자)
  CONTENT_END
  ```

각 사이트 결과를 메모리에 보관합니다. 한 사이트가 실패해도 나머지는 계속 진행합니다.

### 3.5단계: 동일 날짜 및 20일 초과 과거 노트북 정리

1. `mcp__notebooklm-mcp__notebook_list`로 전체 노트북 목록을 가져옵니다.
2. 제목이 `^(\d{2}-\d{2}-\d{2}) auto-web ` 정규식에 매칭되면 이 스킬이 만든 것으로 간주합니다.
3. 매칭된 노트북 중 다음 조건에 해당하면 삭제합니다:
   - **동일 날짜**: 노트북 날짜가 `<TARGET_DATE>`와 같은 경우 (재실행 시 중복 방지)
   - **20일 초과**: `today - notebook_date > 20 days`인 경우
4. `mcp__notebooklm-mcp__notebook_delete`로 삭제합니다. 개별 삭제가 실패해도 계속 진행합니다.
5. 삭제 결과를 보관합니다 (최종 Obsidian 출력용).

### 3.7단계: 제목 요약 생성 및 NotebookLM 노트북 생성

**3.7-1. 제목 요약 생성**

수집된 글 제목들을 통독하고, 공통된 **트렌드·쟁점을 한 문장으로 합성**합니다.
- 단순 제목 나열 금지. 이모지·따옴표 금지.

**3.7-2. 제목 조합**

```
YY-MM-DD auto-web (N건) <요약 문구>
```
- `YY-MM-DD`: 기준 날짜의 2자리 연도 포맷
- `N`: 수집된 글 수
- **전체 80자 이내**
- 예: `26-04-11 auto-web (5건) LangChain 에이전트 배포와 오픈소스 하네스 트렌드`

**3.7-3. 노트북 생성**

```bash
nlm notebook create "<제목>"
```

`notebook_id`를 파싱하여 이후 단계에서 사용합니다.

### 3.8단계: 기사 URL 소스 등록 및 오디오 생성

수집된 각 글의 URL을 노트북에 한 번에 추가합니다:

```bash
nlm source add <notebook_id> --url "<글URL1>" --url "<글URL2>" ... --wait
```

URL이 접근 불가능한 경우 건너뛰고 계속 진행합니다.

오디오 오버뷰를 생성합니다:

```bash
nlm audio create <notebook_id> --language ko --length long --focus "각 블로그 글을 제목과 함께 순서대로 소개해 주세요. 각 글마다 제목을 먼저 말하고, 핵심 내용을 2~3문장으로 요약해 주세요. 한국어로 진행해 주세요." -y
```

보고서도 생성합니다:

```bash
nlm report create <notebook_id> --format "Create Your Own" --prompt "각 블로그 글을 소스별로 정리해주세요. 글마다 사이트명, 제목을 먼저 쓰고, 핵심 내용을 3~5개 불릿 포인트로 요약해주세요. 한국어로 작성해주세요." --language ko -y
```

`nlm studio status <notebook_id>`를 30초 간격, 최대 20분간 폴링하여 완료를 확인합니다.

### 4단계: 각 글을 한국어로 요약

각 글의 `CONTENT_START`~`CONTENT_END` 본문을 읽고 **"한줄 요약 + 주요 내용(3~5 bullet)"** 포맷으로 정리합니다. 규칙:

- **한줄 요약**: 글 전체를 **한 문장(40~60자)**으로 압축합니다. 글의 핵심 주장/출시/결론을 담아야 합니다. 문장 끝에는 마침표를 붙입니다.
- **주요 내용**: 한국어 불릿 포인트 **3~5개**. 각 불릿은 완전한 문장으로 작성하고, 한줄 요약에서 이미 언급한 내용의 근거·세부사항·수치를 담습니다.
- **굵게 강조**: 일반적인 핵심 용어는 `**굵게**`(Markdown bold)로 강조합니다. 한 불릿당 1~3개가 적당합니다.
- **색상 강조**: 의미 구분이 필요한 항목은 Obsidian이 렌더링하는 인라인 HTML `<span style="color:#HEX; font-weight:bold">...</span>` 로 색+굵게를 동시에 적용합니다.
- **⚠️ 매우 중요 — HTML span 안에는 마크다운 `**bold**`를 절대 쓰지 마세요.** Obsidian은 HTML 태그 내부의 마크다운을 파싱하지 않기 때문에 `<span style="color:#1971c2">**텍스트**</span>` 라고 쓰면 별표가 그대로 텍스트로 보입니다. 반드시 `style` 속성에 `font-weight:bold`를 포함시키고 별표는 생략해야 합니다:
  - ❌ `<span style="color:#1971c2">**LangChain**</span>` — 별표가 보임
  - ✅ `<span style="color:#1971c2; font-weight:bold">LangChain</span>` — 정상 렌더
- 과도한 색 사용은 강조 효과를 희석시킵니다 — **강조는 희소할 때 의미를 갖습니다.**
- 본문이 너무 짧거나 빈약해서 3개 불릿이 어려우면 2개까지 허용합니다.

**색상 체계 (고정 2색, 의미 기반):**

| 색 | HEX | 의미 | 적용 대상 |
|---|---|---|---|
| 🔵 파랑 | `#1971c2` | 중립 강조 — 이름·고유명사·핵심 포인트 | 제품명, 프로젝트명, 컨퍼런스명, 기업·인물 공식 명칭, 주목할 수치·성과, 주요 방향/개념 |
| 🔴 빨강 | `#e03131` | 위험·부정·경고 | deprecation, 보안 이슈, 장애, 실패 사례, lock-in, walled garden, 충돌 |

색상에 해당하지 않는 일반적인 핵심어는 **굵게**(마크다운 bold)만 적용합니다. 색상은 "여기가 이 글의 고유명사/이벤트"이거나 "이건 경고/위험 신호"를 시각적으로 빠르게 구분하기 위한 용도이고, 그 외 일반적인 중요 용어는 굵게만 써서 강약을 만듭니다.

**요약 형식 예시:**

```markdown
**한줄 요약:** <span style="color:#1971c2; font-weight:bold">LangChain</span>이 <span style="color:#1971c2; font-weight:bold">Deep Agents Deploy</span>를 베타 출시하며 **오픈소스 에이전트 하네스의 프로덕션 배포**를 단일 명령어로 가능하게 했다.

**주요 내용:**
- 배포 파라미터는 `model`, `AGENTS.md`, `skills`, `mcp.json`, `sandbox`로 구성되며 <span style="color:#1971c2; font-weight:bold">OpenAI·Anthropic·Bedrock·Ollama</span> 등 주요 공급자를 모두 지원.
- <span style="color:#1971c2; font-weight:bold">LangSmith Deployment</span> 서버 기반으로 **MCP·A2A·Agent Protocol** 등 <span style="color:#1971c2; font-weight:bold">30개 이상 엔드포인트</span>를 자동 노출.
- 핵심 차별점은 **오픈 표준 기반으로 lock-in을 회피**한다는 점이며, 특히 메모리 소유권을 개발자가 유지할 수 있음을 강조.
- <span style="color:#1971c2; font-weight:bold">Claude Managed Agents</span>와 비교 포지셔닝: 후자는 <span style="color:#e03131; font-weight:bold">walled garden</span>인 반면 Deep Agents Deploy는 완전 오픈.
```

한줄 요약 줄과 주요 내용 섹션 사이에는 빈 줄 하나를 둡니다.

### 5단계: 통합 파일 생성

파일명은 3.7단계에서 생성한 **노트북 제목**(`YY-MM-DD auto-web (N건) <요약>`)을 그대로 사용합니다.

- 그날 수집된 글이 **0개면 파일을 만들지 않고** "기준 날짜 {DATE}에 새 글이 없습니다"만 출력 후 종료.

예시 파일명:
- `26-04-10 auto-web (5건) LangChain 에이전트 배포와 오픈소스 하네스 트렌드.md`
- `26-04-07 auto-web (3건) MitchellHashimoto 빌딩블록 경제학.md`

**중요: 같은 날짜 파일은 항상 덮어씁니다.** 절차:

1. `mcp__mcp-obsidian__obsidian_list_files_in_dir`로 `_Inbox/web-tracking/` 폴더를 조회.
2. `<YY-MM-DD> auto-web`로 시작하는 파일이 하나라도 있으면 **전부 삭제** (`confirm: true`).
3. `mcp__mcp-obsidian__obsidian_append_content`로 새 파일을 생성합니다.

이 방식은 사용자의 명시적 요구로, "같은 날짜에 대해 가장 최근 실행 결과만 남긴다"는 원칙입니다. 부분 업데이트(기존 내용 유지 + 새 글만 추가)는 하지 않습니다 — 발행 시각이 같은 날짜 안에서 바뀌거나, 요약 포맷이 업데이트되었을 때 같은 파일 안에서 옛 버전과 새 버전이 섞이는 것을 방지하기 위함입니다.

파일 내부의 마크다운 형식은 다음과 같습니다:

```markdown
# Web Tracking - YYYY-MM-DD

> 수집 기준: YYYY-MM-DD (KST 하루) | 총 N개 글 (M개 사이트 중 K개 사이트에서)

---

## 🔗 NotebookLM

- **노트북**: [<노트북 제목>](https://notebooklm.google.com/notebook/<notebook_id>)
- **오디오 오버뷰**: 생성 완료 (NotebookLM에서 재생 가능)
- **정리된 과거 노트북**: N개 삭제 (20일 초과). 없으면 "없음".

---

## 제프리 헌틀리 (ghuntley.com)

### [글 제목](https://ghuntley.com/post-url)
> 발행: 2026-04-10 14:32

**한줄 요약:** 글 전체를 **핵심 키워드**가 굵게 강조된 한 문장으로 압축.

**주요 내용:**
- 첫 번째 핵심 불릿. **가장 중요한 키워드**는 굵게 강조.
- 두 번째 불릿. **중요한 수치**나 **제품명**을 자연스럽게 포함.
- 세 번째 불릿.

---

## langchain blog (blog.langchain.com)

### [글 제목](URL)
> 발행: 2026-04-10 09:00

**한줄 요약:** ...

**주요 내용:**
- ...
- ...
- ...

---

#web-tracking #daily
```

**형식 규칙:**

- 사이트 섹션 헤더는 `## {tracking list의 이름} ({호스트명})` — 호스트명은 URL에서 `www.` 접두사를 뗀 도메인만 사용합니다.
- **새 글이 없는 사이트는 섹션 자체를 만들지 않습니다.** 채널명도 출력하지 않고 아예 생략합니다. 파일 상단 요약 줄에서 전체 사이트 수 대비 실제로 새 글이 나온 사이트 수를 `(M개 사이트 중 K개 사이트에서)` 형태로 표시해 "확인은 했다"는 사실을 메타데이터로만 남깁니다.
- 상단 요약 줄의 `총 N개 글`은 전체 새 글 개수, `M개 사이트`는 tracking list의 전체 사이트 수, `K개 사이트`는 그중 새 글이 있었던 사이트 수입니다.
- 제목은 원문 언어 그대로 두되, 요약 불릿은 한국어로 작성하고 **굵게 강조**를 포함합니다.

### 6단계: 완료 보고

사용자에게 간결하게 보고합니다:

```
Web tracking 완료! (기준: YYYY-MM-DD)
- tracking list: N개 사이트 (확인 완���)
- 새 글: M개 (K개 사이���에서)
  - 제프리 ��틀리: 2개
  - langchain blog: 3개
- NotebookLM: [노트북 링크](https://notebooklm.google.com/notebook/<id>)
- 오디오 오���뷰: 생�� 완료
- 저장: _Inbox/web-tracking/<노트북 제목>.md
```

완료 보고에도 새 글이 없는 사이트는 줄로 표시하지 않고, 전체 N개 사이트 중 몇 개 사이트에 새 글이 있었는지만 `(K개 사이트에서)`로 집계합니다.

## 오류 처리

- **tracking list 파일이 없음**: "tracking list.md 파일이 없습니다. _Inbox/web-tracking/!tracking list.md를 먼저 만들어주세요" 출력 후 종료
- **모든 사이트에서 새 글 없음**: 빈 파일을 만들지 말고 "기준 날짜 {DATE}에 새 글이 없습니다" 메시지만 출력 후 종료 (저장 건너뜀)
- **하나의 사이트 실패**: 다른 사이트는 계속 진행 — 전체 실행을 멈추지 않음
- **잘못된 날짜 형식**: 1단계에서 즉시 종료

## 새 사이트 추가 후 NO_ITEMS가 나올 때 (트러블슈팅)

tracking list에 새 URL을 추가했는데 예상한 글이 안 잡힐 때, 원인은 대부분 아래 다섯 유형 중 하나입니다. 순서대로 체크하면 3분 안에 원인을 찾을 수 있습니다.

### 진단: `--debug` 플래그 사용

```bash
python3 .claude/skills/web-tracking/scripts/fetch_site.py "<새-URL>" "<최근 글 있는 날짜>" --debug
```

`--debug`는 stderr에 다음을 출력합니다:

- 피드 디스커버리 경로
- `raw_items` 개수 (필터 전 수집된 항목)
- 적용된 날짜 윈도우 (KST)
- 각 항목의 발행 시각과 제목, 그리고 윈도우 내부 여부(`✓` 마커)

이 출력만 보면 어떤 유형인지 즉시 판별됩니다.

### 유형별 원인과 대응

| 유형 | 증상 (debug 출력) | 원인 | 대응 위치 |
|---|---|---|---|
| **A. 날짜 파싱 실패** | `feed: <url>` 로그 후 `raw_items`에 "NO DATE" 표시 항목이 많음 | `parse_date_any`가 해당 포맷을 모름 | `fetch_site.py` `parse_date_any` 함수의 `strptime` 포맷 리스트에 한 줄 추가 |
| **B. JS 렌더링 SPA** | `no feed discovered` + `html fallback: 0 items` + 개별 글 페이지도 텍스트 없음 | 초기 HTML이 비어있고 JS가 DOM을 만듦 | 해당 사이트는 urllib로는 불가. 대체 경로(트위터 RSS, Medium mirror, 저자 github feed 등) 찾거나 스킵. 마지막 수단으로 개별 글 페이지 JSON-LD 추출 (`fetch_article_date` 패턴) |
| **C. 사이트별 DOM 구조 특이** | `raw_items > 0`인데 전부 윈도우 밖 (✓ 없음) | 날짜 윈도우는 맞지만 해당 날에 글 없음 — 문제가 아님. 또는 prefix가 특이해 Strategy 2가 못 잡음 | 실제로 해당 날에 글이 있다면 `html_fallback` Strategy 2의 prefix 추출을 개선하거나 사이트별 어댑터 추가 |
| **D. SSL/네트워크 에러** | `<urlopen error ...>` 에러 메시지 | CA 번들, 프록시, 타임아웃 | 스크립트는 이미 `certifi` 기반 SSL context를 쓰므로 이 유형은 거의 안 나옴. 나온다면 `TIMEOUT` 늘리기 또는 `USER_AGENT` 교체 |
| **E. 피드에 날짜 필드 없음** | `feed: <url>` + `feed items lack dates, hydrating via per-article JSON-LD/meta` + 여전히 0개 | Google 스타일 RSS처럼 피드가 link만 주고, 개별 글 페이지에도 JSON-LD가 없음 | `fetch_article_date`의 탐색 순서(JSON-LD → og:article:published_time → meta pubdate → time tag)를 개별 글 HTML로 직접 확인하고 추가 패턴 구현 |

### 디버그 출력 예시

```
[web-tracking] site=https://blog.langchain.com/ date=2026-04-10 (KST)
  [debug] raw_items: 15
  [debug] window: 2026-04-10 00:00:00+09:00 ~ 2026-04-11 00:00:00+09:00 (KST)
  [debug]   [0] 2026-04-11 23:52  Your harness, your memory
  [debug] ✓ [1] 2026-04-10 02:00  Previewing Interrupt 2026
  [debug] ✓ [2] 2026-04-10 00:40  Deep Agents Deploy
  [debug] ✓ [3] 2026-04-10 00:00  Human judgment in the agent improvement loop
  [debug]   [4] 2026-04-09 04:30  Better Harness
```

`✓` 마커가 달린 항목이 윈도우 내부이고, 마커 없는 건 윈도우 밖입니다. `NO DATE`가 나오면 유형 A, 마커 없는 항목이 많은데 실제로는 있어야 한다면 유형 C.

### 새 사이트 추가 체크리스트

1. `--debug`로 해당 사이트의 "최근 1주일 안에 확실히 글이 있는 날짜"로 테스트 (하루짜리 필터는 안 걸리기 쉬움)
2. 출력에서 유형 판별 → 대응
3. 수정 후 같은 명령 재실행해 ✓ 마커가 달리는지 확인
4. 실제 tracking list에 URL 추가
