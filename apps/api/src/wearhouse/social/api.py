from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from ..accounts.api import optional_principal
from ..identity.api import current_principal
from ..identity.domain import Principal


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AvatarOut(BaseModel):
    kind: str
    preset: Optional[str] = None
    url: Optional[str] = None


class SocialCardOut(BaseModel):
    handle: Optional[str]
    display_name: str
    avatar: AvatarOut


class ProjectedItemOut(BaseModel):
    """Safe projection: no serial, key, wardrobe item id, photo, care, wear or location."""

    slot: str
    name: Optional[str]
    category: Optional[str]
    colour: Optional[str]
    verified: bool
    product_id: Optional[str]


class ProjectedLookOut(BaseModel):
    look_name: str
    revision_no: int
    items: list[ProjectedItemOut]


class ShareOut(BaseModel):
    id: str
    owner: Optional[SocialCardOut]
    caption: Optional[str]
    audience: Literal["friends", "public"]
    created_at: str
    look: Optional[ProjectedLookOut]
    look_id: Optional[str] = None
    revoked: Optional[bool] = None
    effective_audience: Optional[Literal["friends", "public", "private"]] = None  # owner only: after privacy ceiling
    moderation: Optional[Literal["visible", "hidden"]] = None  # owner only (complete-wearhouse-tdd)


class SharesOut(BaseModel):
    items: list[ShareOut]


class ShareIn(_Strict):
    look_id: uuid.UUID
    audience: Literal["friends", "public"]
    caption: Optional[StrictStr] = Field(default=None, max_length=140)


class SharePatch(_Strict):
    audience: Optional[Literal["friends", "public"]] = None
    caption: Optional[StrictStr] = Field(default=None, max_length=140)
    repin: Optional[StrictBool] = None


class FeedOut(BaseModel):
    items: list[ShareOut]
    next_cursor: Optional[str]


class PlanSharingIn(_Strict):
    audience: Literal["none", "friends"]


class PlanSharingOut(BaseModel):
    audience: Literal["none", "friends"]


class WeekDayOut(BaseModel):
    date: str
    occasion: Optional[str]
    look: Optional[ProjectedLookOut]


class WeekOut(BaseModel):
    owner: SocialCardOut
    days: list[WeekDayOut]


class NotificationOut(BaseModel):
    kind: Literal["friend_request", "request_accepted", "friend_shared_look"]
    at: str
    account: SocialCardOut
    ref: str
    unread: bool


class NotificationsOut(BaseModel):
    read_through: Optional[str]
    items: list[NotificationOut]


class UnreadOut(BaseModel):
    unread: int


class ShowcaseIn(_Strict):
    headline: Optional[StrictStr] = Field(default=None, max_length=80)
    accent: Literal["plum", "ivory", "blush", "noir", "sage", "sky"] = "plum"
    featured_share_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)


class MyShowcaseOut(BaseModel):
    headline: Optional[str]
    accent: str
    featured: list[str]


class ShowcaseOut(BaseModel):
    owner: SocialCardOut
    headline: Optional[str]
    accent: str
    featured: list[ShareOut]


def _svc(request: Request):
    return request.app.state.services.social


me_router = APIRouter(tags=["social: me"])
public_router = APIRouter(tags=["social"])


@me_router.get("/me/shares", response_model=list[ShareOut], summary="Your look shares (including revoked)")
def my_shares(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).my_shares(principal)


@me_router.post("/me/shares", status_code=201, response_model=ShareOut,
                summary="Share one of your looks (pinned to its current revision) with friends or public")
def share(body: ShareIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).share_look(principal, look_id=body.look_id, audience=body.audience, caption=body.caption)


@me_router.patch("/me/shares/{share_id}", response_model=ShareOut, summary="Change audience/caption or re-pin")
def update_share(share_id: uuid.UUID, body: SharePatch, request: Request,
                 principal: Principal = Depends(current_principal)):
    return _svc(request).update_share(principal, share_id, {k: getattr(body, k) for k in body.model_fields_set})


@me_router.delete("/me/shares/{share_id}", status_code=204, summary="Revoke a share")
def revoke_share(share_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).revoke_share(principal, share_id)
    return Response(status_code=204)


@me_router.get("/me/feed", response_model=FeedOut, summary="Friends timeline: shares you can see now, newest first")
def feed(request: Request, limit: Optional[int] = Query(None), cursor: Optional[str] = Query(None, max_length=512),
         principal: Principal = Depends(current_principal)):
    return _svc(request).feed(principal, limit=limit, cursor=cursor)


@me_router.get("/me/plan-sharing", response_model=PlanSharingOut, summary="Who may see your week plan")
def plan_sharing(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).plan_sharing(principal)


@me_router.put("/me/plan-sharing", response_model=PlanSharingOut, summary="Set week plan sharing (none/friends)")
def set_plan_sharing(body: PlanSharingIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).set_plan_sharing(principal, body.audience)


