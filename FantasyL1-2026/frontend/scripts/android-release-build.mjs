import path from "node:path";
import { spawnSync } from "node:child_process";

import { loadProfileEnv, resolveProfile } from "./mobile-env.mjs";

function runStep(step, cmd, args, options) {
  const child = spawnSync(cmd, args, {
    stdio: "inherit",
    ...options
  });

  if (child.error) {
    console.error(`[android-release-build] ${step} fallo:`, child.error);
    process.exit(1);
  }
  if (child.status !== 0) {
    process.exit(child.status ?? 1);
  }
}

const frontendRoot = process.cwd();
const profile = resolveProfile(process.argv[2]);
const gradleTask = process.argv[3] || "bundleRelease";
const envOverrides = loadProfileEnv(frontendRoot, profile);
const finalEnv = {
  ...process.env,
  ...envOverrides
};

const buildScript = path.join(frontendRoot, "scripts", "mobile-bundle-build.mjs");
const syncScript = path.join(frontendRoot, "scripts", "cap-sync-profile.mjs");
const androidDir = path.join(frontendRoot, "android");

runStep("build mobile bundle", process.execPath, [buildScript, profile], {
  cwd: frontendRoot,
  env: finalEnv
});

runStep("cap sync android", process.execPath, [syncScript, profile, "android"], {
  cwd: frontendRoot,
  env: finalEnv
});

if (process.platform === "win32") {
  runStep("gradle release", "cmd.exe", ["/c", "gradlew.bat", gradleTask], {
    cwd: androidDir,
    env: finalEnv
  });
} else {
  runStep("gradle release", "./gradlew", [gradleTask], {
    cwd: androidDir,
    env: finalEnv
  });
}

console.log(`[android-release-build] Perfil=${profile} tarea=${gradleTask} completado`);
