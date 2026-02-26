"use client";

import { useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import AuthPanel from "@/components/AuthPanel";
import PublicPageNav from "@/components/PublicPageNav";
import { useFantasyStore } from "@/lib/store";

const normalizeRedirect = (value: string | null) => {
  if (!value) return "/app";
  if (!value.startsWith("/") || value.startsWith("//")) return "/app";
  return value;
};

export default function LoginClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = useFantasyStore((state) => state.token);
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);

  const redirectTo = useMemo(
    () => normalizeRedirect(searchParams.get("redirect")),
    [searchParams]
  );

  useEffect(() => {
    if (token) {
      router.replace(redirectTo);
      return;
    }
    const storedToken = localStorage.getItem("fantasy_token");
    const storedEmail = localStorage.getItem("fantasy_email");
    if (storedToken) {
      setToken(storedToken);
      if (storedEmail) {
        setUserEmail(storedEmail);
      }
      router.replace(redirectTo);
    }
  }, [token, redirectTo, router, setToken, setUserEmail]);

  return (
    <div className="space-y-4">
      <PublicPageNav />
      <div>
        <h1 className="text-xl font-semibold text-ink">Login</h1>
        <p className="text-sm text-muted">
          Accede para continuar al juego. También puedes navegar en Ranking y Rondas sin iniciar sesión.
        </p>
      </div>
      <AuthPanel onAuthenticated={() => router.replace(redirectTo)} />
    </div>
  );
}
