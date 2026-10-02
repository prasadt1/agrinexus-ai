"""Profile location_coords holds [lat, lon] values that DynamoDB accepts."""
from decimal import Decimal

import pytest
from boto3.dynamodb.types import TypeSerializer

from tests.test_rag_refusal_detection import processor_handler as h


class _Table:
    def __init__(self):
        self.puts, self.updates = [], []

    def put_item(self, Item, **_k):
        TypeSerializer().serialize(Item)
        self.puts.append(Item)

    def update_item(self, **kw):
        TypeSerializer().serialize(kw["ExpressionAttributeValues"])
        self.updates.append(kw)

    def get_item(self, **_k):
        return {"Item": {"onboarding_state": "location", "dialect": "en"}}


LATUR = [Decimal("18.4088"), Decimal("76.5604")]


def test_create_user_profile_stores_lat_lon(monkeypatch):
    t = _Table()
    monkeypatch.setattr(h, "table", t)
    h.create_user_profile("15550001111", "mr", "Latur", "Cotton", True)
    assert t.puts[0]["location_coords"] == LATUR


def test_unknown_district_stores_none(monkeypatch):
    t = _Table()
    monkeypatch.setattr(h, "table", t)
    h.create_user_profile("15550001111", "mr", "Pune", "Cotton", True)
    assert t.puts[0]["location_coords"] is None


@pytest.mark.parametrize("district,expected", [("Latur", LATUR), ("Jalna", [Decimal("19.8347"), Decimal("75.8816")])])
def test_location_coords_helper(district, expected):
    assert h._location_coords(district) == expected
