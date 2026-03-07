import { spawn } from "node:child_process";
import path from "node:path";

const args = process.argv.slice(2);

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

const cypressCli = path.join(process.cwd(), "node_modules", "cypress", "bin", "cypress");

const child = spawn(process.execPath, [cypressCli, ...args], {
  env,
  stdio: "inherit"
});

child.on("exit", (code) => {
  process.exit(code ?? 1);
});

child.on("error", (error) => {
  console.error("Failed to launch Cypress:", error);
  process.exit(1);
});
