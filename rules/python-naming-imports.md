---
description: Python 네이밍 컨벤션 및 임포트 스타일
globs: src/**/*.py
alwaysApply: false
---

# 네이밍 컨벤션

- 파일/모듈: `snake_case` (예: `base_agent.py`, `agent_executor.py`)
- 클래스: `PascalCase` (예: `BaseAgent`, `WebSearchAgent`)
- 함수/변수: `snake_case` (예: `setup_logger`, `intent_analyzer`)
- 프라이빗 헬퍼: `_leading_underscore` (예: `_make_shop_tools`)
- 상수: `UPPER_SNAKE_CASE` (예: `KST`, `_SHOP_DATA_DIR`)
- LangGraph 노드 함수: `snake_case` (예: `intent_analyzer`, `action_dispatcher`)

# 임포트 스타일

- 순서: 표준 라이브러리 → 서드파티 → 로컬 모듈
- `src.` 접두사 없이 짧은 모듈 경로 사용
- 같은 패키지 내에서는 상대 임포트 사용

```python
# ✅ GOOD
from common.log import setup_logger
from models.azure import llm_gpt4o
from prompts.prompt_manager import apply_prompt
from .store import RetailStore  # 같은 패키지 내

# ❌ BAD
from src.common.log import setup_logger
import common.log  # 직접 임포트 선호
```

# 타입 힌트

- 내장 제네릭 사용: `list[str]`, `dict[str, Any]`
- `typing`에서 필요한 것만 임포트: `Dict`, `Optional`, `Annotated`
- `str | None` 유니온 문법 허용 (Python 3.13+)
