import { formatCurrency, formatPercent, formatDate, truncate, formatLargeNumber } from "../formatters";

// Test pure utility functions that don't need React
describe("formatters", () => {
  describe("formatCurrency", () => {
    it("should format EUR amount with euro sign", () => {
      const result = formatCurrency(1234.56, "EUR");
      expect(result).toContain("1");
      expect(result).toContain("234,56");
      expect(result).toContain("€");
    });

    it("should format USD amount correctly", () => {
      expect(formatCurrency(1234.56, "USD")).toBe("$1,234.56");
    });

    it("should handle zero", () => {
      const result = formatCurrency(0, "EUR");
      expect(result).toContain("0,00");
      expect(result).toContain("€");
    });

    it("should handle negative amounts", () => {
      const result = formatCurrency(-500, "EUR");
      expect(result).toContain("-500");
      expect(result).toContain("€");
    });
  });

  describe("formatPercent", () => {
    it("should format positive percentage", () => {
      expect(formatPercent(5.23)).toBe("+5.23%");
    });

    it("should format negative percentage", () => {
      expect(formatPercent(-3.1)).toBe("-3.10%");
    });

    it("should format zero with plus sign", () => {
      expect(formatPercent(0)).toBe("+0.00%");
    });

    it("should handle null/undefined", () => {
      expect(formatPercent(null)).toBe("N/A");
      expect(formatPercent(undefined)).toBe("N/A");
    });
  });

  describe("formatDate", () => {
    it("should format ISO date string", () => {
      const result = formatDate("2026-01-15T10:30:00Z", "fr");
      expect(result).toContain("2026");
    });

    it("should return placeholder for invalid date", () => {
      expect(formatDate("invalid")).toBe("—");
    });
  });

  describe("truncate", () => {
    it("should truncate long strings", () => {
      expect(truncate("Hello World", 5)).toBe("Hello...");
    });

    it("should not truncate short strings", () => {
      expect(truncate("Hi", 5)).toBe("Hi");
    });
  });

  describe("formatLargeNumber", () => {
    it("should format millions", () => {
      expect(formatLargeNumber(1_500_000)).toBe("1.5M");
    });

    it("should format thousands", () => {
      expect(formatLargeNumber(4_200)).toBe("4.2k");
    });
  });
});
