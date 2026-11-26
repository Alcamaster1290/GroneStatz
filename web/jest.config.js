const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

module.exports = createJestConfig({
  testEnvironment: "node",
  testMatch: ["<rootDir>/lib/**/*.test.ts"],
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/$1" },
});
