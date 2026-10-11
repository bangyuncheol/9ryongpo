import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.tsx'
import AppV2 from './v2/AppV2.tsx'

// 2차 시안은 ?v=2 로만 연다(10/11). 기본 화면은 그대로.
const v2 = new URLSearchParams(location.search).get('v') === '2'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {v2 ? <AppV2 /> : <App />}
  </StrictMode>,
)
