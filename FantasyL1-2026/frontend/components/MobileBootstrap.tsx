"use client";

import { useEffect } from "react";

import { addPassivePushListeners, isNativeMobilePlatform } from "@/lib/mobile/push";

export default function MobileBootstrap() {
  useEffect(() => {
    let removeNetwork: () => Promise<void> = async () => {};
    let removePush: () => Promise<void> = async () => {};

    const syncConnectivityHint = (connected: boolean) => {
      if (typeof document === "undefined") return;
      document.documentElement.dataset.online = connected ? "true" : "false";
    };

    const bootstrap = async () => {
      if (!isNativeMobilePlatform()) return;
      const { Network } = await import("@capacitor/network");

      const pushHandle = await addPassivePushListeners();
      removePush = pushHandle.removeAll;

      const initialStatus = await Network.getStatus();
      syncConnectivityHint(initialStatus.connected);
      const networkHandle = await Network.addListener("networkStatusChange", (status) => {
        syncConnectivityHint(status.connected);
      });
      removeNetwork = async () => {
        await networkHandle.remove();
      };
    };

    bootstrap().catch(() => undefined);

    return () => {
      removeNetwork().catch(() => undefined);
      removePush().catch(() => undefined);
    };
  }, []);

  return null;
}
