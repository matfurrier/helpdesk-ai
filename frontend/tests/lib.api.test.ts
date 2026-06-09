import { describe, it, expect } from "vitest";
import { buildApiUrl } from "@/lib/api";

describe("buildApiUrl", () => {
  it("returns a relative path in browser context (proxy rewrite)", () => {
    // Client-side API_BASE is "" — requests go to the same origin and are
    // proxied by Next.js rewrites to the backend. No hardcoded host/port.
    expect(buildApiUrl("/health")).toBe("/health");
  });
});
