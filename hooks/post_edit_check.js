#!/usr/bin/env node
/**
 * PostToolUse Hook - 파일 수정 후 TDD 피드백 제공
 * Edit/Write 도구 실행 후 자동으로 린트 및 테스트 실행
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const PROJECT_DIR = process.env.CLAUDE_PROJECT_DIR || 'C:/claude';

const FATIGUE_LOG = path.join(PROJECT_DIR, '.claude', 'logs', 'fatigue_signals.jsonl');
const BURST_WINDOW_MS = 5 * 60 * 1000;  // 5분
const BURST_THRESHOLD = 3;               // 3회

function recordEditSignal(filePath) {
  try {
    const logsDir = path.dirname(FATIGUE_LOG);
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }
    const now = Date.now();
    const entry = JSON.stringify({ file: filePath, ts: now, type: 'edit' }) + '\n';
    fs.appendFileSync(FATIGUE_LOG, entry, 'utf8');

    // edit_burst 감지: 동일 파일 5분 내 3회+
    const content = fs.readFileSync(FATIGUE_LOG, 'utf8');
    const lines = content.trim().split('\n').filter(Boolean);
    const recent = lines
      .map(l => { try { return JSON.parse(l); } catch { return null; } })
      .filter(e => e && e.file === filePath && e.type === 'edit' && (now - e.ts) < BURST_WINDOW_MS);

    if (recent.length >= BURST_THRESHOLD) {
      const burst = JSON.stringify({ file: filePath, ts: now, type: 'edit_burst', count: recent.length }) + '\n';
      fs.appendFileSync(FATIGUE_LOG, burst, 'utf8');
    }
  } catch (e) {
    // 조용히 무시
  }
}

/**
 * 파일 경로에서 확장자 확인
 */
function getFileExtension(filePath) {
  return path.extname(filePath).toLowerCase();
}

/**
 * 건너뛸 경로인지 확인 (node_modules, .git 등)
 */
function shouldSkipPath(filePath) {
  const skipPatterns = [
    /node_modules/i,
    /\.git\//i,
    /\.venv/i,
    /dist\//i,
    /build\//i,
    /__pycache__/i,
    /\.pytest_cache/i,
    /\.omc\//i,
    /\.pyc$/i,
    /\.min\./i,
    /package-lock\.json$/i,
    /yarn\.lock$/i,
  ];

  return skipPatterns.some(pattern => pattern.test(filePath));
}

/**
 * Python 파일 관련 테스트 파일 찾기
 * src/foo/bar.py -> tests/test_bar.py 또는 tests/foo/test_bar.py
 */
