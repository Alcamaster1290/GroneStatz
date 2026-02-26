"use client";

import { usePathname } from "next/navigation";

import AppHeader from "@/components/AppHeader";

export default function RouteAwareHeader() {
  const pathname = usePathname();

  if (pathname === "/") {
    return null;
  }

  return <AppHeader />;
}
