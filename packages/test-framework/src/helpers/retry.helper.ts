export type RetryOptions = {
  timeoutMs?: number;
  intervalMs?: number;
  description?: string;
};

export async function retryUntil<T>(
  operation: () => Promise<T>,
  predicate: (value: T) => boolean,
  options: RetryOptions = {}
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? 30_000;
  const intervalMs = options.intervalMs ?? 500;
  const deadline = Date.now() + timeoutMs;
  let lastValue: T | undefined;
  let lastError: unknown;

  while (Date.now() < deadline) {
    try {
      lastValue = await operation();
      if (predicate(lastValue)) {
        return lastValue;
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  const suffix = options.description ? ` while waiting for ${options.description}` : "";
  throw new Error(`Timed out after ${timeoutMs}ms${suffix}`, { cause: lastError ?? lastValue });
}
