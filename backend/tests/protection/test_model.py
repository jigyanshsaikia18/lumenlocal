"""ProfileChangeEvent model wiring (P4A-2 / schema §7)."""
import app.models  # noqa: F401 — registers every table on Base.metadata
from app.db.base import Base
from app.models import ProfileChangeEvent


def test_table_registered_on_metadata():
    assert "profile_change_events" in Base.metadata.tables


def test_location_fk_present():
    col = ProfileChangeEvent.__table__.c["location_id"]
    assert "locations.id" in {fk.target_fullname for fk in col.foreign_keys}


def test_has_action_taken_and_severity_columns():
    cols = set(ProfileChangeEvent.__table__.c.keys())
    # action_taken is what P4A-2 fills (alerted/reverted/ignored); severity drives the policy.
    assert {"field", "old_value", "new_value", "severity", "action_taken"} <= cols
