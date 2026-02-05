import { Capacitor } from "@capacitor/core";
import { Device } from "@capacitor/device";
import {
  PushNotifications,
  PushNotificationSchema,
  ActionPerformed
} from "@capacitor/push-notifications";
import type { PluginListenerHandle } from "@capacitor/core";

export type NativePushPayload = {
  token: string;
  platform: "android" | "ios";
  device_id: string;
  timezone?: string;
};

export function isNativeMobilePlatform(): boolean {
  if (!Capacitor.isNativePlatform()) return false;
  const platform = Capacitor.getPlatform();
  return platform === "android" || platform === "ios";
}

export async function getNativeDeviceId(): Promise<string | null> {
  if (!isNativeMobilePlatform()) return null;
  const info = await Device.getId();
  return info.identifier || null;
}

export async function registerNativePush(): Promise<NativePushPayload> {
  if (!isNativeMobilePlatform()) {
    throw new Error("native_only");
  }

  const permission = await PushNotifications.requestPermissions();
  if (permission.receive !== "granted") {
    throw new Error("push_permission_denied");
  }

  const platform = Capacitor.getPlatform();
  if (platform !== "android" && platform !== "ios") {
    throw new Error("unsupported_platform");
  }

  const deviceId = await getNativeDeviceId();
  if (!deviceId) {
    throw new Error("device_id_unavailable");
  }

  return new Promise<NativePushPayload>((resolve, reject) => {
    let onSuccess: PluginListenerHandle | null = null;
    let onError: PluginListenerHandle | null = null;

    const cleanup = async () => {
      if (onSuccess) {
        await onSuccess.remove();
      }
      if (onError) {
        await onError.remove();
      }
    };

    const rejectWithError = (err: unknown) => {
      const message = err instanceof Error ? err : new Error(String(err || "push_register_error"));
      cleanup()
        .catch(() => undefined)
        .finally(() => reject(message));
    };

    const timeout = setTimeout(() => {
      rejectWithError(new Error("push_register_timeout"));
    }, 15000);

    const register = async () => {
      onSuccess = await PushNotifications.addListener("registration", (token) => {
        clearTimeout(timeout);
        cleanup()
          .catch(() => undefined)
          .finally(() =>
            resolve({
              token: token.value,
              platform,
              device_id: deviceId,
              timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            })
          );
      });
      onError = await PushNotifications.addListener("registrationError", (error) => {
        clearTimeout(timeout);
        rejectWithError(new Error(String(error?.error || "push_register_error")));
      });

      await PushNotifications.register();
    };

    register().catch((err) => {
      clearTimeout(timeout);
      rejectWithError(err);
    });
  });
}

export async function removeNativePushListeners(): Promise<void> {
  if (!isNativeMobilePlatform()) return;
  await PushNotifications.removeAllListeners();
}

export async function addPassivePushListeners(): Promise<{
  removeAll: () => Promise<void>;
}> {
  if (!isNativeMobilePlatform()) {
    return { removeAll: async () => undefined };
  }
  const received = await PushNotifications.addListener(
    "pushNotificationReceived",
    (_notification: PushNotificationSchema) => undefined
  );
  const action = await PushNotifications.addListener(
    "pushNotificationActionPerformed",
    (_action: ActionPerformed) => undefined
  );
  return {
    removeAll: async () => {
      await received.remove();
      await action.remove();
    }
  };
}
