const PUBLIC_ROUTES = [
  { path: "/landing", name: "landing" },
  { path: "/login", name: "login" },
  { path: "/ranking", name: "ranking" },
  { path: "/fixtures", name: "fixtures" }
];

const PRIVATE_ROUTES = [
  { path: "/team", name: "team" },
  { path: "/market", name: "market" },
  { path: "/stats", name: "stats" },
  { path: "/settings", name: "settings" }
];

const captureRoute = (path: string, name: string) => {
  cy.viewport(390, 844);
  cy.visit(path);
  cy.get("body").should("be.visible");
  cy.percySnapshot(`${name} - mobile`);

  cy.viewport(1280, 720);
  cy.visit(path);
  cy.get("body").should("be.visible");
  cy.percySnapshot(`${name} - desktop`);
};

const hasCredentials = () => {
  const email = Cypress.env("E2E_EMAIL") as string | undefined;
  const password = Cypress.env("E2E_PASSWORD") as string | undefined;
  return Boolean(email && password);
};

const login = () => {
  const email = Cypress.env("E2E_EMAIL") as string;
  const password = Cypress.env("E2E_PASSWORD") as string;
  cy.visit("/login?redirect=/app");
  cy.get('input[placeholder="email"]').clear().type(email);
  cy.get('input[placeholder="password"]').clear().type(password, { log: false });
  cy.contains("button", "Login").click();
  cy.url({ timeout: 15000 }).should("include", "/team");
};

describe("Visual regression", () => {
  it("captures public routes", () => {
    PUBLIC_ROUTES.forEach((route) => captureRoute(route.path, route.name));
  });

  it("captures login validation state", () => {
    cy.viewport(390, 844);
    cy.visit("/login");
    cy.contains("button", "Login").click();
    cy.percySnapshot("login-errors - mobile");
  });

  it("captures private routes when credentials are available", () => {
    if (!hasCredentials()) {
      cy.log("Skipping private visual snapshots: CYPRESS_E2E_EMAIL/CYPRESS_E2E_PASSWORD not set.");
      return;
    }

    login();
    PRIVATE_ROUTES.forEach((route) => captureRoute(route.path, route.name));
  });
});
