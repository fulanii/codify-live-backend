import uuid
import logging
from fastapi import Request

logger = logging.getLogger(__name__)

async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())

    logger.info(f"[REQ {request_id}] {request.method} {request.url.path}")

    try:
        response = await call_next(request)
        logger.info(f"[REQ {request_id}] {response.status_code}")
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        logger.exception(f"[REQ {request_id}] Unhandled error")
        raise
