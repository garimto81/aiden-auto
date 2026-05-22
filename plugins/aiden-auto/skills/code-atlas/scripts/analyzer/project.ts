import { Project, ts } from 'ts-morph'
import { existsSync, readdirSync, statSync } from 'node:fs'
import { resolve, join, sep } from 'node:path'

export interface TargetContext {
  rootDir: string
  project: Project
  hasNextJs: boolean
  srcFiles: string[]
  /** tsconfig 가 하나라도 발견된 경우 true */
  hasTsConfig: boolean
  /** monorepo 구조에서 발견된 모든 tsconfig 절대 경로 */
  tsConfigs: string[]
}

const IGNORED_DIRS = new Set([
  'node_modules',
  '.git',
  'dist',
  'build',
  '.next',
  '.nuxt',
  '.output',
  '.svelte-kit',
  '.turbo',
  '.cache',
  '.code-atlas',
  'coverage',
  '.vercel',
])

/**
 * Recursively find tsconfig.json / jsconfig.json up to a depth limit.
 * Handles monorepos (team1, packages, apps subdirectories) without
 * relying on a root-level tsconfig.
 */
function findConfigs(root: string, maxDepth = 4): string[] {
  const out: string[] = []
  function walk(dir: string, depth: number) {
    if (depth > maxDepth) return
    let entries: string[]
    try {
      entries = readdirSync(dir)
    } catch {
      return
    }
    for (const name of entries) {
      if (IGNORED_DIRS.has(name)) continue
      const full = join(dir, name)
      let st
      try {
        st = statSync(full)
      } catch {
        continue
      }
      if (st.isDirectory()) {
        walk(full, depth + 1)
      } else if (name === 'tsconfig.json' || name === 'jsconfig.json') {
        out.push(full)
      }
    }
  }
  walk(root, 0)
  return out
}

function detectNextJs(absRoot: string, tsConfigs: string[]): boolean {
  const candidates: string[] = []
  const roots = new Set<string>([absRoot, ...tsConfigs.map((p) => p.replace(/[\\/](ts|js)config\.json$/, ''))])
  for (const r of roots) {
    for (const ext of ['js', 'mjs', 'ts']) {
      candidates.push(join(r, `next.config.${ext}`))
    }
  }
  return candidates.some((p) => existsSync(p))
}

export function loadTargetProject(rootDir: string): TargetContext {
  const absRoot = resolve(rootDir)
  if (!existsSync(absRoot)) throw new Error(`Target directory not found: ${absRoot}`)

  const tsConfigs = findConfigs(absRoot)
  const rootTsConfig = tsConfigs.find((p) => {
    const parent = p.split(sep).slice(0, -1).join(sep)
    return parent === absRoot
  })
  const primaryConfig = rootTsConfig ?? tsConfigs[0]

  const project = new Project({
    tsConfigFilePath: primaryConfig,
    compilerOptions: primaryConfig
      ? undefined
      : {
          allowJs: true,
          jsx: ts.JsxEmit.ReactJSX,
          target: ts.ScriptTarget.ES2022,
          module: ts.ModuleKind.ESNext,
          moduleResolution: ts.ModuleResolutionKind.Bundler,
          strict: false,
        },
    skipAddingFilesFromTsConfig: false,
  })

  // Additional tsconfigs in a monorepo: load their source files too.
  for (const cfg of tsConfigs) {
    if (cfg === primaryConfig) continue
    try {
      project.addSourceFilesFromTsConfig(cfg)
    } catch {
      // ignore individual config failures (malformed tsconfig, circular refs, etc.)
    }
  }

  // If no config at all, fall back to globbing the whole tree.
  if (!primaryConfig) {
    const includeGlob = join(absRoot, '**', '*.{ts,tsx,js,jsx,mjs,cjs}').replace(/\\/g, '/')
    const excludes = [...IGNORED_DIRS].map((d) => `!${join(absRoot, '**', d, '**').replace(/\\/g, '/')}`)
    project.addSourceFilesAtPaths([includeGlob, ...excludes])
  }

  const srcFiles = project
    .getSourceFiles()
    .filter((sf) => !sf.getFilePath().includes('node_modules'))
    .map((sf) => sf.getFilePath())

  const hasNextJs = detectNextJs(absRoot, tsConfigs)

  return {
    rootDir: absRoot,
    project,
    hasNextJs,
    srcFiles,
    hasTsConfig: tsConfigs.length > 0,
    tsConfigs,
  }
}

export function relPath(ctx: TargetContext, absPath: string): string {
  return absPath.replace(ctx.rootDir + '\\', '').replace(ctx.rootDir + '/', '').replace(/\\/g, '/')
}
