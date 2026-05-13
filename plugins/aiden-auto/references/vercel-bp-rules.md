# Vercel Best Practices 검증 규칙

Phase 4 Step 4.2에서 code-reviewer teammate prompt에 동적 주입하는 규칙.

> 주입 시 이 파일의 전체 내용을 Read하여 code-reviewer prompt에 포함.

## 규칙 목록

```
=== Vercel Best Practices 검증 규칙 ===

[React 성능]
- useMemo/useCallback: 실제 re-render 비용이 높은 경우에만 사용. 과도한 메모이제이션 지양.
- key prop: 배열 렌더링 시 안정적 key 사용 (index 금지).
- lazy loading: 큰 컴포넌트는 React.lazy + Suspense.
- state 최소화: 파생 가능한 값은 state 대신 계산.

[Next.js 패턴]
- App Router 우선: pages/ 대신 app/ 디렉토리 사용.
- Server Component 기본: 'use client' 최소화. 인터랙티브 부분만 Client.
- Metadata API: generateMetadata 사용, <Head> 지양.
- Image 최적화: next/image 필수, width/height 명시.
- Font 최적화: next/font 사용, FOUT/FOIT 방지.

[접근성]
- 모든 인터랙티브 요소에 aria-label 또는 accessible name.
- Semantic HTML: div 남용 대신 nav, main, section, article, aside.
- 키보드 네비게이션: 모든 기능이 Tab/Enter로 접근 가능.
- 색상 대비: WCAG 2.1 AA 기준 (4.5:1 이상).

[보안]
- dangerouslySetInnerHTML 사용 시 sanitize 필수.
- 환경 변수: NEXT_PUBLIC_ prefix 없이 서버 전용 비밀 유지.
- CSP 헤더: next.config.js에 Content-Security-Policy 설정.

[성능]
- Bundle size: dynamic import로 코드 분할.
- API Route: Edge Runtime 우선 (해당 시).
- Caching: ISR/SSG 우선, SSR은 필요한 경우만.
```
