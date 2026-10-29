# failure_injection.py - 운영 장애 주입 도구 (제공 코드)
"""FAILURE_MODE 환경 변수로 장애 종류를 골라 주입합니다.
값: timeout | rate_limit | bad_schema | none

실행 예:
  $env:FAILURE_MODE="timeout"; python failure_agent.py
"""
import os
import time
import logging
from langchain_core.tools import tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.FileHandler("agent.log", encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger("tools")

FAILURE_MODE = os.environ.get("FAILURE_MODE", "none")
API_KEY = os.environ.get("INTERNAL_API_KEY", "sk-internal-dummy-1234")   # 점검용 더미 Secret


class RateLimitError(Exception):
    pass


def _call_backend(asset_id: str) -> dict:
    """가짜 자산 관리 백엔드 호출. FAILURE_MODE에 따라 장애를 재현한다."""
    # 주의: Secret은 절대 로그에 남기지 않습니다. 마스킹해서 기록.
    logger.info("backend 호출 asset_id=%s api_key=%s***", asset_id, API_KEY[:6])

    if FAILURE_MODE == "timeout":
        time.sleep(5)                      # 응답 지연 재현
        raise TimeoutError("backend 응답이 5초를 초과했습니다")
    if FAILURE_MODE == "rate_limit":
        raise RateLimitError("429 Too Many Requests: 분당 호출 한도 초과")
    if FAILURE_MODE == "bad_schema":
        return {"assetStatus": "사용중인듯"}   # 계약(status, owner 키)과 다른 응답
    return {"asset_id": asset_id, "status": "사용중", "owner": "김하늘"}


@tool
def get_asset_status(asset_id: str) -> str:
    """자산 관리 백엔드에서 자산 ID로 현재 상태를 실시간 조회한다.

    Args:
        asset_id: 자산 ID (예: 'A-1001')
    """
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            data = _call_backend(asset_id)

            # bad_schema 방어: 응답 계약 검증 (재시도해도 소용없으므로 즉시 fallback 안내)
            if "status" not in data or "owner" not in data:
                logger.error("응답 스키마 불일치: keys=%s", list(data.keys()))
                return ("에러: 백엔드 응답 형식이 올바르지 않습니다. "
                        "get_asset_status_backup 도구를 대신 사용하세요.")

            return f"{data['asset_id']}: {data['status']} (사용자: {data['owner']})"

        except RateLimitError as e:
            wait = 2 ** attempt                    # 2초, 4초, 8초
            logger.warning("rate limit (시도 %d/%d), %d초 대기: %s", attempt, max_retries, wait, e)
            if attempt == max_retries:
                return "에러: 호출 한도를 초과했습니다. get_asset_status_backup 도구를 사용하세요."
            time.sleep(wait)

        except TimeoutError as e:
            logger.warning("timeout (시도 %d/%d): %s", attempt, max_retries, e)
            if attempt == max_retries:
                return "에러: 백엔드 응답이 계속 지연됩니다. get_asset_status_backup 도구를 사용하세요."

        except Exception as e:
            logger.exception("예상 못한 장애")
            return f"에러: 조회 실패 ({type(e).__name__}). get_asset_status_backup 도구를 사용하세요."


@tool
def get_asset_status_backup(asset_id: str) -> str:
    """백업 자산 상태 조회. get_asset_status 실패 시 사용한다. 1시간 전 스냅샷 기준이라 느리지만 안정적이다."""
    logger.info("backup 경로 사용 asset_id=%s", asset_id)
    return f"{asset_id}: 사용중 (백업 스냅샷 기준, 갱신 주기 1시간)"