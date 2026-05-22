/**
 * Maps technical code names to human-readable Korean labels so non-developers
 * can read the Atlas diagram without knowing TypeScript. Keeps the original
 * name in `originalName` for tooltip / detail panel.
 */

const PAGE_DICT: Record<string, string> = {
  login: '로그인 화면',
  signin: '로그인 화면',
  signup: '회원가입 화면',
  register: '회원가입 화면',
  home: '홈 화면',
  index: '홈 화면',
  dashboard: '대시보드',
  profile: '프로필 화면',
  account: '계정 화면',
  settings: '설정 화면',
  payment: '결제 화면',
  checkout: '결제 화면',
  order: '주문 화면',
  orders: '주문 목록',
  cart: '장바구니',
  product: '상품 화면',
  products: '상품 목록',
  search: '검색 화면',
  analytics: '분석 화면',
  admin: '관리자 화면',
  atlas: 'Atlas 화면',
  visualization: '시각화 화면',
  callback: '인증 콜백',
}

const FN_DICT: Record<string, string> = {
  useauth: '로그인 훅',
  requireauth: '로그인 확인',
  getuser: '사용자 가져오기',
  getusers: '사용자 목록',
  getsession: '세션 가져오기',
  signin: '로그인 실행',
  signout: '로그아웃 실행',
  processpayment: '결제 처리',
  handlesubmit: '폼 제출',
  handleclick: '클릭 처리',
  handlechange: '입력 변경',
  usercard: '사용자 카드',
  customercard: '고객 카드',
  profilecard: '프로필 카드',
  ordercard: '주문 카드',
  header: '헤더',
  footer: '푸터',
  navigation: '내비게이션',
  sidebar: '사이드바',
  modal: '모달',
  dialog: '다이얼로그',
  form: '입력 폼',
  table: '표',
  chart: '차트',
  button: '버튼',
  navbar: '내비게이션 바',
  // Code-analysis specific terms (project_master 도메인)
  analyzesourcecode: '코드 분석',
  analyzesourcefile: '파일 분석',
  analyzemultiplefiles: '여러 파일 분석',
  analyzecallgraph: '호출 흐름 분석',
  analyzeerrorpropagation: '에러 전파 분석',
  analyzedataflow: '데이터 흐름 분석',
  analyzedataflowfromfiles: '파일 데이터 흐름 분석',
  analyzedataflowfromcontent: '내용 데이터 흐름 분석',
  analyzewithskott: 'Skott 으로 분석',
  analyzeimpact: '영향도 분석',
  tracedataflow: '데이터 흐름 추적',
  traceerrorpropagation: '에러 전파 추적',
  generatecallgraphmermaid: '호출 흐름 다이어그램 만들기',
  generateprompt: '프롬프트 만들기',
  generatesequenceflow: '시퀀스 흐름 만들기',
  extractcodeblocks: '코드 블록 추출',
  extractfirstcodeblock: '첫 코드 블록 추출',
  applylayerstyles: '레이어 스타일 적용',
  copytoclipboard: '클립보드 복사',
  isreactcomponent: 'React 컴포넌트 판별',
  iscustomhook: '커스텀 훅 판별',
  isapiroutehandler: 'API 라우트 판별',
  inferlayerfrompath: '경로로 레이어 추론',
  maptouserfeatures: '사용자 기능 매핑',
  interactiveflowdiagram: '인터랙티브 흐름 다이어그램',
  mermaiddiagram: 'Mermaid 다이어그램',
  rootlayout: '최상위 레이아웃',
  homepage: '홈 화면',
  loginpage: '로그인 화면',
  logicflowviewer: '로직 흐름 뷰어',
  problemanalyzer: '문제 분석기',
  solutiondirector: '해결안 안내자',
  airedirectmodal: 'AI 연결 모달',
  openaiservice: 'AI 서비스 시작',
  githubgraphql: 'GitHub GraphQL',
  aiservice: 'AI 서비스',
  atlasskeleton: 'Atlas 뼈대',
  atlaspage: 'Atlas 화면',
}

const API_DICT: Record<string, string> = {
  auth: '인증 API',
  login: '로그인 API',
  logout: '로그아웃 API',
  signup: '회원가입 API',
  callback: '인증 콜백 API',
  me: '내 정보 API',
  users: '사용자 API',
  payment: '결제 API',
  orders: '주문 API',
  products: '상품 API',
  search: '검색 API',
  health: '헬스체크',
  issues: '이슈 API',
  repositories: '레포 API',
  ai: 'AI 처리 API',
  atlas: 'Atlas API',
  'logic-flow': '코드 분석 API',
}

