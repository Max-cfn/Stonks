// Tests for token store utilities (no React needed)
import { formatCurrency, formatPercent, formatLargeNumber } from "../formatters";

describe("token store / formatters", () => {
  it("formatPercent handles edge cases", () => {
    expect(formatPercent(0)).toBe("+0.00%");
    expect(formatPercent(-5)).toBe("-5.00%");
    expect(formatPercent(null)).toBe("N/A");
    expect(formatPercent(undefined)).toBe("N/A");
  });

  it("formatLargeNumber scales correctly", () => {
    expect(formatLargeNumber(1_500_000)).toBe("1.5M");
    expect(formatLargeNumber(4_200)).toBe("4.2k");
    expect(formatLargeNumber(42)).toBe("42.00");
  });
});
