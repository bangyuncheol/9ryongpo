---
description: qa-regression 스킬을 로드해 회귀 QA 체크리스트를 수행한다
---

`.claude/skills/qa-regression/` 스킬을 로드하고 `checklist.md` 에서 다음 영역의 항목을 수행한다. 영역: $ARGUMENTS (비어 있으면 전체)

## 출력 형식
1. 수행한 항목 표 — 항목 / 결과(✅ ❌ ⏭) / 비고
2. 실패 항목 상세 — 재현 절차와 관찰된 동작
3. 후속 조치 제안

작성 시 준수사항:
- 확인하지 못한 항목을 통과로 표시하지 않는다.
- 실패 항목은 `.claude/skills/project-history/bug-fix.md` 에 기록할 문구를 함께 제안한다.
