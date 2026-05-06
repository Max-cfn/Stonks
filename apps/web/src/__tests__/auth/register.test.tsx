import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const { authDict, commonDict, mockRegisterFn } = vi.hoisted(() => ({
  authDict: {
    email: "Email",
    password: "Mot de passe",
    confirmPassword: "Confirmer le mot de passe",
    registerTitle: "Créez votre compte",
    hasAccount: "Déjà un compte ?",
    emailRequired: "L'email est obligatoire",
    emailInvalid: "Veuillez entrer une adresse email valide",
    passwordRequired: "Le mot de passe est obligatoire",
    passwordMinLength: "Le mot de passe doit contenir au moins 8 caractères",
    confirmPasswordRequired: "Veuillez confirmer votre mot de passe",
    passwordsDoNotMatch: "Les mots de passe ne correspondent pas",
    registerError: "L'inscription a échoué. Veuillez réessayer.",
  } as Record<string, string>,
  commonDict: {
    login: "Connexion",
    register: "Inscription",
  } as Record<string, string>,
  mockRegisterFn: vi.fn(),
}));

vi.mock("next-intl", () => ({
  useTranslations: (ns?: string) => {
    const dict = ns === "common" ? commonDict : authDict;
    return (key: string) => dict[key] ?? key;
  },
}));

vi.mock("@/lib/auth/useAuth", () => ({
  useAuth: () => ({ register: mockRegisterFn }),
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => ({ push: vi.fn() }),
  Link: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

import RegisterPage from "@/app/[locale]/(auth)/register/page";

function setInput(element: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, "value",
  )?.set;
  setter?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  element.dispatchEvent(new Event("blur", { bubbles: true }));
}

describe("RegisterPage", () => {
  it("affiche le formulaire avec email, password, confirmPassword", () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Mot de passe")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirmer le mot de passe")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Inscription" })).toBeInTheDocument();
  });

  it("validation — passwords non identiques affiche erreur", async () => {
    render(<RegisterPage />);
    setInput(screen.getByLabelText("Email") as HTMLInputElement, "test@test.com");
    setInput(screen.getByLabelText("Mot de passe") as HTMLInputElement, "password123");
    setInput(screen.getByLabelText("Confirmer le mot de passe") as HTMLInputElement, "different");
    screen.getByRole("button", { name: "Inscription" }).click();

    expect(await screen.findByText("Les mots de passe ne correspondent pas")).toBeInTheDocument();
  });

  it("validation — password trop court affiche erreur", async () => {
    render(<RegisterPage />);
    setInput(screen.getByLabelText("Email") as HTMLInputElement, "test@test.com");
    setInput(screen.getByLabelText("Mot de passe") as HTMLInputElement, "abc");
    setInput(screen.getByLabelText("Confirmer le mot de passe") as HTMLInputElement, "abc");
    screen.getByRole("button", { name: "Inscription" }).click();

    expect(await screen.findByText(/8 caractères/)).toBeInTheDocument();
  });

  it("validation — champs vides affichent erreurs", async () => {
    render(<RegisterPage />);
    screen.getByRole("button", { name: "Inscription" }).click();

    expect(await screen.findByText("L'email est obligatoire")).toBeInTheDocument();
    expect(screen.getByText("Le mot de passe est obligatoire")).toBeInTheDocument();
    expect(screen.getByText("Veuillez confirmer votre mot de passe")).toBeInTheDocument();
  });

  it("soumission valide appelle register", async () => {
    mockRegisterFn.mockReset();
    mockRegisterFn.mockResolvedValue(undefined);
    render(<RegisterPage />);

    setInput(screen.getByLabelText("Email") as HTMLInputElement, "test@test.com");
    setInput(screen.getByLabelText("Mot de passe") as HTMLInputElement, "password123");
    setInput(screen.getByLabelText("Confirmer le mot de passe") as HTMLInputElement, "password123");
    screen.getByRole("button", { name: "Inscription" }).click();

    await waitFor(() => {
      expect(mockRegisterFn).toHaveBeenCalledWith({
        email: "test@test.com",
        password: "password123",
      });
    });
  });

  it("affiche le lien vers la page login", () => {
    render(<RegisterPage />);
    const loginLink = screen.getByRole("link", { name: "Connexion" });
    expect(loginLink).toBeInTheDocument();
    expect(loginLink).toHaveAttribute("href", "/login");
  });
});
