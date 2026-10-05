"""File storage for uploads: listing photos, avatars, resource previews and resource PDFs.

Two backends behind one interface:

* SupabaseStorage: files live in Supabase Storage, so every machine running the
  backend sees the same files. Public files (photos, avatars, previews) go to a public
  bucket and are served straight from Supabase's CDN. Resource PDFs go to a PRIVATE bucket
  and are only ever read by this backend, which streams them after an access check.
* LocalStorage: files live on this machine's disk under uploads/ (public, served at
  /uploads) and private/ (never served). Used when Supabase isn't configured, and in tests.

Keys are paths like "listings/<uuid>.jpg" or "resources/<uuid>.pdf".
"""

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class StorageError(RuntimeError):
    pass


class LocalStorage:
    name = "local"

    def __init__(self, public_dir: Path, private_dir: Path):
        self.public_dir = public_dir
        self.private_dir = private_dir

    def _path(self, root: Path, key: str) -> Path:
        path = (root / key).resolve()
        if not path.is_relative_to(root.resolve()):
            raise StorageError(f"Invalid storage key: {key}")
        return path

    def _write(self, root: Path, key: str, data: bytes) -> None:
        path = self._path(root, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def put_public(self, key: str, data: bytes, content_type: str) -> None:
        self._write(self.public_dir, key, data)

    def public_url(self, key: str, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/uploads/{key}"

    def put_private(self, key: str, data: bytes, content_type: str) -> None:
        self._write(self.private_dir, key, data)

    def get_private(self, key: str) -> bytes | None:
        path = self._path(self.private_dir, key)
        return path.read_bytes() if path.is_file() else None

    def delete_public(self, keys: list[str]) -> None:
        self._delete(self.public_dir, keys)

    def delete_private(self, keys: list[str]) -> None:
        self._delete(self.private_dir, keys)

    def _delete(self, root: Path, keys: list[str]) -> None:
        for key in keys:
            try:
                path = self._path(root, key)
                if path.is_file():
                    path.unlink()
            except (OSError, StorageError):
                pass

    def key_from_url(self, url: str) -> str | None:
        path = urlparse(url).path
        marker = "/uploads/"
        return path.split(marker, 1)[1] if marker in path else None


class SupabaseStorage:
    name = "supabase"

    def __init__(self, url: str, service_key: str, public_bucket: str, private_bucket: str, client: httpx.Client | None = None):
        self.base = url.rstrip("/") + "/storage/v1"
        self.public_bucket = public_bucket
        self.private_bucket = private_bucket
        # The service role key never leaves the backend; the frontend only ever sees public URLs.
        self.client = client or httpx.Client(
            timeout=60,
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
        )
        self._buckets_ready = False

    def ensure_buckets(self) -> None:
        if self._buckets_ready:
            return
        for bucket, public in ((self.public_bucket, True), (self.private_bucket, False)):
            res = self.client.post(f"{self.base}/bucket", json={"id": bucket, "name": bucket, "public": public})
            # 409 / "already exists" is fine; anything else (bad key, wrong URL) should be loud.
            if res.status_code >= 400 and "already exists" not in res.text.lower() and res.status_code != 409:
                raise StorageError(f"Couldn't create Supabase bucket {bucket!r}: {res.status_code} {res.text}")
        self._buckets_ready = True

    def _put(self, bucket: str, key: str, data: bytes, content_type: str) -> None:
        self.ensure_buckets()
        res = self.client.post(
            f"{self.base}/object/{bucket}/{key}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true", "Cache-Control": "max-age=31536000"},
        )
        if res.status_code >= 400:
            raise StorageError(f"Upload to Supabase failed: {res.status_code} {res.text}")

    def _delete(self, bucket: str, keys: list[str]) -> None:
        if not keys:
            return
        try:
            self.client.request("DELETE", f"{self.base}/object/{bucket}", json={"prefixes": keys})
        except httpx.HTTPError:
            pass  # best effort, same as local deletes

    def put_public(self, key: str, data: bytes, content_type: str) -> None:
        self._put(self.public_bucket, key, data, content_type)

    def public_url(self, key: str, base_url: str = "") -> str:
        return f"{self.base}/object/public/{self.public_bucket}/{key}"

    def put_private(self, key: str, data: bytes, content_type: str) -> None:
        self._put(self.private_bucket, key, data, content_type)

    def get_private(self, key: str) -> bytes | None:
        res = self.client.get(f"{self.base}/object/{self.private_bucket}/{key}")
        if res.status_code in (400, 404):
            return None
        if res.status_code >= 400:
            raise StorageError(f"Download from Supabase failed: {res.status_code} {res.text}")
        return res.content

    def delete_public(self, keys: list[str]) -> None:
        self._delete(self.public_bucket, keys)

    def delete_private(self, keys: list[str]) -> None:
        self._delete(self.private_bucket, keys)

    def key_from_url(self, url: str) -> str | None:
        prefix = f"{self.base}/object/public/{self.public_bucket}/"
        return url[len(prefix):] if url.startswith(prefix) else None


def supabase_url() -> str | None:
    if settings.SUPABASE_URL:
        return settings.SUPABASE_URL
    # Derive https://<ref>.supabase.co from the database URL, so only the key needs adding.
    m = re.search(r"postgres\.([a-z0-9]+)[:@]", settings.DATABASE_URL) or re.search(
        r"db\.([a-z0-9]+)\.supabase\.co", settings.DATABASE_URL
    )
    return f"https://{m.group(1)}.supabase.co" if m else None


def _build():
    mode = settings.STORAGE_BACKEND.lower()
    url = supabase_url()
    if mode == "supabase" or (mode == "auto" and settings.SUPABASE_SERVICE_ROLE_KEY and url):
        if not (url and settings.SUPABASE_SERVICE_ROLE_KEY):
            raise RuntimeError("STORAGE_BACKEND=supabase needs SUPABASE_SERVICE_ROLE_KEY (and SUPABASE_URL if it can't be derived)")
        return SupabaseStorage(url, settings.SUPABASE_SERVICE_ROLE_KEY, settings.SUPABASE_PUBLIC_BUCKET, settings.SUPABASE_PRIVATE_BUCKET)
    return LocalStorage(BACKEND_ROOT / "uploads", BACKEND_ROOT / "private")


storage = _build()


def delete_public_urls(urls: list[str]) -> None:
    """Remove public files by their stored URL. Handles both Supabase URLs and older /uploads/ URLs."""
    local = LocalStorage(BACKEND_ROOT / "uploads", BACKEND_ROOT / "private") if storage.name != "local" else storage
    keys, local_keys = [], []
    for url in urls:
        if not url:
            continue
        if (key := storage.key_from_url(url)) is not None:
            keys.append(key)
        elif (key := local.key_from_url(url)) is not None:
            local_keys.append(key)
    storage.delete_public(keys)
    if local is not storage:
        local.delete_public(local_keys)
