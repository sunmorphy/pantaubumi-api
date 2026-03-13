from pydantic import BaseModel, Field


class FCMTokenCreate(BaseModel):
    token: str = Field(..., min_length=10, description="FCM registration token from Firebase SDK")
    device_id: str = Field(default="", description="Optional device identifier")


class FCMTokenResponse(BaseModel):
    id: int
    token: str
    device_id: str

    model_config = {"from_attributes": True}
