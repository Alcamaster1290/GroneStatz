"use client";

import { useFantasyStore } from "@/lib/store";

const TOKEN_KEY = "fantasy_token";
const EMAIL_KEY = "fantasy_email";
export const SESSION_COOKIE_KEY = "fantasy_session";

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30;

const isBrowser = () => typeof window !== "undefined" && typeof document !== "undefined";

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
  localStorage.setItem(TOKEN_KEY, token);
  if (email && email.trim()) {
    localStorage.setItem(EMAIL_KEY, email.trim());
  } else if (email !== undefined) {
    localStorage.removeItem(EMAIL_KEY);
  }
  setSessionCookie();
};

export const clearSession = () => {
  if (!isBrowser()) return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
  useFantasyStore.getState().setToken(null);
  useFantasyStore.getState().setUserEmail(null);
  clearSessionCookie();
};

export const hydrateSessionFromStorage = () => {
  if (!isBrowser()) {
    return { token: null as string | null, email: null as string | null };
  }
  const token = localStorage.getItem(TOKEN_KEY);
  const email = localStorage.getItem(EMAIL_KEY);

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
