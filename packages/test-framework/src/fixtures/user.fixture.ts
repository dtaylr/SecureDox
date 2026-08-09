import type { Role } from "../clients/ApiClient.js";

export type TestUser = {
  username: Role;
  password: string;
  tenantId: string;
  roles: Role[];
};

export function testUserFactory(overrides: Partial<TestUser> = {}): TestUser {
  const username = overrides.username ?? "admin";
  return {
    username,
    password: overrides.password ?? "securedox-demo",
    tenantId: overrides.tenantId ?? "acme-lending",
    roles: overrides.roles ?? [username],
    ...overrides
  };
}
