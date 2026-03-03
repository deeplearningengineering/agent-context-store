---
description: 로깅 및 에러 처리 패턴
globs: src/**/*.py
alwaysApply: false
---

# 로거 설정

- `common.log.setup_logger` 사용, 모듈 최상단에서 초기화
- 로거 이름은 항상 `__name__` 사용

```python
# ✅ GOOD
from common.log import setup_logger
logger = setup_logger(__name__)

# ❌ BAD
import logging
logger = logging.getLogger(__name__)  # setup_logger 사용할 것
```

# 에러 처리

- `try/except`에서 `logger.exception()` 또는 `logger.error()` 사용
- 빈 except 금지 — 반드시 로깅 또는 재전파
- 도구(tool) 에러는 `{"status": "error", "message": ...}` JSON 형태로 반환
- A2A 프로토콜 에러는 `ServerError` 사용
- `asyncio.CancelledError`는 SSE 취소 시 별도 처리

```python
# ✅ GOOD
try:
    result = await some_async_operation()
except Exception as e:
    logger.exception(f"작업 실패: {e}")
    raise

# ❌ BAD
try:
    result = await some_async_operation()
except Exception:
    pass
```
