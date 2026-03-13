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


@router.post(
    "/fcm-token",
    response_model=APIResponse[FCMTokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Register or update a device FCM token for push notifications",
)
@limiter.limit("20/minute")
async def register_fcm_token(
    request: Request,
    payload: FCMTokenCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a device's Firebase Cloud Messaging token.

    - If the token already exists, its `device_id` is updated (upsert).
    - Tokens are used to send push notifications for high-severity alerts.
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
