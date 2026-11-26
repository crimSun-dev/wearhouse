"""Composition root: the only place that wires adapters to ports."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.engine import Engine

from ..accounts.adapters.sql import SqlAccountsRepository
from ..accounts.application import AccountsService, StaffRolesService
from ..catalogue.adapters.sql import SqlCataloguePublishing, SqlCatalogueRepository, SqlRevisionReader
from ..catalogue.application import CatalogueService
from ..catalogue.adapters.sizes import SqlSizeRepository
from ..catalogue.publication import CataloguePublicationService, ProductMediaService
from ..catalogue.sizing import SizingService
from ..commerce.adapters.sql import SqlCommerceRepository
from ..commerce.application import CommerceService, CommerceStaffService
from ..recommendations.adapters.events import SqlRecommendationEvents
from ..recommendations.adapters.sql import SqlArtifactRepository
from ..recommendations.serving import RecommendationService
from ..social.adapters.sql import SqlSocialRepository
from ..social.application import SocialService
from ..wardrobe.adapters.sql import SqlWardrobeRepository
from ..wardrobe.application import WardrobeService
from ..weather.adapters.bmkg import BmkgFetcher
from ..weather.adapters.sql import SqlWeatherRepository
from ..weather.application import WeatherService
from ..identity.adapters.oidc import DiscoveryJwks, JwksUrlSource, OidcTokenVerifier, StaticJwks
from ..identity.adapters.sql import SqlAccountDirectory, SqlIdentityRepository, SqlUserDirectory
from ..identity.application import IdentityService
from ..identity.ports import TokenVerifier
from ..ownership.adapters.sql import SqlOwnedItemReader, SqlOwnershipRepository
from ..ownership.application import (AdmissionPolicy, DiscoveryService, IssuanceService, OwnedItemsService,
                                     RedemptionService, StarterKit, UnitFulfilment)
from ..platform.adapters.sql import SqlUnitOfWorkFactory
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.ports import FaultHook, no_faults
from .config import ConfigError, Settings

REPOSITORIES = {
    "identity": SqlIdentityRepository,
    "users": SqlUserDirectory,
    "catalogue": SqlCatalogueRepository,
    "revisions": SqlRevisionReader,
    "publishing": SqlCataloguePublishing,
    "ownership": SqlOwnershipRepository,
    "accounts": SqlAccountsRepository,
    "owned": SqlOwnedItemReader,
    "directory": SqlAccountDirectory,
    "commerce": SqlCommerceRepository,
    "wardrobe": SqlWardrobeRepository,
    "weather": SqlWeatherRepository,
    "social": SqlSocialRepository,
    "artifacts": SqlArtifactRepository,
    "sizes": SqlSizeRepository,
    "reco_events": SqlRecommendationEvents,
}


@dataclass
class Services:
    identity: IdentityService
    catalogue: CatalogueService
    publication: CataloguePublicationService
    media: ProductMediaService
    issuance: IssuanceService
    discovery: DiscoveryService
    redemption: RedemptionService
    owned_items: OwnedItemsService
    accounts: AccountsService
    staff_roles: StaffRolesService
    commerce: CommerceService
    commerce_staff: CommerceStaffService
    weather: WeatherService
    wardrobe: WardrobeService
    social: SocialService
    recommendations: RecommendationService
    sizing: SizingService
    uow_factory: SqlUnitOfWorkFactory
    ring: KeyRing
    trusted_proxies: frozenset[str] = field(default_factory=frozenset)


def build_verifier(settings: Settings) -> TokenVerifier:
    if settings.auth_adapter != "oidc":
        raise ConfigError("The test identity adapter must be injected through wearhouse.testing.create_test_app.")
    if settings.oidc_jwks_file:
        keys = StaticJwks.from_file(settings.oidc_jwks_file)  # local development issuer (never deployment)
    elif settings.oidc_jwks_url:
        keys = JwksUrlSource(settings.oidc_jwks_url, cache_ttl_s=settings.jwks_cache_ttl_s,
                             min_refresh_interval_s=settings.jwks_min_refresh_s)
    else:
        keys = DiscoveryJwks(settings.oidc_issuer, cache_ttl_s=settings.jwks_cache_ttl_s,
                             min_refresh_interval_s=settings.jwks_min_refresh_s)
    return OidcTokenVerifier(issuer=settings.oidc_issuer, audience=settings.oidc_audience, keys=keys,
                             leeway_s=settings.token_leeway_s, algorithms=tuple(settings.oidc_algorithms))


def build_services(settings: Settings, engine: Engine, verifier: TokenVerifier, *, clock: Clock = utcnow,
                   faults: FaultHook = no_faults) -> Services:
    ring = settings.key_ring()
    uow = SqlUnitOfWorkFactory(engine, REPOSITORIES)
    policy = AdmissionPolicy(actor_limit=settings.redemption_actor_limit, ip_limit=settings.redemption_ip_limit,
                             global_limit=settings.redemption_global_limit)
    publication = CataloguePublicationService(uow, ring, clock)
    commerce = CommerceService(uow, ring, UnitFulfilment(ring, clock, settings.delivery_ttl_s), clock=clock,
                               lease_s=settings.idempotency_lease_s)
    weather = WeatherService(uow, BmkgFetcher(), clock=clock)
    wardrobe = WardrobeService(uow, ring, weather, clock=clock, lease_s=settings.idempotency_lease_s)
    social = SocialService(uow, ring, wardrobe, clock=clock)
    sizing = SizingService(uow, clock=clock)
    return Services(
        identity=IdentityService(uow, verifier, clock),
        catalogue=CatalogueService(uow, clock),
        publication=publication,
        media=ProductMediaService(uow, clock),
        issuance=IssuanceService(uow, ring, clock=clock, delivery_ttl_s=settings.delivery_ttl_s,
                                 lease_s=settings.idempotency_lease_s, faults=faults),
        discovery=DiscoveryService(uow),
        redemption=RedemptionService(uow, ring, clock=clock, policy=policy, lease_s=settings.idempotency_lease_s,
                                     faults=faults),
        owned_items=OwnedItemsService(uow, ring),
        accounts=AccountsService(uow, ring, clock=clock, lease_s=settings.idempotency_lease_s, faults=faults,
                                 on_onboarded=StarterKit(settings.starter_kit).grant if settings.starter_kit else None,
                                 export_sections={"commerce": commerce.export_data, "wardrobe": wardrobe.export_data,
                                                  "social": social.export_data, "sizes": sizing.export_data},
                                 erasers=(lambda u, user_id: u.commerce.erase_lists(user_id),
                                          sizing.erase,
                                          lambda u, user_id: u.reco_events.erase(user_id),
                                          lambda u, user_id: u.social.erase_all(user_id),  # before wardrobe (FKs)
                                          lambda u, user_id: u.wardrobe.erase_all(user_id),
                                          lambda u, user_id: u.weather.clear_location(user_id))),
        commerce=commerce,
        commerce_staff=CommerceStaffService(uow, ring, clock=clock),
        staff_roles=StaffRolesService(uow, clock=clock),
        weather=weather,
        wardrobe=wardrobe,
        social=social,
        recommendations=RecommendationService(uow, clock=clock),
        sizing=sizing,
        uow_factory=uow,
        ring=ring,
        trusted_proxies=frozenset(settings.trusted_proxies),
    )
