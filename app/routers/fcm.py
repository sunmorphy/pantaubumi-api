from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.fcm_token import FCMToken
from app.schemas.fcm import FCMTokenCreate, FCMTokenResponse
from app.schemas.response import APIResponse, ok

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_RESPONSE_200 = {
    "content": {
        "application/json": {
            "example": {
                "code": 200,
                "status": "Success",
                "message": None,
                "data": {
                    "id": 3,
                    "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwV...",
                    "device_id": "android-device-uuid-1234",
                },
            }
        }
    }
}

_RESPONSE_429 = {
    "description": "Rate Limit Exceeded",
    "content": {
        "application/json": {
            "example": {
                "code": 429,
                "status": "Too Many Requests",
                "message": "20 per 1 minute",
                "data": None,
            }
        }
    },
}


@router.post(
    "/fcm-token",
    response_model=APIResponse[FCMTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Register or update a device FCM token for push notifications",
    responses={200: _RESPONSE_200, 429: _RESPONSE_429},
)
@limiter.limit("20/minute")
async def register_fcm_token(
    request: Request,
    payload: FCMTokenCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a device's Firebase Cloud Messaging (FCM) token for push notifications.

    **Upsert semantics:** posting the same `token` again updates its `device_id` — the row
    is not duplicated.

    **When are push notifications sent?**
    The background scheduler broadcasts to all registered tokens when a **`high`** or
    **`critical`** earthquake alert is detected (USGS M≥4.5 within Indonesia).

    **Rate limit:** 20 requests / minute / IP
    """
    result = await db.execute(
        select(FCMToken).where(FCMToken.token == payload.token)
    )
    token_row = result.scalar_one_or_none()

    if token_row:
        token_row.device_id = payload.device_id
    else:
        token_row = FCMToken(
            token=payload.token,
            device_id=payload.device_id,
        )
        db.add(token_row)

    await db.flush()
    await db.refresh(token_row)

    return ok(data=FCMTokenResponse.model_validate(token_row).model_dump(mode="json"))
