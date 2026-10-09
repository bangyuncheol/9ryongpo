# 이 템플릿으로 새 프로젝트 시작하기

> 이 파일은 템플릿 사용 설명서다. **새 프로젝트에서는 아래 체크리스트를 끝낸 뒤 삭제한다.**

## 무엇이 들어 있나

`ai_facilitator_jhk` 저장소의 초기 세팅 커밋(`dbc6390`, 2026-09-15)에서 프로젝트 고유 내용을 뺀 것.
4계층 문서 구조 — 절대 규칙(`CLAUDE.md`) · 작업 규칙(`.claude/rules/`) · 스펙/이력(`.claude/skills/`) · 반복 절차(`.claude/commands/`) 와 `.gitignore`.

```
CLAUDE.md                      절대 규칙의 유일한 정본 (세션 시작 시 자동 로드)
.gitignore
.claude/
  rules/      8개              database · permissions · server-code · file-structure ·
                               testing · error-handling · git-workflow · ui-design
  skills/     6개              db-schema · requirements · deploy · qa-regression ·
                               project-status · project-history
  commands/   4개              /feature-plan · /db-change-plan · /qa · /deploy-check
```

## 새 레포 만드는 두 가지 방법

**A. GitHub 템플릿 (권장)** — 이 저장소를 GitHub 에서 Settings → General → "Template repository" 체크.
이후 새 프로젝트는 GitHub 의 "Use this template" 버튼 → 레포 이름·비공개 선택 → 클론. 히스토리 없이 깨끗한 첫 커밋으로 시작한다.

```bash
gh repo create <owner>/<new-repo> --private --template <owner>/claude-project-template --clone
```

**B. 로컬 복사** — GitHub 를 거치지 않을 때.

```bash
git clone --depth 1 <템플릿 URL> <new-repo> && cd <new-repo> && rm -rf .git && git init -b main
```

## 채워야 할 자리표시자 (체크리스트)

`grep -rn '<' CLAUDE.md .claude/` 로 `<...>` 자리표시자를 찾는다.

- [ ] `CLAUDE.md` — `<프로젝트명>` 과 한 문단 설명. 기술 스택 4줄은 확정 전까지 "미정"으로 둔다
- [ ] `.claude/rules/git-workflow.md` — `<GitHub URL>`, `<GitHub ID>`
- [ ] `.claude/skills/project-history/legacy-docs-note.md` — `<YYYY-MM-DD>`
- [ ] `.claude/skills/project-history/work-log-YYYY-MM-DD.md` — 파일명을 오늘 날짜로 바꾸고 첫날 한 일 기록
- [ ] 이 파일(`TEMPLATE_SETUP.md`) 삭제
- [ ] 첫 커밋: `docs: CLAUDE.md + .claude/rules 8개 · skills 6개 · commands 4개 생성 (문서 구조 템플릿 도입)`

## 스택이 정해진 뒤 채우는 곳

템플릿의 `paths:` 는 Next.js 식(`src/app/**`, `src/components/**`)이 기본값이다. 스택이 다르면 고친다.

- `.claude/rules/file-structure.md` — `src/` 아래 세부 폴더 규칙
- `.claude/rules/server-code.md` — `paths:` 와 "코드 예시"
- `.claude/rules/testing.md` — `paths:` 와 "실행 방법"
- `.claude/rules/ui-design.md` — `paths:` 와 "디자인 기준"
- `.claude/rules/permissions.md` · `database.md` — `paths:`
- `.claude/skills/deploy/SKILL.md` — 배포 플랫폼, 환경 변수 **이름** 목록 (값 금지)
- `.claude/skills/db-schema/` — DB 가 없으면 "없음"이라고 적고 둔다 (삭제하지 않는다 — `/db-change-plan` 이 참조)

## 운영 원칙 (템플릿이 전제하는 것)

- 같은 규칙을 두 문서에 적지 않는다. 정본 하나 + 포인터.
- 오너 결정은 결정일과 함께 적는다: `(오너 결정 YYYY-MM-DD)`.
- 완료된 것은 `project-status` 에서 내리고 `project-history/resolved-items.md` 로.
- 의도적으로 안 하는 것은 `CLAUDE.md` "의도적으로 하지 않는 것"에만.
