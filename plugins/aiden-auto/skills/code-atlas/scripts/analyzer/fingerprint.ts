import { createHash } from 'node:crypto'
import type { HallucinationKind } from './types.js'

export function fingerprint(
  kind: HallucinationKind,
  file: string,
  line: number,
  extra: string = '',
): string {
  return createHash('sha256')
    .update(`${kind}|${file}|${line}|${extra}`)
    .digest('hex')
    .slice(0, 16)
}

export function clusterFingerprint(kind: HallucinationKind, members: string[]): string {
  const sorted = [...members].sort().join('|')
  return createHash('sha256').update(`${kind}|cluster|${sorted}`).digest('hex').slice(0, 16)
}
