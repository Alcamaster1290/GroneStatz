import type { CapacitorConfig } from "@capacitor/cli";

const mobileWebUrl =
  process.env.NEXT_PUBLIC_MOBILE_WEB_URL || "https://fantasyliga1peru.com";

const config: CapacitorConfig = {
  appId: "com.gronestatz.fantasyliga1",
  appName: "Fantasy Liga 1 2026",
  webDir: "www",
  server: {
    url: mobileWebUrl,
    cleartext: mobileWebUrl.startsWith("http://"),
    androidScheme: "https"
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"]
    }
  }
};

export default config;
