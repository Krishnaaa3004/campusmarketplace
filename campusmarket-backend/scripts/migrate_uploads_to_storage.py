"""One-time move of files saved on this machine's disk into Supabase Storage.

Uploads the local listing photos, avatars, resource previews and resource PDFs that the
database still points at, then rewrites those database rows to the new storage keys/URLs.
Safe to re-run: anything already in Supabase is skipped.

    uv run python scripts/migrate_uploads_to_storage.py           # dry run, changes nothing
    uv run python scripts/migrate_uploads_to_storage.py --apply   # upload + update the DB
"""

import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main  # noqa: F401,E402  (registers every model)
from app.core.storage import BACKEND_ROOT, LocalStorage, storage  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.listing import Listing  # noqa: E402
from app.models.resource import Resource  # noqa: E402
from app.models.user import User  # noqa: E402

local = LocalStorage(BACKEND_ROOT / "uploads", BACKEND_ROOT / "private")


def content_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"


class Migrator:
    def __init__(self, apply: bool):
        self.apply = apply
        self.moved = 0
        self.missing: list[str] = []

    def public_url(self, url: str | None, prefix: str) -> str | None:
        """Old /uploads/<name> URL -> Supabase public URL (uploading the file)."""
        if not url or storage.key_from_url(url) is not None:
            return url  # empty, or already in Supabase
        old_key = local.key_from_url(url)
        if old_key is None:
            return url  # some other URL; leave it alone
        path = local.public_dir / old_key
        if not path.is_file():
            self.missing.append(str(path))
            return url
        key = prefix + Path(old_key).name
        print(f"  public  {path.name} -> {key}")
        if self.apply:
            storage.put_public(key, path.read_bytes(), content_type(key))
        self.moved += 1
        return storage.public_url(key)

    def preview(self, page: dict) -> dict:
        if "key" in page and not (local.public_dir / page["key"]).is_file():
            return page  # already migrated (or created with cloud storage on)
        key = page.get("key") or f"resource-previews/{page['name']}"
        path = local.public_dir / key
        if not path.is_file():
            self.missing.append(str(path))
            return page
        print(f"  public  {path.name} -> {key}")
        if self.apply:
            storage.put_public(key, path.read_bytes(), "image/jpeg")
        self.moved += 1
        return {"key": key, "kind": page["kind"]}

    def pdf(self, file_name: str | None) -> str | None:
        if not file_name:
            return file_name
        key = file_name if "/" in file_name else f"resources/{file_name}"
        path = local.private_dir / key
        if not path.is_file():
            if "/" not in file_name:
                self.missing.append(str(path))
            return file_name  # already migrated, or lost
        print(f"  private {path.name} -> {key}")
        if self.apply:
            storage.put_private(key, path.read_bytes(), "application/pdf")
        self.moved += 1
        return key


def main() -> None:
    apply = "--apply" in sys.argv
    if storage.name != "supabase":
        sys.exit("Supabase Storage isn't configured. Set SUPABASE_SERVICE_ROLE_KEY in .env first.")

    m = Migrator(apply)
    db = SessionLocal()
    try:
        for listing in db.query(Listing).all():
            new = [m.public_url(u, "listings/") for u in (listing.images or [])]
            if new != (listing.images or []):
                print(f"listing {listing.id}: {listing.title}")
                listing.images = new
        for user in db.query(User).filter(User.avatar_url.isnot(None)).all():
            new = m.public_url(user.avatar_url, "avatars/")
            if new != user.avatar_url:
                print(f"avatar: {user.email}")
                user.avatar_url = new
        for r in db.query(Resource).all():
            pages = [m.preview(p) for p in (r.preview_pages or [])]
            file_name = m.pdf(r.file_name)
            if pages != (r.preview_pages or []) or file_name != r.file_name:
                print(f"resource {r.id}: {r.title}")
                r.preview_pages = pages
                r.file_name = file_name
        if apply:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()

    verb = "Moved" if apply else "Would move"
    print(f"\n{verb} {m.moved} file(s).")
    if m.missing:
        print(f"{len(m.missing)} file(s) referenced in the DB weren't found on this machine:")
        for p in m.missing:
            print("  ", p)
    if not apply and m.moved:
        print("Dry run only. Re-run with --apply to upload and update the database.")
    if apply and m.moved:
        print("Local copies were left in place; delete uploads/ and private/ once everything looks right.")


if __name__ == "__main__":
    main()
