import { spawn } from "node:child_process";
import path from "node:path";

const modeArg = process.argv[2] ?? "smoke";

const modeConfig = {
  smoke: {
    defaultPort: "3101",
    command: "node ./scripts/run-cypress.mjs run --spec cypress/e2e/smoke.cy.ts"
  },
  visual: {
    defaultPort: "3102",
    command: "node ./scripts/run-cypress.mjs run --spec cypress/e2e/visual.cy.ts"
  },
  "percy-visual": {
    defaultPort: "3102",
    command: "percy exec -- node ./scripts/run-cypress.mjs run --spec cypress/e2e/visual.cy.ts"
  }
};

const selectedMode = modeConfig[modeArg] ? modeArg : "smoke";
const hasPercyToken = Boolean(process.env.PERCY_TOKEN);
const effectiveMode = selectedMode === "percy-visual" && !hasPercyToken ? "visual" : selectedMode;
const mode = modeConfig[effectiveMode];

if (selectedMode === "percy-visual" && !hasPercyToken) {
  console.warn("[visual] PERCY_TOKEN missing: running local visual E2E without Percy snapshots.");
}

const port = process.env.E2E_TEST_PORT || mode.defaultPort;
const baseUrl = process.env.CYPRESS_BASE_URL || `http://127.0.0.1:${port}`;
const env = {
  ...process.env,
  CYPRESS_BASE_URL: baseUrl
};
delete env.ELECTRON_RUN_AS_NODE;

const startServerAndTestBin = path.join(
  process.cwd(),
  "node_modules",
  "start-server-and-test",
  "src",
  "bin",
  "start.js"
);

const startCommand = `next start -p ${port}`;
const waitUrl = `http-get://127.0.0.1:${port}`;

const child = spawn(
  process.execPath,
  [startServerAndTestBin, startCommand, waitUrl, mode.command],
  {
    env,
    stdio: "inherit"
  }
);

child.on("exit", (code) => {
  process.exit(code ?? 1);
});

child.on("error", (error) => {
  console.error("Failed to run start-server-and-test:", error);
  process.exit(1);
});
