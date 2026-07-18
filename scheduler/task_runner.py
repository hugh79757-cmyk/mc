"""
task_runner.py — 스케줄러에서 호출되는 래퍼

사용법:
  python scheduler/task_runner.py <chain_id>

launchd/cron에서 직접 chain_publisher.py를 호출하는 대신
이 래퍼를 통해 실행하면 로그, 에러 핸들링 일관성 유지.
"""

import os
import sys
import traceback

MC_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, MC_ROOT)


def run_chain_publish(chain_id: int):
    """체인 publish 실행 (스케줄러용 엔트리)."""
    try:
        from chain_publisher import publish_chain
        publish_chain(chain_id)
        print(f"[scheduler] ✅ Chain #{chain_id} published successfully")
    except Exception as e:
        print(f"[scheduler] ❌ Chain #{chain_id} failed: {e}")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python task_runner.py <chain_id>")
        sys.exit(1)
    chain_id = int(sys.argv[1])
    sys.exit(run_chain_publish(chain_id))