/** Normalize a raw name for dictionary lookup (camelCase/kebab-case → lowercase). */
function norm(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '')
}

/** Given the file path of a Next.js page (e.g. `src/app/login/page.tsx`),
 *  derive the route segment ("login") and look it up. */
export function labelForScreen(filePath: string): string {
  const match = filePath.match(/\/app\/(.+)\/page\.(tsx|jsx|ts|js)$/)
  let segment = 'index'
  if (match) {
    const parts = match[1].split('/').filter((s) => !s.startsWith('(') && !s.startsWith('[') && s !== 'page')
    segment = parts[parts.length - 1] || 'index'
  } else {
    const m2 = filePath.match(/\/(?:pages|views)\/([^/]+?)(?:\.(tsx|jsx|ts|js|vue))?$/)
    if (m2) segment = m2[1].replace(/Page$|View$/i, '')
  }
  const key = norm(segment)
  return PAGE_DICT[key] ?? prettifyCamel(segment)
}

/** Label for a Next.js API route: `src/app/api/foo/bar/route.ts` → "foo/bar API" */
export function labelForApi(filePath: string): string {
  const m = filePath.match(/\/api\/(.+?)\/route\.(ts|tsx|js|jsx)$/)
  if (!m) return 'API'
  const segments = m[1].split('/')
  const head = norm(segments[0])
  const head2 = norm(segments[0] + '-' + (segments[1] ?? ''))
  const dictHit = API_DICT[head2] ?? API_DICT[head]
  if (dictHit) return dictHit
  return segments.join('/') + ' API'
}

/** Strip common suffixes that add noise for non-developers. */
function stripCosmeticSuffix(name: string): string {
  return name.replace(/Service$/, '').replace(/Helper$/, '').replace(/Utils?$/, '').replace(/Manager$/, '')
}

/** Label for an exported function / component / hook. */
export function labelForSymbol(name: string): string {
  const key = norm(name)
  if (FN_DICT[key]) return FN_DICT[key]

  // Pattern-based fallbacks
  if (/^use[A-Z]/.test(name)) {
    const stripped = name.replace(/^use/, '')
    return `${prettifyCamel(stripped)} 훅`
  }
  if (/^handle[A-Z]/.test(name)) {
    const stripped = name.replace(/^handle/, '')
    return `${prettifyCamel(stripped)} 처리`
  }
  if (/^on[A-Z]/.test(name)) {
    const stripped = name.replace(/^on/, '')
    return `${prettifyCamel(stripped)} 발생 시`
  }
  if (/^get[A-Z]/.test(name)) {
    const stripped = name.replace(/^get/, '')
    return `${prettifyCamel(stripped)} 가져오기`
  }
  if (/^set[A-Z]/.test(name)) {
    const stripped = name.replace(/^set/, '')
    return `${prettifyCamel(stripped)} 저장`
  }
  if (/^save[A-Z]/.test(name)) return `${prettifyCamel(name.replace(/^save/, ''))} 저장`
  if (/^create[A-Z]/.test(name)) return `${prettifyCamel(name.replace(/^create/, ''))} 만들기`
  if (/^delete[A-Z]|^remove[A-Z]/.test(name)) {
    const stripped = name.replace(/^(delete|remove)/, '')
    return `${prettifyCamel(stripped)} 삭제`
  }
  if (/^update[A-Z]/.test(name)) return `${prettifyCamel(name.replace(/^update/, ''))} 수정`
  if (/^fetch[A-Z]/.test(name)) return `${prettifyCamel(name.replace(/^fetch/, ''))} 요청`

  // Capitalized: probably a React component
  if (/^[A-Z]/.test(name)) return prettifyCamel(stripCosmeticSuffix(name))

  return prettifyCamel(stripCosmeticSuffix(name))
}

/** Label for an edge (relationship between nodes). */
export function labelForEdge(kind: 'imports' | 'calls' | 'fetch' | 'query'): string {
  switch (kind) {
    case 'imports':
      return '사용'
    case 'calls':
      return '호출'
    case 'fetch':
      return 'API 부름'
    case 'query':
      return 'DB 에 저장'
  }
}

function prettifyCamel(s: string): string {
  // "UserProfileCard" → "User Profile Card" (for display only; no Korean hit)
  return s
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[-_]/g, ' ')
    .trim()
    .replace(/\s+/g, ' ')
}
