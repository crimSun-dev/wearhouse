"""Accounts domain: handles, profile fields, visibility policy and social limits (pure; no I/O)."""
from __future__ import annotations

import re
import unicodedata
from datetime import timedelta
from enum import Enum

from ..platform.errors import ApiError, FieldError, conflict, validation_failed

HANDLE_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")
RESERVED_HANDLES = frozenset({
    "admin", "administrator", "wearhouse", "support", "help", "me", "api", "root", "system", "staff", "moderator",
    "mod", "official", "security", "settings", "account", "accounts", "profile", "profiles", "login", "logout",
    "signin", "signup", "register", "null", "undefined", "anonymous", "everyone", "friends", "privacy",
})
AVATAR_PRESETS = ("plum", "ivory", "blush", "noir", "sage", "sky")
DISPLAY_NAME_MAX = 32
BIO_MAX = 160
DEFAULT_DISPLAY_NAME = "Wearhouse user"

HANDLE_CHANGE_INTERVAL = timedelta(days=7)
HANDLE_HOLD = timedelta(days=30)
FRIEND_REQUESTS_PER_DAY = 50
FRIEND_REQUEST_WINDOW = timedelta(hours=24)
MAX_PENDING_OUTGOING = 200
MAX_FRIENDS = 1000
MAX_BLOCKS = 1000
EXPORTS_PER_HOUR = 5
EXPORT_WINDOW = timedelta(hours=1)
RECENT_AUTH = timedelta(seconds=300)
SEARCH_LIMIT = 20
SEARCH_MIN_PREFIX = 3


class Visibility(str, Enum):
    PUBLIC = "public"
    FRIENDS = "friends"
    PRIVATE = "private"


class Section(str, Enum):
    PROFILE = "profile"
    WARDROBE = "wardrobe"
    FRIENDS_LIST = "friends_list"


class Relation(str, Enum):
    SELF = "self"
    FRIEND = "friend"
    STRANGER = "stranger"  # signed in, not a friend
    ANONYMOUS = "anonymous"
    BLOCKED = "blocked"  # either direction


def can_view(section: Section, setting: Visibility, relation: Relation) -> bool:
    """Single visibility decision used for every non-owner read. Blocks override everything."""
    if relation is Relation.BLOCKED:
        return False
    if relation is Relation.SELF:
        return True
    if setting is Visibility.PUBLIC:
        return True
    if setting is Visibility.FRIENDS:
        return relation is Relation.FRIEND
    return False


def relation_of(*, is_self: bool, viewer_known: bool, blocked: bool, friends: bool) -> Relation:
    if is_self:
        return Relation.SELF
    if blocked:
        return Relation.BLOCKED
    if not viewer_known:
        return Relation.ANONYMOUS
    return Relation.FRIEND if friends else Relation.STRANGER


# ------------------------------------------------------------------ validators
def normalize_handle(raw: str) -> str:
    """Lowercase canonical handle or 422. Reserved/taken checks happen in the application layer."""
    if not isinstance(raw, str) or not raw.isascii():
        raise validation_failed([FieldError("body.handle", "invalid_handle", _HANDLE_RULES)])
    h = raw.strip().lower()
    if not HANDLE_RE.fullmatch(h):
        raise validation_failed([FieldError("body.handle", "invalid_handle", _HANDLE_RULES)])
    return h


_HANDLE_RULES = "Handles are 3-20 characters: a-z, 0-9 and _, starting with a letter."


def is_reserved(handle: str) -> bool:
    return handle in RESERVED_HANDLES or handle.startswith("wearhouse")


def _has_control(text: str, allow_newline: bool) -> bool:
    for ch in text:
        if allow_newline and ch == "\n":
            continue
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Co", "Cn"):
            return True
    return False


def clean_display_name(raw: str) -> str:
    name = raw.strip() if isinstance(raw, str) else ""
    if not 1 <= len(name) <= DISPLAY_NAME_MAX or _has_control(name, allow_newline=False):
        raise validation_failed([FieldError("body.display_name", "invalid_display_name",
                                            f"Display names are 1-{DISPLAY_NAME_MAX} characters without "
                                            "control characters.")])
    return name


def default_display_name(hint: str | None) -> str:
    """Seed from the broker name hint when it is usable; never fail account creation over it."""
    if hint:
        name = "".join(ch for ch in hint.strip() if unicodedata.category(ch)[0] != "C")[:DISPLAY_NAME_MAX].strip()
        if name:
            return name
    return DEFAULT_DISPLAY_NAME


def clean_bio(raw: str) -> str:
    bio = raw.strip() if isinstance(raw, str) else ""
    if len(bio) > BIO_MAX or _has_control(bio, allow_newline=True):
        raise validation_failed([FieldError("body.bio", "invalid_bio",
                                            f"Bios are at most {BIO_MAX} characters without control characters.")])
    return bio


# ------------------------------------------------------------------ errors
def handle_unavailable() -> ApiError:
    return conflict("HANDLE_UNAVAILABLE", "That handle is not available.")


def handle_change_too_soon(retry_after_s: int) -> ApiError:
    return ApiError(409, "HANDLE_CHANGE_TOO_SOON", "Handles can be changed once every 7 days.",
                    headers={"Retry-After": str(max(1, int(retry_after_s)))})