@me_router.get("/me/notifications", response_model=NotificationsOut,
               summary="Derived notifications: friend requests, accepted requests, friends' shares")
def notifications(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).notifications(principal)


@me_router.get("/me/notifications/unread-count", response_model=UnreadOut, summary="Unread notification count")
def unread(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).unread_count(principal)


@me_router.post("/me/notifications/read", response_model=UnreadOut, summary="Mark all notifications read")
def mark_read(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).mark_read(principal)


@me_router.get("/me/showcase", response_model=MyShowcaseOut, summary="Your profile showcase settings")
def my_showcase(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).my_showcase(principal)


@me_router.put("/me/showcase", response_model=MyShowcaseOut, summary="Headline, accent and up to 3 featured shares")
def put_showcase(body: ShowcaseIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).put_showcase(principal, headline=body.headline, accent=body.accent,
                                      featured=body.featured_share_ids)


@public_router.get("/shares/{share_id}", response_model=ShareOut,
                   summary="A shared look, if you may see it now (public or signed in)")
def read_share(share_id: uuid.UUID, request: Request, viewer: Optional[Principal] = Depends(optional_principal)):
    return _svc(request).read_share(viewer, share_id)


@public_router.get("/profiles/{handle}/shares", response_model=SharesOut, summary="Shares on a profile you may see")
def profile_shares(handle: str, request: Request, viewer: Optional[Principal] = Depends(optional_principal)):
    return _svc(request).profile_shares(viewer, handle)


@public_router.get("/profiles/{handle}/week", response_model=WeekOut, summary="A friend's week plan (if shared)")
def week(handle: str, request: Request, viewer: Optional[Principal] = Depends(optional_principal)):
    return _svc(request).week(viewer, handle)


@public_router.get("/profiles/{handle}/showcase", response_model=ShowcaseOut,
                   summary="Profile showcase under profile visibility")
def showcase(handle: str, request: Request, viewer: Optional[Principal] = Depends(optional_principal)):
    return _svc(request).showcase(viewer, handle)


# ================================================================ reports, moderation, inspiration (complete-wearhouse-tdd)
class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: StrictStr = Field(max_length=300)


class ReportOut(BaseModel):
    share_id: str
    reported: bool


class ModerationItemOut(ShareOut):
    reports: int
    reasons: list[str]
    first_reported_at: Optional[str]


class ModerationQueueOut(BaseModel):
    items: list[ModerationItemOut]


class ModerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["hide", "restore", "dismiss"]
    reason: StrictStr = Field(max_length=300)


class ModerateOut(BaseModel):
    share_id: str
    moderation: Literal["visible", "hidden"]


class InspirationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    share_id: uuid.UUID


class InspirationOut(BaseModel):
    id: str
    saved_at: str
    shared_at: Optional[str]
    caption: Optional[str]
    look: Optional[ProjectedLookOut]
    from_: Optional[SocialCardOut] = Field(default=None, alias="from", serialization_alias="from")
    model_config = ConfigDict(populate_by_name=True)


class InspirationsOut(BaseModel):
    items: list[InspirationOut]


admin_router = APIRouter(tags=["admin: moderation"])


@public_router.post("/shares/{share_id}/report", response_model=ReportOut,
                    summary="Report a share you can see (once per share)")
def report_share(share_id: uuid.UUID, body: ReportIn, request: Request,
                 principal: Principal = Depends(current_principal)):
    return _svc(request).report_share(principal, share_id, body.reason)


@admin_router.get("/admin/moderation/reports", response_model=ModerationQueueOut,
                  summary="Open reports grouped by share (social:moderate)")
def moderation_queue(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).moderation_queue(principal)


@admin_router.post("/admin/moderation/shares/{share_id}", response_model=ModerateOut,
                   summary="Hide, restore or dismiss reports for a share (social:moderate; audited)")
def moderate(share_id: uuid.UUID, body: ModerateIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).moderate(principal, share_id, action=body.action, reason=body.reason)


@me_router.get("/me/inspirations", response_model=InspirationsOut, response_model_by_alias=True,
               summary="Looks you saved as inspiration (snapshots; they never grant items)")
def inspirations(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).inspirations(principal)


@me_router.post("/me/inspirations", status_code=201, response_model=InspirationOut, response_model_by_alias=True,
                summary="Save a share you can see as a private inspiration snapshot")
def save_inspiration(body: InspirationIn, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).save_inspiration(principal, body.share_id)


@me_router.delete("/me/inspirations/{inspiration_id}", status_code=204, summary="Delete a saved inspiration")
def delete_inspiration(inspiration_id: uuid.UUID, request: Request, principal: Principal = Depends(current_principal)):
    _svc(request).delete_inspiration(principal, inspiration_id)
    return Response(status_code=204)
