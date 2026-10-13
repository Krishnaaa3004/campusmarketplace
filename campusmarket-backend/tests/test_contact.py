"""Phone numbers and emails: never in lists or pages, revealed one person at a time,
logged and rate-limited so nobody can scrape the whole campus."""

import pytest

from app.core.config import settings
from app.models.listing import Listing
from app.models.product_request import ProductRequest
from conftest import _user


@pytest.fixture
def listing_ids(db_session, users):
    db, _ = db_session
    ids = []
    for i in range(3):
        listing = Listing(owner_id=users["owner"].id, title=f"Item {i}", category="Sports", listing_type="sale",
                          price=100, condition="Good", pickup_spot="Gate", images=[])
        db.add(listing)
        db.commit()
        ids.append(listing.id)
    return ids


def contact(client, headers, target_id, channel="whatsapp", target_type="listing"):
    return client.post("/api/contact", json={"target_type": target_type, "target_id": target_id, "channel": channel},
                       headers=headers)


def test_lists_and_pages_carry_no_contact_details(client, auth, listing_ids, create):
    for item in client.get("/api/listings", headers=auth("buyer")).json()["items"]:
        assert item["seller"]["phone"] is None and item["seller"]["email"] is None
        assert item["seller"]["has_phone"] is True
    page = client.get(f"/api/listings/{listing_ids[0]}", headers=auth("buyer")).json()
    assert page["seller"]["phone"] is None and page["seller"]["email"] is None
    rec = client.get("/api/listings/recommended", headers=auth("buyer")).json()["items"]
    assert all(i["seller"]["phone"] is None for i in rec)
    rid = create().json()["id"]
    res = client.get(f"/api/resources/{rid}", headers=auth("buyer")).json()
    assert res["owner"]["phone"] is None and res["owner"]["email"] is None


def test_reveal_gives_only_the_requested_channel(client, auth, listing_ids):
    wa = contact(client, auth("buyer"), listing_ids[0], "whatsapp").json()
    assert wa["phone"] == "919876543210" and wa["email"] is None
    em = contact(client, auth("buyer"), listing_ids[0], "email").json()
    assert em["email"] == "owner@campus.edu" and em["phone"] is None


def test_reveal_rules(client, auth, listing_ids, db_session, users):
    assert contact(client, {}, listing_ids[0]).status_code in (401, 403)
    assert contact(client, auth("unverified"), listing_ids[0]).status_code == 403
    assert contact(client, auth("buyer"), 9999).status_code == 404
    assert contact(client, auth("buyer"), listing_ids[0], channel="sms").status_code == 422
    db, _ = db_session
    users["owner"].phone = None
    db.commit()
    no_phone = contact(client, auth("buyer"), listing_ids[0], "whatsapp")
    assert no_phone.status_code == 404 and "email" in no_phone.json()["detail"]


def test_reveals_are_rate_limited(client, auth, db_session, users, monkeypatch):
    monkeypatch.setattr(settings, "CONTACT_REVEALS_PER_HOUR", 2)
    db, _ = db_session
    ids = []
    for i in range(3):  # three different sellers' listings
        seller = _user(db, f"seller{i}@campus.edu", account_type="seller")
        listing = Listing(owner_id=seller.id, title=f"Thing {i}", category="Sports", listing_type="sale",
                          price=10, condition="Good", pickup_spot="Gate", images=[])
        db.add(listing)
        db.commit()
        ids.append(listing.id)

    assert contact(client, auth("buyer"), ids[0]).status_code == 200
    assert contact(client, auth("buyer"), ids[1]).status_code == 200
    # Re-opening a seller you already contacted doesn't count...
    assert contact(client, auth("buyer"), ids[0], "email").status_code == 200
    # ...but a third new person this hour is refused.
    blocked = contact(client, auth("buyer"), ids[2])
    assert blocked.status_code == 429 and "hour" in blocked.json()["detail"]
    # Other students aren't affected.
    assert contact(client, auth("other"), ids[2]).status_code == 200


def test_daily_limit(client, auth, listing_ids, monkeypatch):
    monkeypatch.setattr(settings, "CONTACT_REVEALS_PER_DAY", 1)
    assert contact(client, auth("buyer"), listing_ids[0]).status_code == 200
    res = contact(client, auth("buyer"), listing_ids[1])
    assert res.status_code == 429 and "today" in res.json()["detail"]


def test_looking_for_feed_hides_contact_and_reply_is_for_sellers(client, auth, db_session, users):
    db, _ = db_session
    req = ProductRequest(user_id=users["buyer"].id, product="Casio calculator", description=None)
    db.add(req)
    db.commit()

    feed = client.get("/api/requests", headers=auth("owner")).json()
    assert feed[0]["requester"]["email"] is None and feed[0]["requester"]["phone"] is None
    mine = client.get("/api/requests/mine", headers=auth("buyer")).json()
    assert mine[0]["requester"]["email"] == "buyer@campus.edu"  # your own request shows your details

    reply = contact(client, auth("owner"), req.id, "whatsapp", target_type="request")
    assert reply.status_code == 200 and reply.json()["phone"] == "919876543210"
    assert contact(client, auth("other"), req.id, "email", target_type="request").status_code == 403  # buyers can't
