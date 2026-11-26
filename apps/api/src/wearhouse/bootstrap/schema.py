"""Schema contract the runtime expects. tests/test_migrations.py asserts SCHEMA_HEAD == alembic head."""
from __future__ import annotations

SCHEMA_HEAD = "0016_underwear_slot"

LEGACY_TABLES = frozenset({"garment", "interface_log", "garment_code", "activation_attempt", "wear_log"})
LEGACY_MARKER_TABLE = "dw_legacy_environment"

# Runtime least privilege: what the API role needs. Anything missing fails startup closed.
RUNTIME_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "wearhouse_environment": ("SELECT",),
    "alembic_version": ("SELECT",),
    "app_user": ("SELECT", "INSERT"),
    "user_subject": ("SELECT", "INSERT", "DELETE"),
    "role_grant": ("SELECT", "INSERT", "DELETE"),
    "catalogue_source": ("SELECT", "INSERT"),
    "source_snapshot": ("SELECT", "INSERT"),
    "product": ("SELECT", "INSERT", "UPDATE"),
    "product_revision": ("SELECT", "INSERT"),
    "product_variant": ("SELECT", "INSERT"),
    "media_reference": ("SELECT", "INSERT"),
    "garment_unit": ("SELECT", "INSERT", "UPDATE"),
    "activation_credential": ("SELECT", "INSERT", "UPDATE"),
    "issuance_delivery": ("SELECT", "INSERT", "UPDATE"),
    "owned_item": ("SELECT", "INSERT"),
    "ownership_event": ("SELECT", "INSERT"),
    "idempotency_record": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "attempt_bucket": ("SELECT", "INSERT", "UPDATE"),
    "attempt_event": ("SELECT", "INSERT", "DELETE"),
    "audit_event": ("SELECT", "INSERT"),
    "outbox_event": ("SELECT", "INSERT", "UPDATE"),
    "outbox_delivery": ("SELECT", "INSERT"),
    # add-wearhouse-accounts (0004)
    "account_profile": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "handle_hold": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "privacy_setting": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "friend_request": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "friendship": ("SELECT", "INSERT", "DELETE"),
    "user_block": ("SELECT", "INSERT", "DELETE"),
    # publish-wearhouse-catalogue (0005)
    "catalogue_import_job": ("SELECT", "INSERT", "UPDATE"),
    "catalogue_import_row": ("SELECT", "INSERT"),
    "catalogue_collection": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "catalogue_collection_item": ("SELECT", "INSERT", "DELETE"),
    # add-wearhouse-sandbox-commerce (0006)
    "sandbox_offer": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "wishlist_item": ("SELECT", "INSERT", "DELETE"),
    "cart_line": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "sandbox_order": ("SELECT", "INSERT", "UPDATE"),
    "sandbox_order_line": ("SELECT", "INSERT"),
    "sandbox_order_unit": ("SELECT", "INSERT", "UPDATE"),
    # build-wearhouse-wardrobe-planning-services (0007)
    "wardrobe_declared_item": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "wardrobe_item_state": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "wardrobe_shelf": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "wardrobe_shelf_item": ("SELECT", "INSERT", "DELETE"),
    "look": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "look_revision": ("SELECT", "INSERT", "DELETE"),
    "plan_entry": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "wear_entry": ("SELECT", "INSERT", "DELETE"),
    "wear_entry_item": ("SELECT", "INSERT", "DELETE"),
    "weather_cache": ("SELECT", "INSERT", "UPDATE"),
    "user_weather_location": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    # add-wearhouse-social-profile-services (0008)
    "look_share": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "plan_share_setting": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "notification_state": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "profile_showcase": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    # add-wearhouse-object-management (0009)
    "product_media": ("SELECT", "INSERT", "UPDATE"),
    # complete-wearhouse-research-intelligence (0010)
    "recommendation_artifact": ("SELECT", "INSERT", "UPDATE"),
    "item_neighbour": ("SELECT", "INSERT"),
    # add-wearhouse-sizes (0011): registry is staff-edited (never deleted); product/offer sizes are replaced
    "size_system": ("SELECT", "INSERT", "UPDATE"),
    "size_value": ("SELECT", "INSERT", "UPDATE"),
    "product_size": ("SELECT", "INSERT", "DELETE"),
    "user_size_preference": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "sandbox_offer_size": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    # add-wearhouse-settings-security (0013)
    "account_setting": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    # align-wearhouse-outfit-recommender (0014)
    "recommendation_run": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "recommendation_exposure": ("SELECT", "INSERT", "DELETE"),
    "recommendation_choice": ("SELECT", "INSERT", "DELETE"),
    # complete-wearhouse-tdd (0015)
    "share_report": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "inspiration": ("SELECT", "INSERT", "DELETE"),
}

# Column-level grants (least privilege): the runtime may only touch these app_user columns.
RUNTIME_COLUMN_PRIVILEGES: dict[str, dict[str, tuple[str, ...]]] = {
    "app_user": {"UPDATE": ("tokens_not_before", "deleted_at", "display_name")},
    # complete-wearhouse-tdd (0015): sandbox revocation flags only; ownership rows stay otherwise immutable
    "owned_item": {"UPDATE": ("revoked_at", "revoked_reason")},
}
