### 🤖 agent-context-store
AI 에이전트(Claude Code, Cursor 등)의 지능적 협업과 일관된 코드 컨벤션 주입을 위한 중앙 컨텍스트 저장소입니다.

### 🎯 목적
이 레포지토리는 개발팀의 엔지니어링 표준, 반복되는 프롬프트 패턴, 그리고 에이전트 전용 스킬셋을 관리합니다.
이를 통해 어떤 환경에서도 AI가 팀의 규칙을 준수하며 개발에 참여하도록 돕습니다.

### 📂 폴더별 관리 가이드라인
1. rules/ (지침 및 규정) https://cursor.com/ko/docs/context/rules
**"어떻게 행동하고 코드를 짜야 하는가?"**에 대한 AI 시스템 레벨 지침
  - 엔지니어링 패턴: 프로젝트 고유 아키텍처, 네이밍 컨벤션, 에러 핸들링 등 (린터가 못 잡는 것 위주)
  - 금지 사항: 특정 타입·라이브러리 사용 제한, 보안 규칙
  - 워크플로우: 커밋 메시지 규격, PR 템플릿, 자동화 절차
  - 적용 방식: Always / Intelligently / Specific Files / Manually

2. agents/ (서브 에이전트) https://cursor.com/ko/docs/context/subagents
**"누가 이 작업을 수행하는가?"**에 대한 전문화된 역할 정의
  - 역할 정의: 특정 도메인에 특화된 서브에이전트 (.md 파일)로, 실행 절차와 보고 형식을 프롬프트로 정의
  - 구성 필드: name, description, model, readonly, is_background
  - 실행 방식: 자동 위임 (description 기반) 또는 명시적 호출 (/name)
  - 위임 구조: 단일 레벨 — 부모→서브에이전트→결과 반환 (중첩 불가)

3. skills/ (재사용 가능한 작업 절차) https://cursor.com/ko/docs/context/skills
**"무엇을 할 수 있는가?"**에 대한 도메인 특화 지시서
  - 워크플로우 자동화: 복잡한 태스크를 단계별로 실행하기 위한 시퀀스 및 도구 사용 순서 가이드.


### 🗂️ 프로젝트 구조
예)
.
├── agents/            # 특정 역할군별 컨텍스트 설정
│   ├── reviewer.md    # 코드 리뷰어 전용 페르소나
│   └── architect.md   # 구조 설계 및 문서화 전용 페르소나
├── rules/             # 에이전트가 준수해야 할 코딩 규칙 및 행동 강령
│   └── git-commit.md  # 커밋 메시지 규칙 (Conventional Commits)
└── skills/            # 반복적인 작업을 수행하는 프롬프트/스크립트 모음
    └── refactoring.md # 코드 리팩토링 및 최적화 전략

### 🚀 사용 방법
1. Cursor에서 사용하기
프로젝트 수준에 적용 시, 프로젝트 최상단 .cursor/ 폴더에 셋팅. 전역 셋팅 원할 경우 ~/.cursor/ 폴더에 적용

2. Claude Code에서 사용하기
Claude Code 실행 시 rules/ 디렉토리의 가이드라인을 컨텍스트로 주입하여, 팀의 특정 라이브러리 활용 방식이나 비즈니스 로직 패턴을 따르도록 명령합니다.

🛠 주요 컨텐츠
📏 Rules (규칙)
- Code Style: ESLint/Prettier 이상의 세밀한 설계 원칙 (예: 함수형 프로그래밍 지향).
- Architecture: 레이어드 아키텍처, 의존성 주입 등 팀 내 합의된 구조 정의.

🧠 Skills (스킬)
- Automated Testing: 테스트 코드 작성 시 반드시 포함되어야 할 Edge Case 체크리스트.
- Documentation: JSDoc 및 README 자동 생성 템플릿.

🤖 Agents (에이전트)
- 특정 목적에 최적화된 시스템 프롬프트를 관리하여 에이전트의 일관성을 유지합니다.

🤝 기여 방법
- 팀 내에서 발견된 유용한 AI 프롬프트나 새로운 코드 컨벤션이 있다면 자유롭게 PR을 날려주세요!
- rules/ 또는 skills/에 새 .md 파일 생성
- 모든 팀원의 IDE에 최신 컨텍스트 동기화
- 사용 예시: AI 에이전트에게 "이 레포지토리의 rules/00000.md를 읽고 내 코드를 리뷰해줘"라고 요청해 보세요.