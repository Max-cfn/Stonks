import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const { authDict, commonDict, mockLoginFn } = vi.hoisted(() => ({
  authDict: {
    email: "Email",
    password: "Mot de passe",
    loginTitle: "Connectez-vous à votre compte",
    noAccount: "Pas encore de compte ?",
    emailRequired: "L'email est obligatoire",
    emailInvalid: "Veuillez entrer une adresse email valide",
    passwordRequired: "Le mot de passe est obligatoire",
    passwordMinLength: "Le mot de passe doit contenir au moins 8 caractères",
    loginError: "Email ou mot de passe incorrect.",
  } as Record<string, string>,
  commonDict: {
    login: "Connexion",
    register: "Inscription",
  } as Record<string, string>,
  mockLoginFn: vi.fn(),
}));

vi.mock("next-intl", () => ({
  useTranslations: (ns?: string) => {
    const dict = ns === "common" ? commonDict : authDict;
    return (key: string) => dict[key] ?? key;
  },
}));

vi.mock("@/lib/auth/useAuth", () => ({
  useAuth: () => ({ login: mockLoginFn }),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: vi.fn() }),
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

import LoginPage from "@/app/[locale]/(auth)/login/page";

function setInput(element: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, "value",
  )?.set;
  setter?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  element.dispatchEvent(new Event("blur", { bubbles: true }));
}

describe("LoginPage", () => {
  it("affiche le formulaire avec les champs email + password", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Mot de passe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connexion" })).toBeInTheDocument();
  });

  it("validation zod — champs vides affichent erreurs", async () => {
    render(<LoginPage />);
    screen.getByRole("button", { name: "Connexion" }).click();

    expect(await screen.findByText("L'email est obligatoire")).toBeInTheDocument();
    expect(screen.getByText("Le mot de passe est obligatoire")).toBeInTheDocument();
  });

  it("validation zod — password trop court affiche erreur", async () => {
    render(<LoginPage />);

    setInput(screen.getByLabelText("Email") as HTMLInputElement, "test@test.com");
    setInput(screen.getByLabelText("Mot de passe") as HTMLInputElement, "abc");
    screen.getByRole("button", { name: "Connexion" }).click();

    expect(await screen.findByText(/8 caractères/)).toBeInTheDocument();
  });

  it("soumission avec credentials valides appelle login", async () => {
    mockLoginFn.mockReset();
    mockLoginFn.mockResolvedValue(undefined);

    render(<LoginPage />);

    setInput(screen.getByLabelText("Email") as HTMLInputElement, "test@test.com");
    setInput(screen.getByLabelText("Mot de passe") as HTMLInputElement, "password123");
    screen.getByRole("button", { name: "Connexion" }).click();

    await waitFor(() => {
      expect(mockLoginFn).toHaveBeenCalledWith({
        email: "test@test.com",
        password: "password123",
      });
    });
  });

  it("affiche le lien vers la page register", () => {
    render(<LoginPage />);
    const registerLink = screen.getByRole("link", { name: "Inscription" });
    expect(registerLink).toBeInTheDocument();
    expect(registerLink).toHaveAttribute("href", "/register");
  });
});
