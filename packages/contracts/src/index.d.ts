// Public entry for clients. Generated operation types live in ./schema (do not edit that file).
import type {components, operations, paths} from './schema';

export type {components, operations, paths};
export type {ErrorCode} from './error-codes';
export type Schemas = components['schemas'];
export type OwnedItem = Schemas['OwnedItem'];
export type OwnedItemPage = Schemas['OwnedItemPage'];
export type PublicItem = Schemas['PublicItem'];
export type IssuedUnit = Schemas['IssuedUnit'];
export type MeResponse = Schemas['MeResponse'];
export type ApiError = Schemas['ErrorOut'];
// add-wearhouse-accounts
export type Card = Schemas['Card'];
export type Avatar = Schemas['Avatar'];
export type OwnProfile = Schemas['OwnProfile'];
export type ProfilePatch = Schemas['ProfilePatch'];
export type Privacy = Schemas['Privacy'];
export type PublicProfile = Schemas['PublicProfile'];
export type WardrobePage = Schemas['WardrobePage'];
export type FriendsPage = Schemas['FriendsPage'];
export type BlocksPage = Schemas['BlocksPage'];
export type SearchResults = Schemas['SearchResults'];
export type FriendRequestOut = Schemas['FriendRequestOut'];
export type RequestsPage = Schemas['RequestsPage'];
export type TransitionOut = Schemas['TransitionOut'];
export type Visibility = Privacy['profile'];
// publish-wearhouse-catalogue
export type BrowsePage = Schemas['BrowsePageOut'];
export type BrowseItem = Schemas['BrowseItemOut'];
export type ProductCard = Schemas['CardOut'];
export type Facets = Schemas['FacetsOut'];
export type ProductDetail = Schemas['ProductDetailOut'];
export type Collection = Schemas['CollectionOut'];
export type StaffCollection = Schemas['StaffCollectionOut'];
export type StaffProduct = Schemas['StaffProductOut'];
export type ReviewItem = Schemas['ReviewItemOut'];
export type ImportJob = Schemas['ImportJobOut'];
// add-wearhouse-sandbox-commerce
export type PublicOffer = Schemas['PublicOfferOut'];
export type StaffOffer = Schemas['StaffOfferOut'];
export type Wishlist = Schemas['WishlistOut'];
export type Cart = Schemas['CartOut'];
export type Receipt = Schemas['ReceiptOut'];
export type OrdersPage = Schemas['OrdersPageOut'];
export type UnitKey = Schemas['KeyOut'];
// build-wearhouse-wardrobe-planning-services
export type WardrobeItem = Schemas['WardrobeItemOut'];
export type WardrobeItems = Schemas['ItemsOut'];
export type Shelf = Schemas['ShelfOut'];
export type Look = Schemas['LookOut'];
export type LookRevision = Schemas['LookRevisionOut'];
export type Planner = Schemas['PlannerOut'];
export type PlannerDay = Schemas['DayOut'];
export type WearEntry = Schemas['WearOut'];
export type Suggestions = Schemas['SuggestionsOut'];
export type Forecast = Schemas['ForecastOut'];
export type SlotRegistry = Schemas['RegistryOut'];
// add-wearhouse-social-profile-services
export type Share = Schemas['ShareOut'];
export type SharesPage = Schemas['SharesOut'];
export type Feed = Schemas['FeedOut'];
export type Week = Schemas['WeekOut'];
export type Notifications = Schemas['NotificationsOut'];
export type Unread = Schemas['UnreadOut'];
export type MyShowcase = Schemas['MyShowcaseOut'];
export type Showcase = Schemas['ShowcaseOut'];
// add-wearhouse-object-management
export type MediaObject = Schemas['MediaObjectOut'];
export type StaffAccount = Schemas['StaffAccountOut'];
export type StaffUnitsPage = Schemas['StaffUnitsPage'];
export type StaffOrdersPage = Schemas['StaffOrdersPage'];
export type BulkOffers = Schemas['BulkOffersOut'];
export type GenerateMissing = Schemas['GenerateMissingOut'];
// complete-wearhouse-research-intelligence
export type SimilarProducts = Schemas['SimilarOut'];
export type ProductsForMe = Schemas['ForMeOut'];
export type RecModel = Schemas['RecModelOut'];
// add-wearhouse-sizes
export type SizeRegistry = Schemas['SizeRegistryOut'];
export type SizeSystem = Schemas['SizeRegistrySystemOut'];
export type UsualSizes = Schemas['UsualSizesOut'];
export type ProductSizes = Schemas['ProductSizesOut'];
export type SizeRef = Schemas['SizeOut'];
// add-wearhouse-settings-security
export type Settings = Schemas['SettingsOut'];
export type SettingSchema = Schemas['SettingSchemaOut'];
export type Security = Schemas['SecurityOut'];
export type About = Schemas['AboutOut'];
