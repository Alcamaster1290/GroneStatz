import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

import { loadProfileEnv, resolveProfile } from "./mobile-env.mjs";

const frontendRoot = process.cwd();
const profile = resolveProfile(process.argv[2]);
const envOverrides = loadProfileEnv(frontendRoot, profile);
const finalEnv = {
  ...process.env,
  ...envOverrides
};

const apiUrl = finalEnv.NEXT_PUBLIC_API_URL || "";
if (!/^https?:\/\//i.test(apiUrl)) {
  throw new Error(
    `NEXT_PUBLIC_API_URL invalida para perfil ${profile}. Debe ser URL absoluta (http/https).`
  );
}

const nextBin = path.join(frontendRoot, "node_modules", "next", "dist", "bin", "next");
const build = spawnSync(process.execPath, [nextBin, "build"], {
  cwd: frontendRoot,
  env: finalEnv,
  stdio: "inherit"
});

if (build.error) {
  console.error("[mobile-bundle-build] Error ejecutando next build:", build.error);
  process.exit(1);
}

if (build.status !== 0) {
  process.exit(build.status ?? 1);
}

const outDir = path.join(frontendRoot, "out");
const wwwDir = path.join(frontendRoot, "www");

if (!fs.existsSync(outDir)) {
  throw new Error(
    `No se encontro ${outDir}. Verifica que next.config.js use output='export' para MOBILE_BUILD_PROFILE=${profile}.`
  );
}

fs.rmSync(wwwDir, { recursive: true, force: true });
fs.cpSync(outDir, wwwDir, { recursive: true });

console.log(`[mobile-bundle-build] Perfil=${profile} listo en ${wwwDir}`);
