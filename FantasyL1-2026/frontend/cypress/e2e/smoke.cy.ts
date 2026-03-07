const PUBLIC_ROUTES = ["/landing", "/login", "/ranking", "/fixtures"];

const getAuthCredentials = () => {
  const email = Cypress.env("E2E_EMAIL") as string | undefined;
  const password = Cypress.env("E2E_PASSWORD") as string | undefined;
  if (!email || !password) return null;
  return { email, password };
};

const loginIfCredentialsAvailable = () => {
  const credentials = getAuthCredentials();
  if (!credentials) {
    cy.log("Skipping private smoke checks: CYPRESS_E2E_EMAIL/CYPRESS_E2E_PASSWORD not set.");
    return;
  }

  cy.visit("/login?redirect=/app");
  cy.get('input[placeholder="email"]').clear().type(credentials.email);
  cy.get('input[placeholder="password"]').clear().type(credentials.password, { log: false });
  cy.contains("button", "Login").click();
  cy.url({ timeout: 15000 }).should("include", "/team");
};

describe("Smoke routes", () => {
  it("loads all public routes", () => {
    PUBLIC_ROUTES.forEach((route) => {
      cy.visit(route);
      cy.get("body").should("be.visible");
    });
  });

  it("can run private core flow when credentials are available", () => {
    loginIfCredentialsAvailable();
    const credentials = getAuthCredentials();
    if (!credentials) return;

    cy.visit("/team");
    cy.contains(/Fantasy Liga 1 2026|Fantasy Liga 1/).should("be.visible");

    cy.visit("/market");
    cy.contains("Mercado").should("be.visible");

    cy.visit("/stats");
    cy.contains("Estadisticas").should("be.visible");

    cy.visit("/settings");
    cy.contains("Ajustes").should("be.visible");
  });
});
