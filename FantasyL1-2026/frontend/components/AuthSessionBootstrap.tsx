"use client";

import { useEffect } from "react";

import { hydrateSessionFromStorage } from "@/lib/session";

export default function AuthSessionBootstrap() {
  useEffect(() => {
    hydrateSessionFromStorage();
  }, []);

  return null;
}
