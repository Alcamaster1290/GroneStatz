"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import AuthPanel from "@/components/AuthPanel";
import PublicPageNav from "@/components/PublicPageNav";
import { hydrateSessionFromStorage } from "@/lib/session";
import { useFantasyStore } from "@/lib/store";

export default function LoginClient() {
  const router = useRouter();
  const token = useFantasyStore((state) => state.token);
  const postLoginTarget = "/app";

  useEffect(() => {
    if (token) {
      router.replace(postLoginTarget);
      return;
    }
    const hydrated = hydrateSessionFromStorage();
    if (hydrated.token) {
      router.replace(postLoginTarget);
    }
  }, [token, postLoginTarget, router]);

  return (
    <div className="space-y-4">
      <PublicPageNav />
      <div>
        <h1 className="text-xl font-semibold text-ink">Login</h1>
      </div>
      <AuthPanel onAuthenticated={() => router.replace(postLoginTarget)} />
    </div>
  );
}
