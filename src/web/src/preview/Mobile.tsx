import { useEffect, useState } from 'react'

/*
 * 발표 화면용 폰 틀(/mobile, 10/13 오너). 사용자 화면(/)을 390×844 폰 틀 안에 띄우고, 창 높이에 맞춰 키우거나 줄인다.
 * 조작 버튼은 두지 않는다 — 시연은 다른 창에서 /?admin=1 진행 막대로 하고, 이 화면은 2초마다 같은 서버를 읽어 따라온다.
 * 시연 도구라 색은 토큰 대신 브랜드 바탕 값을 직접 쓴다(Preview.tsx 와 같은 예외).
 */
const W = 390, H = 844, BORDER = 12, MARGIN = 24

function useFit() {
  const calc = () => Math.min((window.innerHeight - MARGIN * 2) / (H + BORDER * 2), (window.innerWidth - MARGIN * 2) / (W + BORDER * 2))
  const [scale, setScale] = useState(calc)
  useEffect(() => {
    const on = () => setScale(calc())
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return scale
}

export default function Mobile() {
  const scale = useFit()
  useEffect(() => { document.title = '배마중' }, [])
  return (
    <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-[#eef3f2]">
      <div className="shrink-0 overflow-hidden rounded-[52px] border-[12px] border-[#111] bg-white shadow-2xl"
        style={{ width: W + BORDER * 2, height: H + BORDER * 2, transform: `scale(${scale})` }}>
        <iframe src="/" title="배마중 폰 화면" className="block border-0" style={{ width: W, height: H }} />
      </div>
    </div>
  )
}
