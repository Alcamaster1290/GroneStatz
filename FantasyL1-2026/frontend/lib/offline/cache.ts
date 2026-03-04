const OFFLINE_CACHE_PREFIX = "fantasy_offline_cache::";
const OFFLINE_CACHE_MAX_AGE_MS = 15 * 60 * 1000;
const OFFLINE_CACHE_MAX_ENTRIES = 80;
const OFFLINE_CACHE_MAX_ITEM_BYTES = 180_000;
const OFFLINE_CACHE_SOFT_MAX_BYTES = 3_500_000;

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

const estimateBytes = (value: string): number => value.length * 2;

type CacheMeta = {
  key: string;
  savedAt: number;
  bytes: number;
};

function listOfflineCacheKeys(): string[] {
  if (!hasStorage()) return [];
  const keys: string[] = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index);
    if (!key) continue;
    if (key.startsWith(OFFLINE_CACHE_PREFIX)) {
      keys.push(key);
    }
  }
  return keys;
}

export function clearOfflineCache(): void {
  if (!hasStorage()) return;
  const keys = listOfflineCacheKeys();
  for (const key of keys) {
    try {
      localStorage.removeItem(key);
    } catch {
      // ignore storage errors
    }
  }
}

function removeOfflineKey(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    // ignore storage errors
  }
}

function collectOfflineCacheMeta(now = Date.now()): CacheMeta[] {
  const entries: CacheMeta[] = [];
  const keys = listOfflineCacheKeys();
  for (const key of keys) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const parsed = JSON.parse(raw) as CachedPayload;
      const savedAt = typeof parsed?.savedAt === "number" ? parsed.savedAt : 0;
      if (!savedAt || now - savedAt > OFFLINE_CACHE_MAX_AGE_MS) {
        removeOfflineKey(key);
        continue;
      }
      entries.push({
        key,
        savedAt,
        bytes: estimateBytes(raw)
      });
    } catch {
      removeOfflineKey(key);
    }
  }
  return entries;
}

function pruneOfflineCache(aggressive = false): void {
  if (!hasStorage()) return;
  const entries = collectOfflineCacheMeta();
  if (!entries.length) return;

  entries.sort((left, right) => right.savedAt - left.savedAt);
  const maxEntries = aggressive ? Math.max(30, Math.floor(OFFLINE_CACHE_MAX_ENTRIES * 0.6)) : OFFLINE_CACHE_MAX_ENTRIES;
  const maxBytes = aggressive ? Math.floor(OFFLINE_CACHE_SOFT_MAX_BYTES * 0.75) : OFFLINE_CACHE_SOFT_MAX_BYTES;

  let totalBytes = entries.reduce((sum, entry) => sum + entry.bytes, 0);

  for (let index = maxEntries; index < entries.length; index += 1) {
    removeOfflineKey(entries[index].key);
    totalBytes -= entries[index].bytes;
  }

  const lastRetainedIndex = Math.min(maxEntries, entries.length) - 1;
  for (let index = lastRetainedIndex; index >= 0 && totalBytes > maxBytes; index -= 1) {
    removeOfflineKey(entries[index].key);
    totalBytes -= entries[index].bytes;
  }
}

export function setOfflineSnapshot(
  fullUrl: string,
  data: unknown,
  identity?: string
): void {
  if (!hasStorage()) return;
  pruneOfflineCache();
  const key = getOfflineCacheKey(fullUrl, identity);
  const payload: CachedPayload = {
    savedAt: Date.now(),
    data
  };
  const serialized = JSON.stringify(payload);
  if (estimateBytes(serialized) > OFFLINE_CACHE_MAX_ITEM_BYTES) {
    return;
  }
  try {
    localStorage.setItem(key, serialized);
  } catch {
    pruneOfflineCache(true);
    try {
      localStorage.setItem(key, serialized);
    } catch {
      // ignore storage quota errors
    }
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
    removeOfflineKey(key);
    return null;
  } catch {
    return null;
  }
}

export function isOnline(): boolean {
  if (typeof navigator === "undefined") return true;
  return navigator.onLine;
}
