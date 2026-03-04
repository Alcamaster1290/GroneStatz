import fs from "node:fs";
import path from "node:path";

const PROFILE_VALUES = new Set(["qa", "prod"]);

export function resolveProfile(rawProfile) {
  const profile = String(rawProfile || "").toLowerCase();
  if (!PROFILE_VALUES.has(profile)) {
    throw new Error(`Perfil invalido '${rawProfile}'. Usa qa o prod.`);
  }
  return profile;
}

function parseEnvFile(content) {
  const parsed = {};
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eqIndex = trimmed.indexOf("=");
    if (eqIndex <= 0) continue;
    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1).trim();
    parsed[key] = value;
  }
  return parsed;
}

export function loadProfileEnv(frontendRoot, profile) {
  const resolvedProfile = resolveProfile(profile);
  const envFile = path.join(frontendRoot, `.env.mobile.${resolvedProfile}`);
  const envFromFile = fs.existsSync(envFile)
    ? parseEnvFile(fs.readFileSync(envFile, "utf8"))
    : {};

  const defaults = {
    NEXT_PUBLIC_APP_CHANNEL: "mobile",
    NEXT_PUBLIC_PUSH_ENABLED: "false",
    MOBILE_BUILD_PROFILE: resolvedProfile,
    CAPACITOR_USE_REMOTE_SERVER: "false"
  };

  return {
    ...defaults,
    ...envFromFile
  };
}
