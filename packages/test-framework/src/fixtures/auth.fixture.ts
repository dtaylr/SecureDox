import { ApiClient, type Role } from "../clients/ApiClient.js";
import { testUserFactory, type TestUser } from "./user.fixture.js";

export async function loginAs(
  api: ApiClient,
  role: Role = "admin",
  overrides: Partial<TestUser> = {}
): Promise<TestUser> {
  const user = testUserFactory({ username: role, ...overrides });
  await api.login({
    username: user.username,
    password: user.password,
    tenantId: user.tenantId
  });
  return user;
}
