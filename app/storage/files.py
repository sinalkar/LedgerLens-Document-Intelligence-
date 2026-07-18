import io
import os

from PIL import Image

from app.config import get_settings


class LocalFileStore:
    def save(self, doc_id: str, img: Image.Image) -> str:
        path = os.path.join(get_settings().upload_dir, doc_id, "watermarked.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path)
        return path


class GCSFileStore:
    """Cloud Run's filesystem is ephemeral — production images live in GCS
    and are served to the UI via short-lived signed URLs."""

    def save(self, doc_id: str, img: Image.Image) -> str:
        from google.cloud import storage  # lazy: not needed for local dev/tests

        bucket_name = get_settings().gcs_bucket_name
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(f"{doc_id}/watermarked.png")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        blob.upload_from_string(buf.getvalue(), content_type="image/png")
        return f"gs://{bucket_name}/{doc_id}/watermarked.png"

    def signed_url(self, gs_path: str, expiry_minutes: int = 15) -> str:
        from datetime import timedelta

        from google.cloud import storage

        bucket_name = get_settings().gcs_bucket_name
        blob_name = gs_path.removeprefix(f"gs://{bucket_name}/")
        client = storage.Client()
        blob = client.bucket(bucket_name).blob(blob_name)
        return blob.generate_signed_url(expiration=timedelta(minutes=expiry_minutes))


def get_file_store():
    return (
        GCSFileStore()
        if get_settings().storage_backend == "gcs"
        else LocalFileStore()
    )
