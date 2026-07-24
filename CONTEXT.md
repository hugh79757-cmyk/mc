# Context — Manual Chain (mc)

> 이 파일은 Phase 18 검증 과정에서 발견된 인프라 격차를 기록한다.
> 새 규칙을 만들기보다, "현재 없다"는 사실만 기록한다.

## 1. metrics 테이블 부족 (검증됨)

- **관찰:** `mc` 시스템 내부에 발행 후 성능(impression, view, CTR) 측정을 위한 독립 테이블이 없음.
- **근거:**
  - DB 스키마 확인: `chain_posts`, `publish_log`, `loop_chains`, `chains` 테이블만 존재
  - `chain_posts` 컬럼: `status`, `published_url`, `published_at` 등만 존재, `impression`/`view`/`ctr` 컬럼 없음
  - 코드 내 검색: `def.*metric`, `performance`, `view`, `impression`, `ctr`, `click` 관련 로직 0건
- **현재 상태:** AdSense/GA는 Hugo 템플릿 수준에서만 운영되고, `mc` DB에는 `publish_log`만 존재
- **영향:** Phase 18 이후 품질 개선 효과를 정량적으로 검증할 수 없음
- **조치:** metrics 테이블/수집 로직은 본 Phase에서 구축하지 않음. 필요 시 별도 Phase로 분리 요망.

## 2. 기타 관찰

- Naver Webmaster Tools / Analytics 연동 코드: `mc` 코드베이스 내 미확인
- DB `database is locked (5)` 오류: 간헐적으로 발생, 일부 정확 쿼리 미확인

---

## 3. 릭 방어 패턴 중복 정의 (잔존 위험, 다음 스프린트)

- **관찰:** 프롬프트 릭 방어 패턴이 D1(`chain_drafter.py _PROMPT_LEAK_RE`, 18개 패턴)과 D10(`audit/audit_chain.py _PROMPT_SECTION_RE`, 9개 패턴)에 독립적으로 정의되어 있음. 패턴 목록이 불일치하면 한쪽은 탐지하지 못하는 릭이 발생 가능.
- **근거:** `chain_drafter.py:361` vs `audit/audit_chain.py:52` — 각각 독자적 regex. JSON 체크도 D6/D8/D9에 4개 독립 regex.
- **영향:** 새 릭 유형이 나올 때마다 N군데를 개별 패치해야 함. 하나라도 누락하면 두더지잡기 재발.
- **조치:** 다음 스프린트에서 공유 상수로 통합 필요. 이번 Phase에서는 손대지 않음.

## 4. 평문 CTA 문구 라이브 노출 가능 (잔존 위험, 다음 스프린트)

- **관찰:** `더 깊이 알아보기`, `더 자세히 보기`, `이어서 실전 적용법`, `관련 주제 보기` 등 Phase 17에서 ABSOLUTE BAN으로 지정한 CTA 문구가 발행 파이프라인(D6 `_extract_clean_body`, D8 `_verify_before_deploy`, D9 산출물 검증)에 필터 없음. 현재 D11(conftest.py `assert_no_cta_leak`) 테스트에서만 차단.
- **근거:** `conftest.py:398-402`에 4개 금지 표현 정의되어 있으나, `chain_publisher_core.py`의 D6/D8/D9에는 CTA 텍스트 검사하는 로직 0건. 라이브 URL(rotcha.kr K2선풍기조끼 글)에서 AI가 생성한 `<div>...더 깊이 알아보기→</div>` 블록이 그대로 렌더링 확인됨.
- **영향:** AI가 Step3 실전형 글에서 자연스럽게 CTA 스타일 문구를 생성하면 발행 파이프라인을 모두 통과하여 라이브에 노출됨. 단기적 실피해 보고는 없음.
- **조치:** 다음 스프린트에서 D6 또는 D8에 CTA 텍스트 필터 추가 필요. 이번 Phase에서는 손대지 않음.

---

*기록일: 2026-07-24*
*Phase: 19*
*금지 사항 확인: affiliate/CPA 링크 없음, FTC disclosure 언어 없음, 7:1 density 개념 없음*
