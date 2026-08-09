export function correlationId(prefix = "test"): string {
  const random = Math.random().toString(16).slice(2, 10);
  return `${prefix}-${Date.now()}-${random}`.slice(0, 64);
}

export function expectCorrelationId(value: string | null | undefined): asserts value is string {
  if (!value || value.length < 8 || value.length > 64) {
    throw new Error(`Invalid correlation id: ${value ?? "<missing>"}`);
  }
}
