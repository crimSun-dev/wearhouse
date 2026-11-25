from __future__ import annotations

from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from ..identity.api import current_principal
from ..identity.domain import Principal
from ..ownership.api import ERRORS, ProductView, _respond
from ..platform.errors import ApiError
from ..platform.idempotency import require_key
from ..platform.ids import parse_uuid

Vis = Literal["public", "friends", "private"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Avatar(BaseModel):
    kind: Literal["preset", "provider"]
    preset: Optional[str] = None
    url: Optional[str] = None


class Card(BaseModel):
    handle: Optional[str]
    display_name: str
    avatar: Avatar


class MeResponse(BaseModel):
    user_id: str
    roles: list[str]
    capabilities: list[str]
    handle: Optional[str]
    needs_onboarding: bool


class Privacy(_Strict):
    profile: Vis
    wardrobe: Vis
    friends_list: Vis


class OwnProfile(Card):
    bio: str
    member_since: str
    needs_onboarding: bool
    privacy: Privacy


class AvatarIn(_Strict):
    kind: Literal["preset", "provider"]
    preset: Optional[StrictStr] = Field(default=None, max_length=32)


class ProfilePatch(_Strict):
    handle: Optional[StrictStr] = Field(default=None, max_length=64)
    display_name: Optional[StrictStr] = Field(default=None, max_length=200)
    bio: Optional[StrictStr] = Field(default=None, max_length=1000)
    avatar: Optional[AvatarIn] = None

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("send at least one field to change")
        return self


class Sections(BaseModel):
    wardrobe: Vis
    friends_list: Vis


class PublicProfile(Card):
    profile_visibility: Vis
    bio: Optional[str] = None
    member_since: Optional[str] = None
    sections: Optional[Sections] = None


class WardrobeItem(BaseModel):
    product: ProductView


class WardrobePage(BaseModel):
    items: list[WardrobeItem]
    next_cursor: Optional[str]


class FriendsPage(BaseModel):
    friends: list[Card]
    next_cursor: Optional[str]


class BlocksPage(BaseModel):
    blocks: list[Card]
    next_cursor: Optional[str]


class SearchResults(BaseModel):
    results: list[Card]


class FriendRequestIn(_Strict):
    handle: StrictStr = Field(min_length=1, max_length=64)


class FriendRequestOut(BaseModel):
    status: Literal["pending", "accepted"]
    request_id: Optional[str] = None
    account: Card


class PendingRequest(BaseModel):
    request_id: str
    account: Card
    created_at: str


class RequestsPage(BaseModel):
    requests: list[PendingRequest]
    next_cursor: Optional[str]


class TransitionOut(BaseModel):
    status: Literal["accepted", "declined", "cancelled"]


class DeleteIn(_Strict):
    confirm: StrictStr = Field(min_length=1, max_length=64, description="Your handle, or DELETE if you have none")


def optional_principal(request: Request) -> Principal | None:
    """Anonymous when no Authorization header; invalid tokens still get 401; suspended users browse as anonymous."""
    if not request.headers.get("authorization"):
        return None
    try:
        return request.app.state.services.identity.authenticate(request.headers.get("authorization"))
    except ApiError as exc:
        if exc.code == "ACCOUNT_SUSPENDED":
            return None
        raise


def _svc(request: Request):
    return request.app.state.services.accounts


account_router = APIRouter(tags=["account"])
social_router = APIRouter(tags=["social"])
profiles_router = APIRouter(tags=["profiles"])


# ------------------------------------------------------------------ account
@account_router.get("/me", response_model=MeResponse, responses=ERRORS,
                    summary="Verified account, server-granted capabilities and onboarding state")
def me(request: Request, principal: Principal = Depends(current_principal)) -> MeResponse:
    return MeResponse(**_svc(request).me(principal))


@account_router.get("/me/profile", response_model=OwnProfile, responses=ERRORS, summary="Your profile")
def get_profile(request: Request, principal: Principal = Depends(current_principal)) -> OwnProfile:
    return OwnProfile(**_svc(request).get_profile(principal))


@account_router.patch("/me/profile", response_model=OwnProfile, responses=ERRORS,
                      summary="Change handle, display name, bio or avatar")
def patch_profile(body: ProfilePatch, request: Request,
                  principal: Principal = Depends(current_principal)) -> OwnProfile:
    patch = body.model_dump(exclude_unset=True)
    return OwnProfile(**_svc(request).update_profile(principal, patch))


@account_router.get("/me/privacy", response_model=Privacy, responses=ERRORS, summary="Your visibility settings")
def get_privacy(request: Request, principal: Principal = Depends(current_principal)) -> Privacy:
    return Privacy(**_svc(request).get_privacy(principal))


@account_router.put("/me/privacy", response_model=Privacy, responses=ERRORS, summary="Set visibility settings")
def put_privacy(body: Privacy, request: Request, principal: Principal = Depends(current_principal)) -> Privacy:
    return Privacy(**_svc(request).set_privacy(principal, body.model_dump()))


class SettingSchemaOut(BaseModel):
    key: str
    section: str
    type: Literal["choice", "flag", "range"]
    default: Union[StrictBool, StrictInt, StrictStr]
    choices: list[str]
    min: Optional[int]
    max: Optional[int]


class SettingsOut(BaseModel):
    version: int
    updated_at: Optional[str]
    values: dict[str, Union[StrictBool, StrictInt, StrictStr]]
    sections: list[str]
    schema_: list[SettingSchemaOut] = Field(alias="schema", serialization_alias="schema")
    model_config = ConfigDict(populate_by_name=True)


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: StrictInt = Field(ge=0)
    values: dict[str, Union[StrictBool, StrictInt, StrictStr]] = Field(max_length=40)


class SecuritySessionOut(BaseModel):
    signed_in_at: Optional[str]
    age_seconds: Optional[int]
    recent_enough_for_sensitive_actions: bool


class SecurityEventOut(BaseModel):
    action: str
    at: str
    by_you: bool
    details: dict[str, Union[str, list[str], bool, None]]


class SecurityOut(BaseModel):
    account_created_at: Optional[str]
    sessions_revoked_at: Optional[str]
    current_session: SecuritySessionOut
    password_managed_by: str
    events: list[SecurityEventOut]


@account_router.get("/me/settings", response_model=SettingsOut, response_model_by_alias=True, responses=ERRORS,
                    summary="Your settings (every key, defaults filled in) with the schema and version")
def get_settings(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).get_settings(principal)


@account_router.patch("/me/settings", response_model=SettingsOut, response_model_by_alias=True, responses=ERRORS,
                      summary="Change settings; send the version you read (409 SETTINGS_CHANGED if another device saved)")
def patch_settings(body: SettingsPatch, request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).update_settings(principal, version=body.version, values=body.values)


@account_router.get("/me/security", response_model=SecurityOut, responses=ERRORS,
                    summary="Security overview: account dates, current session, your recent security events")
def security(request: Request, principal: Principal = Depends(current_principal)):
    return _svc(request).security(principal)


@account_router.post("/me/sessions/revoke-all", status_code=204, responses=ERRORS,
                     summary="Sign out everywhere: every token issued until now stops working")
def revoke_all(request: Request, principal: Principal = Depends(current_principal)) -> Response:
    _svc(request).revoke_all(principal)
    return Response(status_code=204)


@account_router.get("/me/export", responses=ERRORS, summary="Download everything Wearhouse holds about you (JSON)")
def export(request: Request, principal: Principal = Depends(current_principal)) -> JSONResponse:
    return JSONResponse(_svc(request).export(principal),
                        headers={"Content-Disposition": 'attachment; filename="wearhouse-export.json"'})


@account_router.delete("/me", status_code=204, responses={**ERRORS, 401: {"model": ERRORS[401]["model"]}},
                       summary="Delete your account (recent sign-in and typed confirmation required)")
def delete_me(body: DeleteIn, request: Request, principal: Principal = Depends(current_principal)) -> Response:
    _svc(request).delete_account(principal, confirm=body.confirm)
    return Response(status_code=204)


# ------------------------------------------------------------------ social
@social_router.get("/users/search", response_model=SearchResults, responses=ERRORS,
                   summary="Find accounts by handle (prefix of at least 3, or @exact)")
def search(request: Request, q: str = Query(..., max_length=21),
           principal: Principal = Depends(current_principal)) -> SearchResults:
    return SearchResults(**_svc(request).search(principal, q))


@social_router.post("/me/friend-requests", status_code=201, response_model=FriendRequestOut, responses=ERRORS,
                    summary="Send a friend request (Idempotency-Key required; 50 per 24 h)")
def send_request(body: FriendRequestIn, request: Request, principal: Principal = Depends(current_principal),
                 idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    out = _svc(request).send_request(principal, handle=body.handle, idem_key=require_key(idempotency_key))
    return _respond(out, FriendRequestOut)


@social_router.get("/me/friend-requests", response_model=RequestsPage, responses=ERRORS,
                   summary="Your pending incoming or outgoing requests")
def list_requests(request: Request, direction: Literal["incoming", "outgoing"] = Query("incoming"),
                  limit: Optional[int] = Query(None), cursor: Optional[str] = Query(None, max_length=512),
                  principal: Principal = Depends(current_principal)) -> RequestsPage:
    return RequestsPage(**_svc(request).list_requests(principal, direction=direction, limit=limit, cursor=cursor))


@social_router.post("/me/friend-requests/{request_id}/accept", response_model=TransitionOut, responses=ERRORS)
def accept(request_id: str, request: Request, principal: Principal = Depends(current_principal)) -> TransitionOut:
    return TransitionOut(**_svc(request).accept(principal, parse_uuid(request_id)))


@social_router.post("/me/friend-requests/{request_id}/decline", response_model=TransitionOut, responses=ERRORS)
def decline(request_id: str, request: Request, principal: Principal = Depends(current_principal)) -> TransitionOut:
    return TransitionOut(**_svc(request).decline(principal, parse_uuid(request_id)))


@social_router.delete("/me/friend-requests/{request_id}", response_model=TransitionOut, responses=ERRORS,
                      summary="Cancel a request you sent")
def cancel(request_id: str, request: Request, principal: Principal = Depends(current_principal)) -> TransitionOut:
    return TransitionOut(**_svc(request).cancel(principal, parse_uuid(request_id)))


@social_router.get("/me/friends", response_model=FriendsPage, responses=ERRORS, summary="Your friends")
def my_friends(request: Request, limit: Optional[int] = Query(None), cursor: Optional[str] = Query(None, max_length=512),
               principal: Principal = Depends(current_principal)) -> FriendsPage:
    return FriendsPage(**_svc(request).my_friends(principal, limit=limit, cursor=cursor))


@social_router.delete("/me/friends/{handle}", status_code=204, responses=ERRORS, summary="Remove a friend")
def remove_friend(handle: str, request: Request, principal: Principal = Depends(current_principal)) -> Response:
    _svc(request).remove_friend(principal, handle)
    return Response(status_code=204)


@social_router.get("/me/blocks", response_model=BlocksPage, responses=ERRORS, summary="Accounts you block")
def my_blocks(request: Request, limit: Optional[int] = Query(None), cursor: Optional[str] = Query(None, max_length=512),
              principal: Principal = Depends(current_principal)) -> BlocksPage:
    return BlocksPage(**_svc(request).my_blocks(principal, limit=limit, cursor=cursor))


@social_router.put("/me/blocks/{handle}", status_code=204, responses=ERRORS,
                   summary="Block an account (ends friendship and pending requests)")
def block(handle: str, request: Request, principal: Principal = Depends(current_principal)) -> Response:
    _svc(request).block(principal, handle)
    return Response(status_code=204)


@social_router.delete("/me/blocks/{handle}", status_code=204, responses=ERRORS, summary="Unblock an account")
def unblock(handle: str, request: Request, principal: Principal = Depends(current_principal)) -> Response:
    _svc(request).unblock(principal, handle)
    return Response(status_code=204)


# ------------------------------------------------------------------ public profiles
@profiles_router.get("/profiles/{handle}", response_model=PublicProfile, response_model_exclude_none=True,
                     responses={404: ERRORS[404]}, summary="A profile, filtered by its owner's privacy settings")
def public_profile(handle: str, request: Request, viewer: Principal | None = Depends(optional_principal)):
    return PublicProfile(**_svc(request).public_profile(viewer, handle))


@profiles_router.get("/profiles/{handle}/wardrobe", response_model=WardrobePage, responses={404: ERRORS[404]},
                     summary="A wardrobe as others see it (no serials, ids or exact times)")
def public_wardrobe(handle: str, request: Request, limit: Optional[int] = Query(None),
                    cursor: Optional[str] = Query(None, max_length=512),
                    viewer: Principal | None = Depends(optional_principal)) -> WardrobePage:
    return WardrobePage(**_svc(request).public_wardrobe(viewer, handle, limit=limit, cursor=cursor))


@profiles_router.get("/profiles/{handle}/friends", response_model=FriendsPage, responses={404: ERRORS[404]},
                     summary="A friends list as others see it")
def public_friends(handle: str, request: Request, limit: Optional[int] = Query(None),
                   cursor: Optional[str] = Query(None, max_length=512),
                   viewer: Principal | None = Depends(optional_principal)) -> FriendsPage:
    return FriendsPage(**_svc(request).public_friends(viewer, handle, limit=limit, cursor=cursor))


# =============================================================================== staff role administration
class StaffAccountOut(BaseModel):
    handle: Optional[str]
    display_name: Optional[str]
    roles: list[str]
    capabilities: list[str]


staff_router = APIRouter(tags=["admin: staff roles"])
StaffRole = Literal["catalogue_editor", "inventory_manager", "admin"]


def _roles(request: Request):
    return request.app.state.services.staff_roles


@staff_router.get("/admin/staff", response_model=list[StaffAccountOut], summary="Accounts holding staff roles (admin)")
def list_staff(request: Request, principal: Principal = Depends(current_principal)):
    return _roles(request).staff(principal)


@staff_router.get("/admin/staff/{handle}", response_model=StaffAccountOut, summary="One account's roles (admin)")
def staff_lookup(handle: str, request: Request, principal: Principal = Depends(current_principal)):
    return _roles(request).lookup(principal, handle)


@staff_router.put("/admin/staff/{handle}/roles/{role}", response_model=StaffAccountOut,
                  summary="Grant a staff role (admin; audited)")
def grant_role(handle: str, role: StaffRole, request: Request, principal: Principal = Depends(current_principal)):
    return _roles(request).grant(principal, handle, role)


@staff_router.delete("/admin/staff/{handle}/roles/{role}", response_model=StaffAccountOut,
                     summary="Revoke a staff role (admin; last admin / own admin role protected)")
def revoke_role(handle: str, role: StaffRole, request: Request, principal: Principal = Depends(current_principal)):
    return _roles(request).revoke(principal, handle, role)
