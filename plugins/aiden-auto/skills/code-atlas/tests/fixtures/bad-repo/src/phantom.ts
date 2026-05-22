// H1 — imports a module that does not exist (no such file)
import { useAuth } from '@/lib/hooks/useAuth'
// H1 — relative phantom
import { helper } from './nonexistent-helper'

export function phantomConsumer() {
  const _a = useAuth()
  const _b = helper()
  return 'ok'
}
