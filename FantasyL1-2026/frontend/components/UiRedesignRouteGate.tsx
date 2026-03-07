"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import {
  getUiRedesignRouteKey,
  isUiRedesignEnabledForPath
} from "@/lib/ui-redesign";

export default function UiRedesignRouteGate() {
  const pathname = usePathname() || "/";
  const enabled = isUiRedesignEnabledForPath(pathname);
  const routeKey = getUiRedesignRouteKey(pathname);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.uiRedesign = enabled ? "1" : "0";

    if (enabled && routeKey) {
      root.dataset.uiRedesignRoute = routeKey;
      return;
    }

    delete root.dataset.uiRedesignRoute;
  }, [enabled, routeKey]);

  return null;
}
