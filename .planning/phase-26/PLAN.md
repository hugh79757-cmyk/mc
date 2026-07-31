# PLAN.md — Phase 26: 코드베이스 리팩터링 (리팩토링을 통한 중복 제거 및 복잡도 감소)

## 목표
MC 코드베이스의 중복을 제거하고 복잡도를 낮추며, 기사 형식 품질과 유지보수성을 향상시키는 점진적인 리팩터링을 수행한다. 기존 기능은 완전히 보존하면서 코드 구조를 모듈화하고, 테스트 커버리지를 높이며, 향후 기능 확산을 용이하게 만든다.

## 개요
이 페이즈는 세 가지 주요 영역으로 구성된다:
1. **Foundation** – 프론트매터, URL 처리, 상수 등을 유틸리티 모듈로 추출·통합
2. **Component Simplification** – 카드 주입 로직을 역할 기반 클래스(LinkFinder, CardGenerator, HtmlRenderer)로 분리하고 퍼사드 패턴으로 기존 인터페이스 유지
3. **Advanced Optimizations** – 이미지 제공자 베이스 클래스, 캐시 매니저, JSON-Schema 설정 검증, 마크다운 처리 파이프라인 리팩터링

각 작업은 기존 테스트(251개)를 통과하는 것을 전제로 하며, 가능하면 추가 단위 테스트를 작성하여 회귀를 방지한다.

## 작업 목록 (Wave 기준)

### Wave 1 – Foundation
| ID | 작업 | 설명 | 산출물 | 검증 방법 |
|----|------|------|--------|-----------|
| F1 | `frontmatter_utils.py` 생성 | `ensure_frontmatter(text, meta)` 단일 함수 구현 | `chain.py`, `chain_publisher_core.py`의 `_ensure_frontmatter`, `_ensure_frontmatter_closer` 대체 | 단위 테스트 (프론트매터 생성/검증) + 기존 테스트 통과 |
| F2 | `url_utils.py` 생성 | 도메인 추출, 정규화, 트래킹 파라미터 제거 함수 제공 | 기존 광고/카드 로직에서 직접 문자열 조작 코드를 `url_utils` 함수 호출로 대체 | 단위 테스트 (URL 변환 케이스) + 기존 테스트 통과 |
| F3 | `constants.py` 생성 | `AUTHORITY_DOMAINS`, `SKIP_DOMAINS`, 정규표현식 패턴 등 하드코딩 상수 중앙집중 | 각 파일에서 상수 import 대신 `constants`에서 가져오도록 수정 | import 구문 검사 + 기존 테스트 통과 |
| F4 | Import 수정 | 위 세 모듈을 사용하도록 관련 파일(`chain_drafter.py`, `chain_publisher_core.py`, `chain_card_injector.py`, `image/` 등) 수정 | - | 린트/import 오류 없음 + 기존 테스트 통과 |
| F5 | 기존 중복 함수 삭제 | `_ensure_frontmatter`, `_ensure_frontmatter_closer` 등 중복 구현 제거 | - | 코드 중복 검사 도구 (예: `duplicates`) 보고서 0 + 기존 테스트 통과 |

