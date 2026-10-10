import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 개발: 화면은 5173, API는 FastAPI(8000)로 넘긴다. 배포: FastAPI가 dist/를 정적 서빙.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 저장소 루트 .env 를 읽는다. 화면에 들어가는 건 VITE_ 로 시작하는 값뿐(카카오맵 JavaScript 키 등 공개 키만).
  envDir: '../..',
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
})
