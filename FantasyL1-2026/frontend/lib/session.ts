"use client";

import { clearOfflineCache } from "@/lib/offline/cache";
import { useFantasyStore } from "@/lib/store";

const TOKEN_KEY = "fantasy_token";
const EMAIL_KEY = "fantasy_email";
export const SESSION_COOKIE_KEY = "fantasy_session";

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

const isBrowser = () => typeof window !== "undefined" && typeof document !== "undefined";

const isQuotaExceeded = (error: unknown) => {
  if (typeof DOMException !== "undefined" && error instanceof DOMException) {
    return error.name === "QuotaExceededError" || error.code === 22 || error.code === 1014;
  }
  return false;
};

const getCookieSecurityFlags = () => {
  if (!isBrowser()) return "Path=/; SameSite=Lax";
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  return `Path=/; SameSite=Lax${secure}`;
};

export const setSessionCookie = () => {
  if (!isBrowser()) return;
  document.cookie = `${SESSION_COOKIE_KEY}=1; Max-Age=${COOKIE_MAX_AGE_SECONDS}; ${getCookieSecurityFlags()}`;
};

export const clearSessionCookie = () => {
  if (!isBrowser()) return;
  document.cookie = `${SESSION_COOKIE_KEY}=; Max-Age=0; ${getCookieSecurityFlags()}`;
};

export const setSessionToken = (token: string, email?: string | null) => {
  if (!isBrowser()) return;
  useFantasyStore.getState().setToken(token);
  if (email !== undefined) {
    useFantasyStore.getState().setUserEmail(email);
  }
  const persist = () => {
    localStorage.setItem(TOKEN_KEY, token);
    if (email && email.trim()) {
      localStorage.setItem(EMAIL_KEY, email.trim());
    } else if (email !== undefined) {
      localStorage.removeItem(EMAIL_KEY);
    }
  };
  try {
    persist();
  } catch (error) {
    if (isQuotaExceeded(error)) {
      clearOfflineCache();
      try {
        persist();
      } catch {
        // keep in-memory session to avoid blocking login
      }
    } else {
      // keep in-memory session to avoid blocking login
    }
  }
  setSessionCookie();
};

export const clearSession = () => {
  if (!isBrowser()) return;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
  } catch {
    // ignore storage errors
  }
  useFantasyStore.getState().setToken(null);
  useFantasyStore.getState().setUserEmail(null);
  clearSessionCookie();
};

export const hydrateSessionFromStorage = () => {
  if (!isBrowser()) {
    return { token: null as string | null, email: null as string | null };
  }
  let token: string | null = null;
  let email: string | null = null;
  try {
    token = localStorage.getItem(TOKEN_KEY);
    email = localStorage.getItem(EMAIL_KEY);
  } catch {
    token = null;
    email = null;
  }

  const { setToken, setUserEmail } = useFantasyStore.getState();
  setToken(token || null);
  setUserEmail(email || null);

  if (token) {
    setSessionCookie();
  } else {
    clearSessionCookie();
  }

  return { token, email };
};