function findPythonTestFile(sourceFile) {
  const normalized = sourceFile.replace(/\\/g, '/');
  const basename = path.basename(sourceFile, '.py');

  // src/ 제거
  const withoutSrc = normalized.replace(/^.*?src\//, '');
  const dirPart = path.dirname(withoutSrc);

  // 소스 파일의 부모 디렉토리 추출 (예: src/agents/config.py → src/agents)
  const sourceDir = path.dirname(normalized);

  const candidates = [
    path.join(PROJECT_DIR, 'tests', `test_${basename}.py`),
    path.join(PROJECT_DIR, 'tests', dirPart, `test_${basename}.py`),
    path.join(PROJECT_DIR, 'tests', 'unit', `test_${basename}.py`),
    path.join(sourceDir, 'tests', `test_${basename}.py`),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return null;
}

/**
 * 명령 실행 with timeout (execFileSync로 command injection 방지)
 */
function runCommand(executable, args, timeoutSec = 30) {
  try {
    const result = execFileSync(executable, args, {
      cwd: PROJECT_DIR,
      timeout: timeoutSec * 1000,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return { success: true, output: result };
  } catch (error) {
    return {
      success: false,
      output: error.stdout || error.stderr || error.message
    };
  }
}

/**
 * Python 파일 처리
 */
function handlePythonFile(filePath) {
  const messages = [];

  // 1. Ruff 린트 실행 (진단 전용, --fix 없음 → Claude 내부 상태와 파일 불일치 방지)
  const lintResult = runCommand('ruff', ['check', filePath], 10);
  if (!lintResult.success) {
    messages.push(`⚠️ Ruff: ${lintResult.output.slice(0, 150).split('\n')[0]}`);
  }

  // 2. 테스트 파일 찾기 및 실행
  const testFile = findPythonTestFile(filePath);
  if (testFile) {
    const testResult = runCommand('pytest', [testFile, '-v', '--timeout=30', '--tb=short'], 30);
    if (!testResult.success) {
      messages.push(`❌ FAIL: ${path.basename(testFile)} ${testResult.output.slice(0, 200).split('\n').slice(-3).join(' | ')}`);
    }
  }

  return messages;
}

/**
 * TypeScript/JavaScript 파일 처리
 */
function handleTypeScriptFile(filePath) {
  return [];  // TS 파일은 lint 메시지 생략 (context 절약)
}

/**
 * HTML UI 파일 변경 감지 — 캡쳐+삽입 자동 안내
 * 반복 프롬프트 분석(2026-03-25): "캡쳐하여 삽입" 4회 반복 해소
 */
function handleHtmlFile(filePath) {
  const messages = [];
  const normalizedPath = filePath.replace(/\\/g, '/');

  if (normalizedPath.includes('/docs/') && normalizedPath.endsWith('.html')) {
    messages.push('📸 HTML UI 변경 감지. 캡쳐 필요 시 `--anno` 옵션 사용 (배치: `--anno 디렉토리`)');
  }
  return messages;
}

/**
 * Mermaid 블록 내 \n 리터럴 자동 수정
 * 노드 레이블의 \n 리터럴을 <br/>로 자동 교체 (GitHub/VS Code 호환성)
 */
function fixMermaidNewlines(filePath) {
  const messages = [];
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    let totalFixed = 0;

    const fixedContent = content.replace(
      /(```mermaid\r?\n)([\s\S]*?)(```)/g,
      (match, prefix, block, suffix) => {
        const fixedBlock = block.replace(
          /"[^"]*\\n[^"]*"/g,
          (label) => {
            const fixed = label.replace(/\\n/g, '<br/>');
            if (fixed !== label) {
              totalFixed += (label.match(/\\n/g) || []).length;
            }
            return fixed;
          }
        );
        return prefix + fixedBlock + suffix;
      }
    );

    if (totalFixed > 0) {
      fs.writeFileSync(filePath, fixedContent, 'utf8');
      messages.push(`🔧 Mermaid 자동수정: ${totalFixed}개 \\n → <br/> 교체됨`);
    }
  } catch (e) {
    // 조용히 무시
  }
  return messages;
}

/**
 * SKILL.md / REFERENCE.md freshness 검증
 * 내용 변경 시 version 필드 업데이트 여부 확인
 */
function checkDocFreshness(filePath) {
  const messages = [];
  try {
    const normalizedPath = filePath.replace(/\\/g, '/');
    const basename = path.basename(normalizedPath);

    // SKILL.md 또는 REFERENCE.md만 대상
    if (basename !== 'SKILL.md' && basename !== 'REFERENCE.md') {
      return messages;
    }

    // git diff로 version 필드 변경 여부 확인
    const diffResult = runCommand('git', ['diff', '--cached', '--', filePath], 5);
    const unstaged = runCommand('git', ['diff', '--', filePath], 5);
    const diff = (diffResult.output || '') + (unstaged.output || '');

    if (!diff.trim()) {
      return messages;  // 변경 없음
    }

    // 내용 변경이 있지만 version 변경이 없는 경우 경고
    const hasVersionChange = /^[+-]version:/m.test(diff);
    const hasContentChange = diff.split('\n').filter(
      l => (l.startsWith('+') || l.startsWith('-')) &&
           !l.startsWith('+++') && !l.startsWith('---') &&
           !/^[+-]version:/m.test(l) &&
           !/^[+-]Last Updated/m.test(l)
    ).length > 2;  // 사소한 변경(2줄 이하)은 무시

    if (hasContentChange && !hasVersionChange) {
      messages.push(`⚠️ ${basename} 내용 변경 감지 — version 필드 업데이트 필요`);
    }
  } catch (e) {
    // 조용히 무시
  }
  return messages;
}

/**
 * Markdown 이미지 링크 유효성 검증
 * 반복 프롬프트 분석(2026-03-25): 이미지 링크 깨짐 3회 반복 해소
 */
function checkImageLinks(filePath) {
  const messages = [];
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const imgPattern = /!\[([^\]]*)\]\(([^)]+)\)/g;
    let match;
    const broken = [];
    const fileDir = path.dirname(filePath);

    while ((match = imgPattern.exec(content)) !== null) {
      const imgPath = match[2];
      if (imgPath.startsWith('http')) continue;
      const resolved = path.resolve(fileDir, imgPath);
      if (!fs.existsSync(resolved)) {
        broken.push(path.basename(imgPath));
      }
    }
    if (broken.length > 0) {
      messages.push(`⚠️ 깨진 이미지 링크 ${broken.length}개: ${broken.slice(0, 3).join(', ')}${broken.length > 3 ? '...' : ''}`);
    }
  } catch (e) {
    // 조용히 무시
  }
  return messages;
}

