import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { loadProfileEnv, resolveProfile } from "./mobile-env.mjs";

const frontendRoot = process.cwd();
const profile = resolveProfile(process.argv[2]);
const platform = process.argv[3];

const envOverrides = loadProfileEnv(frontendRoot, profile);
const finalEnv = {
  ...process.env,
  ...envOverrides
};

const capBin = fileURLToPath(
  new URL("../node_modules/@capacitor/cli/bin/capacitor", import.meta.url)
);
const args = ["sync"];
if (platform) {
  args.push(platform);
}

const sync = spawnSync(process.execPath, [capBin, ...args], {
  cwd: frontendRoot,
  env: finalEnv,
  stdio: "inherit"
});

if (sync.error) {
  console.error("[cap-sync-profile] Error ejecutando cap sync:", sync.error);
  process.exit(1);
}

if (sync.status !== 0) {
  process.exit(sync.status ?? 1);
}

console.log(
  `[cap-sync-profile] Perfil=${profile}${platform ? ` plataforma=${platform}` : ""} completado`
);
