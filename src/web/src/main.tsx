import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.tsx'
import AppV2 from './v2/AppV2.tsx'
import AppV3 from './v3/AppV3.tsx'
import Preview from './preview/Preview.tsx'

// 2차 시안은 ?v=2 로만 연다(10/11). 기본 화면은 그대로.
const q = new URLSearchParams(location.search)
const v = q.get('v') // 시안: 2 = 긴 한 페이지, 3 = 웹은 2와 같고 폰만 홈+탭(10/11)
// 팀 내부 미리보기(?preview=1): 폰·웹 × 버전 1·2 를 한 화면에서. iframe 안에서는 다시 미리보기를 띄우지 않는다
const preview = q.has('preview') && window.self === window.top

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {preview ? <Preview /> : v === '3' ? <AppV3 /> : v === '2' ? <AppV2 /> : <App />}
  </StrictMode>,
)
