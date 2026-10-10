/** 카카오맵 JavaScript SDK 불러오기(한 번만). 지도 컴포넌트는 KakaoArrivalMap.tsx. */
/* eslint-disable @typescript-eslint/no-explicit-any */
declare global { interface Window { kakao?: any } }

const KEY = import.meta.env.VITE_KAKAO_MAP_KEY
let loading: Promise<any> | null = null

/** SDK를 한 번만 불러온다. 8초 안에 못 불러오면 실패(호출한 쪽이 기존 지도로 돌아감). */
export function loadKakao(): Promise<any> {
  if (!KEY) return Promise.reject(new Error('VITE_KAKAO_MAP_KEY 없음'))
  if (loading) return loading
  loading = new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('카카오맵 SDK 시간 초과')), 8000)
    const done = () => window.kakao!.maps.load(() => { clearTimeout(timer); resolve(window.kakao!) })
    if (window.kakao?.maps) return done()
    const s = document.createElement('script')
    s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false`
    s.async = true
    s.onload = () => (window.kakao?.maps ? done() : reject(new Error('카카오맵 SDK 응답 이상(도메인 등록·사용 설정 확인)')))
    s.onerror = () => { clearTimeout(timer); reject(new Error('카카오맵 SDK를 불러오지 못함')) }
    document.head.appendChild(s)
  })
  loading.catch(() => { loading = null })
  return loading
}
