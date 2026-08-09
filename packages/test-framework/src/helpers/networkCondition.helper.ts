export type NetworkCondition = "online" | "offline" | "slow";

export async function applyNetworkCondition(
  page: { context: () => { setOffline: (offline: boolean) => Promise<void> } },
  condition: NetworkCondition
): Promise<void> {
  await page.context().setOffline(condition === "offline");
  if (condition === "slow") {
    await new Promise((resolve) => setTimeout(resolve, 750));
  }
}
