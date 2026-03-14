from pydantic import BaseModel, Field


class FCMTokenCreate(BaseModel):
    token: str = Field(
        ...,
        min_length=10,
        description="FCM registration token obtained from the Firebase SDK on the Android device",
    )
    device_id: str = Field(
        default="",
        description="Optional unique device identifier (e.g. Android ANDROID_ID) for deduplication",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Register new Android device",
                    "value": {
                        "token": "eNGvgqk5T6q:APA91bHPRgkFjJiNvmMqLwVxyz...",
                        "device_id": "android-device-uuid-1234",
                    },
                }
            ]
        }
    }


class FCMTokenResponse(BaseModel):
    id: int
    token: str
    device_id: str

    model_config = {"from_attributes": True}