/**
 * Markdown 파일 처리
 */
function handleMarkdownFile(filePath) {
  const mermaidMessages = fixMermaidNewlines(filePath);
  const freshnessMessages = checkDocFreshness(filePath);
  const imgMessages = checkImageLinks(filePath);
  return mermaidMessages.concat(freshnessMessages).concat(imgMessages);
}

/**
 * 메인 로직
 */
function main() {
  let rawInput = '';
  try {
    rawInput = fs.readFileSync(0, 'utf8');
  } catch (e) {
    return;
  }

  if (!rawInput.trim()) {
    return;
  }

  try {
    const data = JSON.parse(rawInput);
    const toolName = data.tool_name || '';
    const toolInput = data.tool_input || {};

    // Phase 인식: CURRENT_PHASE 환경변수 또는 상태 파일 기반
    const currentPhase = process.env.CURRENT_PHASE || (() => {
      try {
        const stateFile = path.join(PROJECT_DIR, '.claude', 'hooks', '.current_phase');
        return fs.readFileSync(stateFile, 'utf8').trim();
      } catch { return ''; }
    })();

    // Phase 0(INIT) 또는 1(PLAN) 중에는 린트/테스트 스킵 (Mermaid 자동수정만 실행)
    const skipLintAndTest = currentPhase === '0' || currentPhase === '1';

    // MCP 프로파일링: mcp__ 접두사 도구 호출 시 로깅
    if (toolName.startsWith('mcp__')) {
      try {
        const mcpLogDir = path.join(PROJECT_DIR, '.claude', 'logs');
        if (!fs.existsSync(mcpLogDir)) fs.mkdirSync(mcpLogDir, { recursive: true });
        const mcpLogPath = path.join(mcpLogDir, 'mcp_profile.jsonl');
        const mcpEntry = JSON.stringify({
          tool: toolName,
          ts: Date.now(),
          session: process.env.CLAUDE_SESSION_ID || 'unknown'
        }) + '\n';
        fs.appendFileSync(mcpLogPath, mcpEntry, 'utf8');
      } catch (e) { /* 조용히 무시 */ }
    }

    // Edit 또는 Write 도구만 처리
    if (toolName !== 'Edit' && toolName !== 'Write') {
      return;
    }

    const filePath = toolInput.file_path || '';

    // 파일 경로 없음 또는 건너뛸 경로
    if (!filePath || shouldSkipPath(filePath)) {
      return;
    }

    recordEditSignal(filePath);

    const ext = getFileExtension(filePath);
    let messages = [];

    // Workflow 파일 변경 감지 경고
    const normalizedPath = filePath.replace(/\\/g, '/');
    if (normalizedPath.includes('.claude/skills/auto/SKILL.md') ||
        normalizedPath.includes('.claude/skills/auto/REFERENCE.md')) {
      messages.push('⚠️ Workflow 핵심 파일 변경 감지. /check --workflow 실행 권장');
    }

    if (ext === '.py') {
      if (!skipLintAndTest) {
        messages = messages.concat(handlePythonFile(filePath));
      }
    } else if (['.ts', '.tsx', '.js', '.jsx'].includes(ext)) {
      messages = handleTypeScriptFile(filePath);
    } else if (ext === '.md') {
      messages = handleMarkdownFile(filePath);
    } else if (ext === '.html') {
      messages = handleHtmlFile(filePath);
    }

    // 메시지가 있으면 출력 (context 절약: 300자 하드캡)
    if (messages.length > 0) {
      const output = messages.join(' | ').slice(0, 300);
      console.log(JSON.stringify({ message: output }));
    }

  } catch (e) {
    // 에러 발생 시 조용히 무시 (PostToolUse는 차단 불가)
  }
}

main();
