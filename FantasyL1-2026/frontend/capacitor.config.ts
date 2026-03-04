import type { CapacitorConfig } from "@capacitor/cli";

const mobileWebUrl =
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL || "https://fantasyliga1peru.com";
const mobileBuildProfile = (process.env.MOBILE_BUILD_PROFILE || "dev").toLowerCase();
const useRemoteServer =
  process.env.CAPACITOR_USE_REMOTE_SERVER === "true" || mobileBuildProfile === "dev";

const config: CapacitorConfig = {
  appId: "com.gronestatz.fantasyliga1",
  appName: "Fantasy Liga 1 2026",
  webDir: "www",
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"]
    }
  }
};

if (useRemoteServer) {
  config.server = {
    url: mobileWebUrl,
    cleartext: mobileWebUrl.startsWith("http://"),
    androidScheme: "https"
  };
}

export default config;
