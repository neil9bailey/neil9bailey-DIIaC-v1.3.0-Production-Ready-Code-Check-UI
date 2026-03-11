// Tests for auth/roleMapping.ts — Vitest
import { describe, it, expect } from "vitest";
import { resolveRole } from "./roleMapping";

describe("resolveRole", () => {
  it("returns viewer when no groups or roles match", () => {
    const result = resolveRole({});
    expect(result.role).toBe("viewer");
    expect(result.subroles).toEqual([]);
    expect(result.groups).toEqual([]);
  });

  it("resolves admin from named app role", () => {
    const result = resolveRole({ roles: ["admin"] });
    expect(result.role).toBe("admin");
  });

  it("resolves standard from named app role", () => {
    const result = resolveRole({ roles: ["standard"] });
    expect(result.role).toBe("standard");
  });

  it("resolves standard from StandardUser app role", () => {
    const result = resolveRole({ roles: ["StandardUser"] });
    expect(result.role).toBe("standard");
  });

  it("resolves viewer from named viewer role", () => {
    const result = resolveRole({ roles: ["viewer"] });
    expect(result.role).toBe("viewer");
  });

  it("app role takes priority over group-based role", () => {
    const result = resolveRole({
      roles: ["admin"],
      groups: ["unknown-group-oid"],
    });
    expect(result.role).toBe("admin");
  });

  it("deduplicates group candidates across groups and roles claims", () => {
    const oid = "some-shared-oid";
    const result = resolveRole({ groups: [oid], roles: [oid] });
    expect(result.groups.filter((g) => g === oid).length).toBe(1);
  });

  it("handles non-array claims gracefully", () => {
    const result = resolveRole({ groups: "not-an-array", roles: null });
    expect(result.role).toBe("viewer");
  });

  it("returns RoleResolution shape with all required fields", () => {
    const result = resolveRole({ roles: ["admin"] });
    expect(result).toHaveProperty("role");
    expect(result).toHaveProperty("subroles");
    expect(result).toHaveProperty("groups");
    expect(Array.isArray(result.subroles)).toBe(true);
    expect(Array.isArray(result.groups)).toBe(true);
  });
});
