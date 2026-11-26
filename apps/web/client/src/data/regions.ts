// Indonesian administrative regions for the BMKG location picker (public/regions, built by scripts/make-regions.mjs
// from the Kemendagri 2025 code list). BMKG forecasts are keyed by the village (adm4) code: PP.CC.DD.VVVV.
import {useQuery} from '@tanstack/react-query';

type Pair = [code: string, name: string];
export type RegionIndex = {source: string; provinces: Pair[]; cities: Pair[]};
/** A city's districts: [district code suffix, name, villages as [village code suffix, name]]. */
export type CityRegions = Array<[string, string, Pair[]]>;
export type Place = {adm4: string; village: string; district: string; city: string; province: string};

const url = (file: string) => `${import.meta.env.BASE_URL}regions/${file}`;
const getJson = async <T,>(file: string): Promise<T> => {
  const r = await fetch(url(file));
  if (!r.ok) throw new Error(`regions ${file} ${r.status}`);
  return r.json() as Promise<T>;
};

/** Places most people pick, shown as one-tap choices (Kemayoran is the legacy app's default). */
export const QUICK_PLACES: Pair[] = [['31.71.03.1001', 'Kemayoran, Jakarta Pusat'], ['31.74.08.1001', 'Pancoran, Jakarta Selatan'],
  ['32.73.19.1001', 'Braga, Bandung'], ['35.78.07.1002', 'Genteng, Surabaya'], ['34.71.10.1001', 'Ngupasan, Yogyakarta'],
  ['51.71.03.1005', 'Dauh Puri, Denpasar'], ['12.71.19.1001', 'Petisah Tengah, Medan']];
export const DEFAULT_PLACE = '31.71.03.1001';

export function useRegionIndex() {
  return useQuery({queryKey: ['regions', 'index'], queryFn: () => getJson<RegionIndex>('index.json'), staleTime: Infinity, gcTime: Infinity});
}
export function useCityRegions(city: string | null) {
  return useQuery({queryKey: ['regions', city], enabled: !!city, queryFn: () => getJson<CityRegions>(`${city}.json`), staleTime: Infinity, gcTime: Infinity});
}

/** "Kota Administrasi Jakarta Pusat" → "Jakarta Pusat"; "Kabupaten Bogor" → "Bogor (Kab.)". */
export function shortCity(name: string) {
  if (name.startsWith('Kota Administrasi ')) return name.slice(18);
  if (name.startsWith('Kabupaten Administrasi ')) return `${name.slice(23)} (Kab.)`;
  if (name.startsWith('Kota ')) return name.slice(5);
  if (name.startsWith('Kabupaten ')) return `${name.slice(10)} (Kab.)`;
  return name;
}

export function placeIn(index: RegionIndex, city: CityRegions, adm4: string): Place | null {
  const [p, c, d, v] = adm4.split('.');
  const district = city.find(x => x[0] === d);
  const village = district?.[2].find(x => x[0] === v);
  if (!district || !village) return null;
  return {adm4, village: village[1], district: district[1], city: index.cities.find(x => x[0] === `${p}.${c}`)?.[1] ?? '',
    province: index.provinces.find(x => x[0] === p)?.[1] ?? ''};
}

/** The named place for a BMKG code (null while loading or when the code is unknown). */
export function usePlace(adm4: string | null | undefined) {
  const index = useRegionIndex();
  const cityCode = adm4 && /^\d{2}\.\d{2}\.\d{2}\.\d{4}$/.test(adm4) ? adm4.slice(0, 5) : null;
  const city = useCityRegions(cityCode);
  return index.data && city.data && adm4 ? placeIn(index.data, city.data, adm4) : null;
}
export const placeLabel = (p: Place) => `${p.village}, ${p.district}, ${shortCity(p.city)}`;