### Wave 2 – Component Simplification (Card Injector)
| ID | 작업 | 설명 | 산출물 | 검증 방법 |
|----|------|------|--------|-----------|
| C1 | `LinkFinder` 클래스 설계 | `find_links(text) -> List[Dict]` 인터페이스 구현 | `link_finder.py` (또는 `card_injector/link_finder.py`) | 단위 테스트 (다양한 HTML 입력에 대한 링크 추출 정확도) |
| C2 | `CardGenerator` 클래스 설계 | 링크 딕셔너리 + 포스트 메타 → 카드 스펙 생성 | `card_generator.py` | 단위 테스트 (예상 출력과 비교) |
| C3 | `HtmlRenderer` 클래스 설계 | 템플릿 문자열 기반 HTML 생성 (next/internal/official) | `html_renderer.py` | 단위 테스트 (템플릿 렌더링 결과) |
| C4 | 퍼사드 유지 | 기존 `chain_card_injector.inject_*` 함수를 새 클래스를 활용하도록 리팩터링 (퍼사드) | `chain_card_injector.py` (리팩터링 버전) | 기능 테스트: 기존 출력과 동일 스냅샷 테스트 |
| C5 | 포괄적 단위 테스트 추가 | 각 새 클래스에 대해 커버리지 90% 이상 목표 | `test_link_finder.py`, `test_card_generator.py`, `test_html_renderer.py` | coverage 보고서 |
| C6 | 통합 테스트 | 샘플 체인(1~3단계) 실행하여 카드 삽입 결과가 변경되지 않음 확인 | - | 기존 스냅샷 테스트 또는 금 파일 비교 |
| C7 | 사용하지 않는 데드 코드 삭제 | 리팩터링 후 사용되지 않는 헬퍼 함수 제거 | - | lint/unused-import 검사 |
| C8 | 문서화 | 각 클래스의 책임과 사용법 설명 docstring 추가 | - | 코드 리뷰 |

### Wave 3 – Advanced Optimizations
| ID | 작업 | 설명 | 산출물 | 검증 방법 |
|----|------|------|--------|-----------|
| A1 | 이미지 제공자 베이스 클래스 | `image/base_provider.py`에 `fetch`, `validate` 인터페이스 정의 | `base_provider.py` | 기존 구현(`unsplash_provider.py`, `pexels_provider.py`)이 인터페이스를 구현하도록 수정 후 단위 테스트 |
| A2 | 캐시 매니저 | `image/cache_manager.py`에 LRU/TTL 캐시 구현 (전역 싱글톤 또는 의존성 주입) | `cache_manager.py` | 캐시 히트/미스 테스트, 수명 만료 검증 |
| A3 | 기존 이미지/프롬프트 모듈 리팩터링 | `search_providers.py`, `prompt_builder.py`에서 베이스 클래스 및 캐시 사용 | - | 기존 기능 동작 확인 (이미지 다운로드/프롬프트 생성) |
| A4 | JSON-Schema 정의 | `config/schema.yaml`에 `prompts.yaml`, `keyword_mapping.yaml` 구조 기술 | `schema.yaml` | 스키마 파일 자체 검증 (yamllint) |
| A5 | 설정 검증 훅 추가 | 설정 로드 시 jsonschema 로 검증, 오류 시 명확한 메시지 출력 | `config/loader.py` (또는 기존 로더 수정) | 잘못된 구성 파일로 실패 테스트, 정상 파일 통과 테스트 |
| A6 | `MarkdownProcessor` 클래스 추출 | `chain_publisher_core.py`에서 누수 방지, 심볼 클리닝, 테이블 보호 로직을 클래스로 분리 | `markdown_processor.py` | 단위 테스트 (각 처리 단계) |
| A7 | 프론트매터 처리 위임 | `MarkdownProcessor` 내에서의 프론트매터 처리는 `frontmatter_utils.ensure_frontmatter` 사용 | - | 기존 테스트 통과 |
| A8 | Hugo 전용 함수 분리 | `_publish_hugo` 는 Hugo‑specific frontmatter 및 이미지 처리만 담당 | - | 변경 전후 Hugo 빌드 결과 동일 확인 |
| A9 | 누수 방어 상수 통합 | `leak_defense.py`에 모듈레벨 상수 참조 (예: `constants.LEAK_PATTERNS`) 사용으로 일관화 | - | 중복 제거 검사 |
| A10 | 성능 회귀 체크 | 리팩터링 전후 중요 경로(링크 찾기, 카드 생성, 마크다운 처리) 벤치마크 | - | 성능 저하 <5% 허용 (간단한 timeit 스크립트) |
| A11 | 전체 테스트 스위트 실행 | 모든 단위/통합 테스트가 통과하도록 보장 | - | `pytest -q` 통과 (251/251) |
| A12 | 문서 및 주석 업데이트 | 새 모듈/클래스에 적절한 docstring 및 인라인 주석 추가 | - | 코드 리뷰 |

