const OFFLINE_CACHE_PREFIX = "fantasy_offline_cache::";
const OFFLINE_CACHE_MAX_AGE_MS = 15 * 60 * 1000;

type CachedPayload = {
  savedAt: number;
  data: unknown;
};

const CACHEABLE_GET_PATTERNS = [
  /^\/catalog\/rounds(?:\?|$)/,
  /^\/catalog\/fixtures(?:\?|$)/,
  /^\/catalog\/teams(?:\?|$)/,
  /^\/catalog\/players(?:\?|$)/,
  /^\/catalog\/player-stats(?:\?|$)/,
  /^\/public\/leaderboard(?:\?|$)/,
  /^\/public\/premium\/config(?:\?|$)/,
  /^\/public\/app-config(?:\?|$)/,
  /^\/fantasy\/team(?:\?|$)/,
  /^\/fantasy\/lineup(?:\?|$)/,
  /^\/ranking\/.+/
];

export function isCacheableGetPath(path: string): boolean {
  return CACHEABLE_GET_PATTERNS.some((pattern) => pattern.test(path));
}

export function getOfflineCacheKey(fullUrl: string, identity = "anon"): string {
  return `${OFFLINE_CACHE_PREFIX}${identity}::${fullUrl}`;
}

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

export function setOfflineSnapshot(
  fullUrl: string,
  data: unknown,
  identity?: string
): void {
  if (!hasStorage()) return;
  const key = getOfflineCacheKey(fullUrl, identity);
  const payload: CachedPayload = {
    savedAt: Date.now(),
    data
  };
  try {
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // ignore storage quota errors
  }
}

export function getOfflineSnapshot(
  fullUrl: string,
  options?: { allowStale?: boolean; maxAgeMs?: number; identity?: string }
): unknown | null {
  if (!hasStorage()) return null;
  const key = getOfflineCacheKey(fullUrl, options?.identity);
  const maxAgeMs = options?.maxAgeMs ?? OFFLINE_CACHE_MAX_AGE_MS;
  const allowStale = Boolean(options?.allowStale);
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const payload = JSON.parse(raw) as CachedPayload;
    if (!payload || typeof payload.savedAt !== "number") return null;
    const age = Date.now() - payload.savedAt;
    if (age <= maxAgeMs || allowStale) {
      return payload.data;
    }
    return null;
  } catch {
    return null;
  }
}

export function isOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine;
}
