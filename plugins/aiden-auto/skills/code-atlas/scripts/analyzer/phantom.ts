import { ImportDeclaration, SourceFile } from 'ts-morph'
import type { TargetContext } from './project.js'
import { relPath } from './project.js'
import type { Hallucination } from './types.js'
import { fingerprint } from './fingerprint.js'

/**
 * H1 — Phantom Reference
 * Detects import declarations whose module cannot be resolved by the TS compiler.
 * Uses ts-morph's built-in symbol resolution via the TypeScript language service.
 */
export function detectPhantomRefs(ctx: TargetContext): Hallucination[] {
  const out: Hallucination[] = []

  for (const sf of ctx.project.getSourceFiles()) {
    if (sf.getFilePath().includes('node_modules')) continue
    for (const imp of sf.getImportDeclarations()) {
      const result = checkImport(sf, imp, ctx)
      if (result) out.push(result)
    }
  }

  return out
}

// Assets that ts-morph cannot resolve (they're not TS/JS). Handled by bundler,
// not the TS compiler — skip to avoid false positives.
const ASSET_EXTENSIONS = /\.(css|scss|sass|less|json|svg|png|jpg|jpeg|gif|webp|avif|ico|ttf|woff2?|eot|mp4|webm|mp3|wav|pdf|md|txt|yaml|yml|toml)$/i

function checkImport(
  sf: SourceFile,
  imp: ImportDeclaration,
  ctx: TargetContext,
): Hallucination | null {
  const moduleSpec = imp.getModuleSpecifierValue()
  if (!moduleSpec) return null

  // Skip node builtins, bare npm modules (they're handled by type resolution separately;
  // we flag only relative/alias imports that clearly cannot resolve to a file).
  const isRelative = moduleSpec.startsWith('.') || moduleSpec.startsWith('/')
  const isAlias = moduleSpec.startsWith('@/') || moduleSpec.startsWith('~/')
  if (!isRelative && !isAlias) return null

  // Skip asset imports — they resolve through the bundler, not TypeScript.
  if (ASSET_EXTENSIONS.test(moduleSpec)) return null

  const resolved = imp.getModuleSpecifierSourceFile()
  if (resolved) return null

  const file = relPath(ctx, sf.getFilePath())
  const line = imp.getStartLineNumber()
  const id = fingerprint('H1', file, line, moduleSpec)

  return {
    id,
    kind: 'H1',
    severity: 'critical',
    file,
    line,
    message: `존재하지 않는 모듈: ${moduleSpec}`,
    evidence: {
      claimedPath: moduleSpec,
      callerFile: file,
      callerLine: line,
      callerSnippet: imp.getText().trim(),
      resolved: null,
    },
  }
}
