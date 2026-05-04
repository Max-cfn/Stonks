import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

// ── Mocks hoisted ──
const { simDict } = vi.hoisted(() => ({
  simDict: {
    title: "Simulateur",
    initial: "Montant initial (€)",
    monthly: "Apport mensuel (€)",
    rate: "Taux annuel (%)",
    years: "Durée (années)",
    futureValue: "Valeur future",
    totalContributions: "Total des versements",
    totalInterest: "Intérêts générés",
    calculate: "Calculer",
  } as Record<string, string>,
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => simDict[key] ?? key,
}));

vi.mock("recharts", () => ({
  AreaChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="area-chart">{children}</div>
  ),
  Area: () => <div data-testid="area" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="recharts-tooltip" />,
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
}));

vi.mock("@/components/ui/error-boundary", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { SimulatorView } from "@/app/[locale]/(authenticated)/portfolio/simulator/SimulatorView";

// ── Helper ──
function fillInput(label: string, value: string) {
  const input = screen.getByLabelText(label);
  fireEvent.change(input, { target: { value } });
}

// ── Tests ──
describe("SimulatorView", () => {
  it("affiche le titre", () => {
    render(<SimulatorView />);
    expect(screen.getByText("Simulateur")).toBeInTheDocument();
  });

  it("affiche les 4 champs du formulaire", () => {
    render(<SimulatorView />);

    expect(screen.getByLabelText("Montant initial (€)")).toBeInTheDocument();
    expect(screen.getByLabelText("Apport mensuel (€)")).toBeInTheDocument();
    expect(screen.getByLabelText("Taux annuel (%)")).toBeInTheDocument();
    expect(screen.getByLabelText("Durée (années)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Calculer/ })).toBeInTheDocument();
  });

  it("affiche les valeurs par défaut dans les champs", () => {
    render(<SimulatorView />);

    expect(screen.getByLabelText("Montant initial (€)")).toHaveValue(10000);
    expect(screen.getByLabelText("Apport mensuel (€)")).toHaveValue(500);
    expect(screen.getByLabelText("Taux annuel (%)")).toHaveValue(7);
    expect(screen.getByLabelText("Durée (années)")).toHaveValue(20);
  });

  it("calcule automatiquement au premier rendu et affiche les résultats", async () => {
    render(<SimulatorView />);

    await waitFor(() => {
      expect(screen.getByText("Valeur future")).toBeInTheDocument();
      expect(screen.getByText("Total des versements")).toBeInTheDocument();
      expect(screen.getByText("Intérêts générés")).toBeInTheDocument();
    });
  });

  it("rend le graphique Recharts", async () => {
    render(<SimulatorView />);

    await waitFor(() => {
      expect(screen.getByTestId("area-chart")).toBeInTheDocument();
    });
  });

  it("recalcule quand on change les paramètres et soumet", async () => {
    render(<SimulatorView />);

    fillInput("Montant initial (€)", "5000");
    fillInput("Apport mensuel (€)", "200");
    fillInput("Taux annuel (%)", "5");
    fillInput("Durée (années)", "10");

    fireEvent.click(screen.getByRole("button", { name: /Calculer/ }));

    await waitFor(() => {
      expect(screen.getByText("Valeur future")).toBeInTheDocument();
    });
  });
});
