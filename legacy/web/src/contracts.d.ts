export type Slot = 'top' | 'bottom' | 'dress' | 'outer' | 'footwear' | 'accessory';
export type Occasion = 'campus' | 'casual' | 'worship' | 'formal' | 'wedding';
export type Style = 'casual' | 'smart' | 'formal' | 'modest' | 'sporty' | 'street';
export type WeatherSource = 'LIVE' | 'CACHED' | 'MANUAL' | 'MANUAL_REQUIRED';
export interface Attributes { color_hex: string; style: Style; rain_suitable: boolean; heavy: boolean; long_sleeve: boolean; long_bottom: boolean; formality: number }
export interface Garment { id: string; name: string; slot: Slot; attrs: Attributes; gtin: string | null; serial: string | null; origin: 'manual' | 'registered'; times_recommended: number; times_chosen: number; last_worn_at: string | null }
export interface Outfit { id: string; label: string | null; planned_for: string | null; occasion: Occasion | null; items: Garment[] }
export interface WeatherSlot { at: string; local_time: string; t: number | null; humidity: number | null; description: string; rain: boolean; hot: boolean }
export interface Forecast { adm4: string; source: WeatherSource; fetched_at: string | null; note: string; timezone: string; credit: string | null; slots: WeatherSlot[] }
export interface Weather extends Partial<WeatherSlot> { source: WeatherSource; fetched_at?: string | null; note: string; credit: string | null; ask?: ('rain' | 'hot')[] }
export interface Recommendation { weather: Weather; context?: {rain: boolean; hot: boolean; occasion: Occasion}; outfits: {rank: number; score: number; compat: number; pref: number; recency: number; items: Garment[]}[]; message: string | null }
export interface Health { status: string; db: 'neon' | 'postgresql' | 'sqlite'; weather_mode: 'mock' | 'live'; fault: string; weather_cache: unknown }
export interface Avatar { outfit_id: string; body: {model: string; gender: string}; slots: Partial<Record<Slot, {garment_id: string; name: string; template: string | null; texture: string | null; tint: string}>>; covers: Partial<Record<Slot, Slot[]>> }
export interface Scan { gtin: string; serial: string; name: string; category: string; slot: Slot; color_hex: string; style: Style; image_url: string | null; digital_link: string; wishlist_only: false; ownership: unknown }
export interface InterfaceRow { id: number; at: string; interface: string; route: string; status: number | string; latency_ms: number; weather_source: WeatherSource | null; note: string | null }
