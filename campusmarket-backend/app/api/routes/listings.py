import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.listing import Listing
from app.models.user import User
from app.schemas.listing import (
    ListingCreate,
    ListingListOut,
    ListingOut,
    ListingUpdate,
    StatusUpdate,
)

router = APIRouter(prefix="/api/listings", tags=["listings"])

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _get_owned_listing(listing_id: int, db: Session, user: User) -> Listing:
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You don't own this listing")
    return listing


@router.get("", response_model=ListingListOut)
def list_listings(
    q: Optional[str] = None,
    category: Optional[str] = None,
    condition: Optional[str] = None,
    listing_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    status: Optional[str] = None,
    seller_id: Optional[str] = None,
    campus_id: Optional[int] = None,
    include_sold: bool = False,
    sort: str = "newest",
    db: Session = Depends(get_db),
):
    query = db.query(Listing)

    if q:
        query = query.filter(Listing.title.ilike(f"%{q}%"))
    if category and category not in ("All", "any"):
        query = query.filter(Listing.category == category)
    if condition and condition not in ("All", "any"):
        query = query.filter(Listing.condition == condition)
    if listing_type and listing_type not in ("All", "any"):
        query = query.filter(Listing.listing_type == listing_type)
    if min_price is not None:
        query = query.filter(Listing.price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.price <= max_price)
    if campus_id:
        query = query.filter(Listing.campus_id == campus_id)
    if seller_id:
        query = query.filter(Listing.owner_id == seller_id)
    if status:
        query = query.filter(Listing.status == status)
    elif not include_sold and not seller_id:
        query = query.filter(Listing.status != "sold")

    if sort == "price_low":
        query = query.order_by(Listing.price.asc())
    elif sort == "price_high":
        query = query.order_by(Listing.price.desc())
    else:
        query = query.order_by(Listing.created_at.desc())

    items = query.all()
    return ListingListOut(
        items=[ListingOut.from_orm_with_art(i) for i in items],
        total=len(items),
    )


@router.get("/recommended", response_model=list[ListingOut])
def recommended_listings(
    exclude_id: Optional[int] = None,
    campus_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Listing).filter(Listing.status == "available")
    if exclude_id:
        query = query.filter(Listing.id != exclude_id)
    if campus_id:
        query = query.filter(Listing.campus_id == campus_id)
    items = query.order_by(Listing.created_at.desc()).limit(6).all()
    return [ListingOut.from_orm_with_art(i) for i in items]


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return ListingOut.from_orm_with_art(listing)


@router.post("", response_model=ListingOut)
def create_listing(
    payload: ListingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = Listing(**payload.model_dump(), owner_id=user.id)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return ListingOut.from_orm_with_art(listing)


@router.put("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = _get_owned_listing(listing_id, db, user)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, key, value)
    db.commit()
    db.refresh(listing)
    return ListingOut.from_orm_with_art(listing)


@router.patch("/{listing_id}/status", response_model=ListingOut)
def set_listing_status(
    listing_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = _get_owned_listing(listing_id, db, user)
    listing.status = payload.status
    db.commit()
    db.refresh(listing)
    return ListingOut.from_orm_with_art(listing)


@router.delete("/{listing_id}", status_code=204)
def delete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = _get_owned_listing(listing_id, db, user)
    db.delete(listing)
    db.commit()


@router.post("/{listing_id}/images", response_model=ListingOut)
def upload_images(
    listing_id: int,
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    listing = _get_owned_listing(listing_id, db, user)

    urls = []
    for f in files[:3]:
        ext = Path(f.filename or "").suffix or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = UPLOAD_DIR / filename
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        urls.append(str(request.base_url) + f"uploads/{filename}")

    listing.images = [*(listing.images or []), *urls]
    db.commit()
    db.refresh(listing)
    return ListingOut.from_orm_with_art(listing)
