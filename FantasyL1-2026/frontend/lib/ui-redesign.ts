const ENABLED = process.env.NEXT_PUBLIC_UI_REDESIGN_V1 === "true";

const ROUTE_KEY_BY_PREFIX = [
  { prefix: "/landing", key: "landing" },
  { prefix: "/login", key: "login" },
  { prefix: "/ranking", key: "ranking" },
  { prefix: "/fixtures", key: "fixtures" },
  { prefix: "/team", key: "team" },
  { prefix: "/market", key: "market" },
  { prefix: "/stats", key: "stats" },
  { prefix: "/settings", key: "settings" }
] as const;

type RouteKeyTuple = (typeof ROUTE_KEY_BY_PREFIX)[number];
export type UiRedesignRouteKey = RouteKeyTuple["key"];

const VALID_ROUTE_KEYS = new Set<UiRedesignRouteKey>(ROUTE_KEY_BY_PREFIX.map((entry) => entry.key));

const parseRoutes = (): Set<UiRedesignRouteKey> => {
  const raw = process.env.NEXT_PUBLIC_UI_REDESIGN_V1_ROUTES || "";
  const mapped = raw
    .split(",")
    .map((chunk) => chunk.trim().toLowerCase())
    .filter(Boolean)
    .map((entry) => (entry === "home" || entry === "/" ? "landing" : entry))
    .filter((entry): entry is UiRedesignRouteKey => VALID_ROUTE_KEYS.has(entry as UiRedesignRouteKey));
  return new Set(mapped);
};

const ENABLED_ROUTES = parseRoutes();

const normalizePathname = (pathname: string) => {
  if (!pathname || pathname === "/") return "/";
  return pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
};

export function getUiRedesignRouteKey(pathname: string): UiRedesignRouteKey | null {
  const normalized = normalizePathname(pathname);
  if (normalized === "/") return "landing";
  const match = ROUTE_KEY_BY_PREFIX.find(
    (entry) => normalized === entry.prefix || normalized.startsWith(`${entry.prefix}/`)
  );
  return match?.key || null;
}

export function isUiRedesignEnabledForPath(pathname: string): boolean {
  if (!ENABLED) return false;
  const routeKey = getUiRedesignRouteKey(pathname);
  if (!routeKey) return false;
  if (ENABLED_ROUTES.size === 0) return true;
  return ENABLED_ROUTES.has(routeKey);
}

export function getUiRedesignRouteList(): UiRedesignRouteKey[] {
  return [...ENABLED_ROUTES];
}
