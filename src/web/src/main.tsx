import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './index.css'
import AppV4 from './v4/AppV4.tsx'
import Preview from './preview/Preview.tsx'
import Demo from './preview/Demo.tsx'

// 화면은 버전 4 하나(10/12 정리). 주소로 나눈다:
//   /            사용자 화면(시연 조작 없음). 예전 링크 ?v=2·3·4 도 같은 화면
//   /?admin=1    시연 진행 막대·통화 내역이 붙은 화면(우리용)
//   /?preview=1  폰·웹 틀 + 시연 패널(발표 노트북용). iframe 안에서는 다시 미리보기를 띄우지 않는다
//   /demo        발표 화면용: 왼쪽 폰 · 오른쪽 웹을 나란히(조작 없음). 시연은 다른 창의 /?admin=1 에서 — 같은 서버 시계라 둘 다 따라 움직인다(10/13)
const q = new URLSearchParams(location.search)
const top = window.self === window.top
const preview = q.has('preview') && top
const demo = location.pathname.replace(/\/$/, '') === '/demo' && top

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {demo ? <Demo /> : preview ? <Preview /> : <AppV4 />}
  </StrictMode>,
)
