import {
  ArrowFunction,
  FunctionDeclaration,
  FunctionExpression,
  MethodDeclaration,
  SyntaxKind,
  Node,
  Statement,
} from 'ts-morph'
import type { TargetContext } from './project.js'
import { relPath } from './project.js'
import type { Hallucination } from './types.js'
import { fingerprint } from './fingerprint.js'

type CallableNode = FunctionDeclaration | FunctionExpression | ArrowFunction | MethodDeclaration

const TODO_RE = /TODO|FIXME|XXX|PLACEHOLDER|stub|not\s*implemented/i
const EMPTY_RETURN = new Set(['null', 'undefined', '{}', '[]', 'void 0', 'true', 'false', "''", '""'])

/**
 * H3 — Hollow Stub
 * Detects function-like declarations whose body is effectively empty:
 *   - ≤ 2 statements, AND
 *   - returns constant falsy / literal, OR
 *   - only throws "not implemented"-style error, OR
 *   - only TODO/FIXME comment
 */
export function detectHollowStubs(ctx: TargetContext): Hallucination[] {
  const out: Hallucination[] = []
  for (const sf of ctx.project.getSourceFiles()) {
    if (sf.getFilePath().includes('node_modules')) continue
    sf.forEachDescendant((node) => {
      if (isCallable(node) && isHollow(node)) {
        const file = relPath(ctx, sf.getFilePath())
        const line = node.getStartLineNumber()
        const symbol = callableName(node)
        out.push({
          id: fingerprint('H3', file, line, symbol ?? ''),
          kind: 'H3',
          severity: 'warn',
          file,
          line,
          endLine: node.getEndLineNumber(),
          symbol,
          message: `빈 껍데기 구현: ${symbol ?? '<anonymous>'}`,
          evidence: {
            symbol,
            bodySnippet: (node.getBody()?.getText() ?? '').slice(0, 240),
            file,
            line,
          },
        })
      }
      // return undefined — forEachDescendant stops if callback returns truthy
    })
  }
  return out
}

function isCallable(node: Node): node is CallableNode {
  return (
    Node.isFunctionDeclaration(node) ||
    Node.isFunctionExpression(node) ||
    Node.isArrowFunction(node) ||
    Node.isMethodDeclaration(node)
  )
}

function callableName(node: CallableNode): string | undefined {
  if (Node.isFunctionDeclaration(node) || Node.isMethodDeclaration(node)) {
    return node.getName()
  }
  const parent = node.getParent()
  if (parent && Node.isVariableDeclaration(parent)) return parent.getName()
  if (parent && Node.isPropertyAssignment(parent)) return parent.getName()
  return undefined
}

function isHollow(node: CallableNode): boolean {
  const body = node.getBody()
  if (!body) return false
  if (!Node.isBlock(body)) {
    // Arrow with expression body: `() => null`
    const text = body.getText().trim()
    if (EMPTY_RETURN.has(text)) return true
    return false
  }

  const statements = body.getStatements()
  if (statements.length === 0) return true
  if (statements.length > 2) return false

  const bodyText = body.getText()
  if (TODO_RE.test(bodyText)) return true

  for (const stmt of statements) {
    if (isReturnEmpty(stmt)) return true
    if (isThrowNotImplemented(stmt)) return true
  }
  return false
}

function isReturnEmpty(stmt: Statement): boolean {
  if (!Node.isReturnStatement(stmt)) return false
  const expr = stmt.getExpression()
  if (!expr) return true
  const text = expr.getText().trim()
  return EMPTY_RETURN.has(text)
}

function isThrowNotImplemented(stmt: Statement): boolean {
  if (!Node.isThrowStatement(stmt)) return false
  const expr = stmt.getExpression()
  if (!expr) return false
  const text = expr.getText()
  return /not\s*implemented|TODO|stub|unimplemented/i.test(text)
}

// Re-export SyntaxKind for test utilities that may want it.
export { SyntaxKind }