def handle_required() -> ApiError:
    return conflict("HANDLE_REQUIRED", "Choose a handle before using social features.")


def friend_limit() -> ApiError:
    return conflict("FRIEND_LIMIT_REACHED", f"Accounts can have at most {MAX_FRIENDS} friends.")


def reauthentication_required() -> ApiError:
    return ApiError(401, "REAUTHENTICATION_REQUIRED", "Sign in again to confirm this action.",
                    headers={"WWW-Authenticate": 'Bearer realm="wearhouse", error="insufficient_user_authentication"'})


# ================================================================ account settings (add-wearhouse-settings-security)
# The registry is code (allowed values are product decisions); values are stored per user (design D1).
# Sections mirror the owner's settings mock: general, wardrobe, style, display, audio, notifications, community, beta.
SETTINGS: dict[str, dict] = {
    "language": {"section": "general", "type": "choice", "choices": ("en", "id"), "default": "en"},
    "wardrobe_view": {"section": "wardrobe", "type": "choice", "choices": ("grid", "list", "outfit"), "default": "grid"},
    "wardrobe_group_by_slot": {"section": "wardrobe", "type": "flag", "default": True},
    "style_suggestions": {"section": "style", "type": "flag", "default": True},
    "weather_in_suggestions": {"section": "style", "type": "flag", "default": True},
    "recommendation_style": {"section": "style", "type": "choice", "choices": ("balanced", "classic", "adventurous"),
                             "default": "balanced"},
    "theme": {"section": "display", "type": "choice", "choices": ("dark", "light", "system"), "default": "system"},
    "reduce_motion": {"section": "display", "type": "flag", "default": False},
    "sound_effects": {"section": "audio", "type": "flag", "default": False},
    "sound_volume": {"section": "audio", "type": "range", "min": 0, "max": 100, "default": 60},
    "notify_friend_requests": {"section": "notifications", "type": "flag", "default": True},
    "notify_request_accepted": {"section": "notifications", "type": "flag", "default": True},
    "notify_friend_shares": {"section": "notifications", "type": "flag", "default": True},
    "friend_requests_from": {"section": "community", "type": "choice", "choices": ("everyone", "nobody"),
                             "default": "everyone"},
    "discoverable": {"section": "community", "type": "flag", "default": True},
    "beta_features": {"section": "beta", "type": "flag", "default": False},
    # Which body model the fitting-room avatar uses (owner request 2026-11-26). Only the avatar reads it.
    "avatar_gender": {"section": "avatar", "type": "choice", "choices": ("unspecified", "female", "male"),
                      "default": "unspecified"},
}
SETTING_SECTIONS = ("general", "wardrobe", "style", "avatar", "display", "audio", "notifications", "community", "beta")
# outfit-suggestion Eq. 7 weight profiles (compatibility / preference / recency): balanced = the demo baseline
# (align-wearhouse-outfit-recommender). Weather is a hard rule, not a weight.
RECOMMENDATION_WEIGHTS = {
    "balanced": {"compatibility": 0.5, "preference": 0.3, "recency": 0.2},
    "classic": {"compatibility": 0.4, "preference": 0.5, "recency": 0.1},
    "adventurous": {"compatibility": 0.4, "preference": 0.2, "recency": 0.4},
}
NOTIFICATION_SETTING = {"friend_request": "notify_friend_requests", "request_accepted": "notify_request_accepted",
                        "friend_shared_look": "notify_friend_shares"}


def effective_settings(stored: dict | None) -> dict:
    """Every registered key: the stored value when valid, else the default (unknown stored keys are ignored)."""
    stored = stored or {}
    return {k: (stored[k] if k in stored and setting_errors({k: stored[k]}) == [] else spec["default"])
            for k, spec in SETTINGS.items()}


def setting_errors(values: dict) -> list[FieldError]:
    errors = []
    for k, v in values.items():
        spec = SETTINGS.get(k)
        field = f"body.values.{k}"
        if spec is None:
            errors.append(FieldError(field, "unknown_setting", "Unknown setting."))
        elif spec["type"] == "flag" and not isinstance(v, bool):
            errors.append(FieldError(field, "invalid", "Use true or false."))
        elif spec["type"] == "choice" and v not in spec["choices"]:
            errors.append(FieldError(field, "invalid", "Choose one of: " + ", ".join(spec["choices"]) + "."))
        elif spec["type"] == "range" and (isinstance(v, bool) or not isinstance(v, int)
                                          or not spec["min"] <= v <= spec["max"]):
            errors.append(FieldError(field, "out_of_range", f"Use a whole number {spec['min']}-{spec['max']}."))
    return errors


def settings_schema() -> list[dict]:
    return [{"key": k, "section": s["section"], "type": s["type"], "default": s["default"],
             "choices": list(s.get("choices", ())), "min": s.get("min"), "max": s.get("max")}
            for k, s in SETTINGS.items()]


# security events a person can see about their own account (design D3)
SECURITY_ACTIONS = ("account.sessions_revoked", "account.handle_changed", "account.privacy_changed",
                    "account.settings_changed", "account.exported", "identity.role_granted", "identity.role_revoked")
