import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/Sidebar";

// ── Mocks ──

const tMock = vi.fn((key: string) => {
  const dict: Record<string, string> = {
    dashboard: "Tableau de bord",
    cashflow: "Trésorerie",
    portfolio: "Portefeuille",
    simulator: "Simulateur",
    settings: "Paramètres",
  };
  return dict[key] ?? key;
});

vi.mock("next-intl", () => ({
  useTranslations: () => tMock,
}));

// Mock usePathname pour simuler la navigation active
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

// Mock icônes lucide
vi.mock("lucide-react", () => ({
  LayoutDashboard: () => <span data-testid="icon-dashboard" />,
  ArrowLeftRight: () => <span data-testid="icon-cashflow" />,
  Briefcase: () => <span data-testid="icon-portfolio" />,
  Play: () => <span data-testid="icon-simulator" />,
  Settings: () => <span data-testid="icon-settings" />,
  TrendingUp: () => <span data-testid="icon-trending" />,
}));

// ── Tests ──

describe("Sidebar", () => {
  it("rend les 5 liens de navigation", () => {
    mockPathname.mockReturnValue("/fr/dashboard");
    render(<Sidebar locale="fr" />);

    expect(screen.getByText("Tableau de bord")).toBeInTheDocument();
    expect(screen.getByText("Trésorerie")).toBeInTheDocument();
    expect(screen.getByText("Portefeuille")).toBeInTheDocument();
    expect(screen.getByText("Simulateur")).toBeInTheDocument();
    expect(screen.getByText("Paramètres")).toBeInTheDocument();
  });

  it("les liens pointent vers les bonnes URLs avec le locale", () => {
    mockPathname.mockReturnValue("/fr/dashboard");
    render(<Sidebar locale="fr" />);

    expect(screen.getByText("Tableau de bord").closest("a")).toHaveAttribute(
      "href",
      "/fr/dashboard",
    );
    expect(screen.getByText("Trésorerie").closest("a")).toHaveAttribute(
      "href",
      "/fr/cashflow",
    );
    expect(screen.getByText("Portefeuille").closest("a")).toHaveAttribute(
      "href",
      "/fr/portfolio",
    );
    expect(screen.getByText("Simulateur").closest("a")).toHaveAttribute(
      "href",
      "/fr/portfolio/simulator",
    );
    expect(screen.getByText("Paramètres").closest("a")).toHaveAttribute(
      "href",
      "/fr/settings",
    );
  });

  it("lien dashboard actif a la classe appropriée", () => {
    mockPathname.mockReturnValue("/fr/dashboard");
    render(<Sidebar locale="fr" />);

    const dashboardLink = screen.getByText("Tableau de bord").closest("a");
    expect(dashboardLink).toHaveClass("bg-primary/10");
    expect(dashboardLink).toHaveClass("text-primary");

    // Les autres ne doivent pas avoir la classe active
    const cashflowLink = screen.getByText("Trésorerie").closest("a");
    expect(cashflowLink).not.toHaveClass("bg-primary/10");
    expect(cashflowLink).toHaveClass("text-muted-foreground");
  });

  it("lien simulator actif quand on est sur /portfolio/simulator", () => {
    mockPathname.mockReturnValue("/fr/portfolio/simulator");
    render(<Sidebar locale="fr" />);

    const simulatorLink = screen.getByText("Simulateur").closest("a");
    expect(simulatorLink).toHaveClass("bg-primary/10");

    // Dashboard ne doit PAS être actif
    const dashboardLink = screen.getByText("Tableau de bord").closest("a");
    expect(dashboardLink).not.toHaveClass("bg-primary/10");
  });

  it("lien portfolio actif quand on est sur /portfolio", () => {
    mockPathname.mockReturnValue("/fr/portfolio");
    render(<Sidebar locale="fr" />);

    const portfolioLink = screen.getByText("Portefeuille").closest("a");
    expect(portfolioLink).toHaveClass("bg-primary/10");
  });

  it("affiche le branding Stonks", () => {
    mockPathname.mockReturnValue("/fr/dashboard");
    render(<Sidebar locale="fr" />);

    expect(screen.getByText("Stonks")).toBeInTheDocument();
    expect(screen.getByTestId("icon-trending")).toBeInTheDocument();
  });

  it("liens avec locale anglais pointent vers /en/...", () => {
    mockPathname.mockReturnValue("/en/dashboard");
    render(<Sidebar locale="en" />);

    expect(screen.getByText("Tableau de bord").closest("a")).toHaveAttribute(
      "href",
      "/en/dashboard",
    );
    expect(screen.getByText("Trésorerie").closest("a")).toHaveAttribute(
      "href",
      "/en/cashflow",
    );
  });
});
