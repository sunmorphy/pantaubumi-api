import logging
import uuid
import time
import boto3
from botocore.exceptions import ClientError
from app.config import settings

logger = logging.getLogger(__name__)

def get_s3_client():
    if not settings.r2_account_id or not settings.r2_access_key_id:
        return None
        
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )

async def upload_image_to_storage(file_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Upload an image to Cloudflare R2 and return its public URL.
    Returns an empty string if it fails or storage is not configured.
    """
    if not settings.r2_bucket_name or not settings.r2_public_url:
        logger.warning("R2 storage not configured. Cannot upload image.")
        return ""

    s3 = get_s3_client()
    if not s3:
        logger.warning("R2 S3 client could not be initialized.")
        return ""

    try:
        from fastapi.concurrency import run_in_threadpool
        
        ext = filename.split(".")[-1] if "." in filename else "jpg"
        unique_name = f"reports/{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        
        # boto3 is synchronous, run in threadpool
        def _upload():
            s3.put_object(
                Bucket=settings.r2_bucket_name,
                Key=unique_name,
                Body=file_bytes,
                ContentType=content_type,
            )
            
        await run_in_threadpool(_upload)
        
        base_url = settings.r2_public_url.rstrip('/')
        return f"{base_url}/{unique_name}"

    except Exception as e:
        logger.error("R2 storage upload error: %s", e)
        return ""