## 의존성
- **선행 단계**: Phase 22 (품질 게이트), Phase 23 (자동 재작성 루프) – 직접적인 블로킹 없음
- **후행 단계**: Phase 27 이후 – 리팩터링된 기반 위에 신규 기능 추가 시 이득

## 리스크 및 완화 방안
| 리스크 | 가능성 | 영향 | 완화 방안 |
|--------|--------|------|-----------|
| Import-time side effect (예: 모듈 로드 시 부수효과)로 import-only 재사용 깨짐 | 낮음 | 높음 | 최상위 코드를 `if __name__ == "__main__":` 로 보호하거나 함수 내로 이동 |
| 카드 삽입 동작 변경으로 인한 스냅샷 불일치 | 중간 | 중간 | 속성 기반 테스트: 랜덤 HTML 입력에 대해 리팩터 전/후 출력 비교 (스냅샷) |
| JSON-Schema가 너무 엄격해서 기존 유효한 YAML을 거부 | 낮음 | 중간 | 관대한 스키마부터 시작해 점진적으로 제약 추가, 기존 설정 파일 모두 검증 후 적용 |
| 간접 레이어 추가로 인한 성능 저하 | 낮음 | 낮음 | 주요 경로 벤치마크 수행, 목표 ≤5% 변동; 필요시 인라인 최적화 |
| URL 유틸리티 에러로 인한 깨진 링크 | 낮음 | 높음 | 포괄적인 단위 테스트 (트래킹 파라미터 제거, 스키마/프래그먼트 처리, 국제화 도메인 등) |

## 성공 기준 (Acceptance Criteria)
1. 모든 기존 테스트가 통과한다 (251/251).
2. 신규 단위 테스트가 추가되어 주요 리팩터링 컴포넌트에 대한 커버리지가 90% 이상이다.
3. 커밋 전 `git diff --check` 및 린트 오류가 없다.
4. 수동 검증: 임의의 시드 키워드(예: `"알프스대영CC"`) 로 체인 #296 전 과정을 실행했을 때,
   - 각 단계(1,2,3) 초안이 정상 생성되며 총 소요 시간이 30초 이내이다.
   - 생성된 마크다운은 앞부분 노출, 플레이스홀더 잔존, 잘못된 CTA 등의 릭이 없다.
   - Hugo 사이트(rotcha, informationhot, techpawz, issue-techpawz) 빌드가 성공하고 결과물이 기존과 시각적으로 동일하다.
5. 구성 파일 검증이 작동하여 잘못된 YAML은 명확한 오류 메시지와 함께 실패한다.
6. 캐시 및 이미지 제공자 교체가 기존 기능에 영향을 주지 않는다 (모킹을 사용한 단위 테스트 통과).

## 다음 단계
1. 디렉토리 `.planning/phase-26` 가 존재함을 확인 (이미 존재).
2. 본 `PLAN.md` 가 작성되었으므로, 필요한 경우 `gsd-planner --phase 26` 로 초안을 다듬을 수 있음 (현재는 이미 계획을 바탕으로 작성됨).
3. `gsd-execute-phase --phase 26` 를 실행하여 작업을 진행한다.
4. 진행 중 주기적으로 `gsd-plan-checker --phase 26` 를 실행해 검증한다.
5. 검증이 통과되면 해당 단계를 완료 표시하고 다음 단계로 넘어간다.
6. 모든 작업이 완료되고 최종 검증이 통과되면 단계 완료 표시하고, 다음 미계획 단계(27)로 이동한다.

---
*이 계획은 위 연구 결과를 바탕으로 작성되었으며, GSD 워크플로우(리서치 → 플랜 → 검증 → 완료)의 플랜 단계에 해당한다. 실행 시 위 워크플로우 지침을 따를 것.*