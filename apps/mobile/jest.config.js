module.exports = {
  preset: "jest-expo",
  transformIgnorePatterns: [],
  setupFiles: ["./src/test-setup.ts"],
  collectCoverageFrom: [
    "src/hooks/**/*.{ts,tsx}",
    "!**/*.d.ts",
    "!**/node_modules/**",
  ],
  coverageThreshold: {
    global: { branches: 10, functions: 10, lines: 10, statements: 10 },
  },
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" },
};
