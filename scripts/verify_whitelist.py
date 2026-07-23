#!/usr/bin/env python3
"""verify_whitelist.py — 화이트리스트 도메인 HTTP 검증.

Usage:
    python scripts/verify_whitelist.py

검증 대상:
    chain_card_injector.py의 AUTHORITY_WHITELIST 도메인 전체

결과:
    - 200/301/302 등 (존재 확인): 통과
    - 403/405 (봇 탐지): 경고 (도메인 존재하나 차단)
    - 404/CONN_ERR/TIMEOUT: 실패 → 화이트리스트에서 제거 필요
"""

import sys
import requests

sys.path.insert(0, "/Users/twinssn/projects2/mc")
from chain_card_injector import AUTHORITY_WHITELIST

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}


def verify_domain(domain: str) -> tuple[int | str, str]:
    """도메인 HTTP 상태 반환. (status_code_or_error, verdict)"""
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            if resp.status_code < 400:
                return (resp.status_code, "OK")
            elif resp.status_code in (403, 405):
                return (resp.status_code, "WARN")  # 봇 탐지, 도메인 존재
            else:
                return (resp.status_code, "FAIL")
        except requests.exceptions.ConnectionError:
            continue  # http로 재시도
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            continue
    return ("CONN_ERR", "FAIL")


def main():
    print(f"화이트리스트 검증: {len(AUTHORITY_WHITELIST)}개 도메인")
    print("=" * 60)

    ok = []
    warn = []
    fail = []

    for domain, label in AUTHORITY_WHITELIST.items():
        status, verdict = verify_domain(domain)
        icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}[verdict]
        print(f"  {icon} {domain:<25} {label:<15} {str(status):<10} {verdict}")
        if verdict == "OK":
            ok.append(domain)
        elif verdict == "WARN":
            warn.append(domain)
        else:
            fail.append(domain)

    print("=" * 60)
    print(f"✅ 통과: {len(ok)}/{len(AUTHORITY_WHITELIST)}")
    if warn:
        print(f"⚠️ 경고 (봇 탐지): {warn}")
    if fail:
        print(f"❌ 실패 (제거 필요): {fail}")

    return len(fail) == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
