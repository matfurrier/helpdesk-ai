import { describe, it, expect } from "vitest";
import { buildApiUrl } from "@/lib/api";

describe("buildApiUrl", () => {
  it("joins base and path correctly", () => {
    expect(buildApiUrl("/health")).toBe("http://localhost:8004/health");
  });
});
