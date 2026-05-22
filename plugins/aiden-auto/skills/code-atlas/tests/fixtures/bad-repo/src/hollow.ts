// H3 — hollow stubs

export function processPayment(amount: number): boolean {
  return false // TODO: implement
}

export function sendNotification(userId: string): void {
  // FIXME: wire up service
}

export function computeTax(value: number): number {
  throw new Error('not implemented')
}

export const emptyArrow = () => null

export function realFunction(x: number): number {
  const doubled = x * 2
  const squared = doubled * doubled
  return squared - 1
}
