import { test, expect } from "@playwright/test";

test.describe("Auth E2E", () => {
  test("navigation vers /login → remplir formulaire → soumettre → redirigé vers /dashboard", async ({
    page,
  }) => {
    // Intercepter les requêtes API d'authentification
    await page.route("**/api/auth/login", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "fake-access-token",
          refresh_token: "fake-refresh-token",
          token_type: "bearer",
        }),
      });
    });

    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "user-1",
          email: "test@test.com",
          is_active: true,
          created_at: "2025-01-01T00:00:00Z",
        }),
      });
    });

    // Aller sur la page login
    await page.goto("/fr/login");

    // Vérifier que le formulaire est visible
    await expect(page.locator("h3")).toContainText("Connectez-vous");
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();

    // Remplir le formulaire
    await page.fill('input[type="email"]', "test@test.com");
    await page.fill('input[type="password"]', "password123");

    // Soumettre
    await page.click('button[type="submit"]');

    // Vérifier la redirection vers /dashboard
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 5000 });
  });

  test("navigation vers / → redirigé vers /fr/login si pas connecté", async ({
    page,
  }) => {
    // Intercepter /api/auth/me pour simuler non-connecté
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      });
    });

    // Aller à la racine
    await page.goto("/");

    // On doit être redirigé vers /fr/login (locale par défaut)
    // La redirection peut mettre un peu de temps
    await expect(page).toHaveURL(/\/fr\/login/, { timeout: 8000 });
  });
});
