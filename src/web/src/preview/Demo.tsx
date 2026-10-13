import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Feed } from '../v4/feed'

/*
 * 발표 화면용 시연 틀(/demo, 10/13 오너). 왼쪽 폰(390×844) · 오른쪽 웹(1440×900)에 같은 사용자 화면(/)을 띄우고,
 * 둘을 같은 높이로 맞춰 창 크기에 따라 키우거나 줄인다. 조작 버튼은 두지 않는다 — 시연은 다른 창에서 /?admin=1 진행 막대로 한다.
 * 이 창이 1초마다 서버를 한 번 읽어 두 화면에 같은 값을 같은 순간 보낸다(10/13 오너: 폰·웹 시계를 같게, v4/feed.ts).
 * 시연 도구라 색은 토큰 대신 브랜드 바탕 값을 직접 쓴다(Preview.tsx 와 같은 예외).
 */
const PW = 390, PH = 844, BORDER = 12 // 폰 화면과 틀 두께
const WW = 1440, WH = 900, BAR = 36 // 웹 화면과 창 윗줄
const GAP = 40, MARGIN = 32

const phoneW = PW + BORDER * 2, phoneH = PH + BORDER * 2
const webH = WH + BAR

/** 두 틀을 같은 높이 h 로: 폭 합 = h·(폰 비율 + 웹 비율) + 사이 여백 */
function useHeight() {
  const calc = () => Math.min(
    window.innerHeight - MARGIN * 2,
    (window.innerWidth - MARGIN * 2 - GAP) / (phoneW / phoneH + WW / webH),
  )
  const [h, setH] = useState(calc)
  useEffect(() => {
    const on = () => setH(calc())
    window.addEventListener('resize', on)
    return () => window.removeEventListener('resize', on)
  }, [])
  return Math.max(200, h)
}

/** 서버를 1초마다 한 번 읽어 두 화면(iframe)에 같은 값을 보낸다. 화면이 새로 뜨면(ready) 마지막 값을 바로 준다. */
function useBroadcast() {
  const last = useRef<Feed | null>(null)
  useEffect(() => {
    const send = (to?: Window | null) => {
      const f = last.current
      if (!f) return
      const targets = to ? [to] : [...document.querySelectorAll('iframe')].map((x) => x.contentWindow)
      targets.forEach((w) => w?.postMessage(f, location.origin))
    }
    let alive = true, busy = false, n = 0, inbox: Feed['inbox'] = []
    const run = async () => {
      if (busy) return // 앞 요청이 늦으면 건너뛴다(쌓이지 않게)
      busy = true
      try {
        const [today, ships] = await Promise.all([api.today(), api.ships()])
        if (n++ % 3 === 0) inbox = await api.notifications().catch(() => inbox) // 알림함은 3초마다
        if (!alive) return
        last.current = { type: 'bmj-feed', today, ships, inbox, at: Date.now() }
        send()
      } catch (e) { console.error(e) } finally { busy = false }
    }
    const onMsg = (e: MessageEvent) => {
      if (e.origin === location.origin && (e.data as { type?: string } | null)?.type === 'bmj-feed-ready') send(e.source as Window)
    }
    window.addEventListener('message', onMsg)
    run()
    const id = setInterval(run, 1000)
    const onShow = () => { if (document.visibilityState === 'visible') run() }
    document.addEventListener('visibilitychange', onShow)
    return () => { alive = false; clearInterval(id); window.removeEventListener('message', onMsg); document.removeEventListener('visibilitychange', onShow) }
  }, [])
}

export default function Demo() {
  useBroadcast()
  const h = useHeight()
  const ps = h / phoneH, ws = h / webH
  useEffect(() => { document.title = '배마중' }, [])
  return (
    <div className="fixed inset-0 flex items-center justify-center overflow-hidden bg-[#eef3f2]" style={{ gap: GAP }}>
      <div className="shrink-0" style={{ width: phoneW * ps, height: h }}>
        <div className="origin-top-left overflow-hidden rounded-[52px] border-[12px] border-[#111] bg-white shadow-2xl"
          style={{ width: phoneW, height: phoneH, transform: `scale(${ps})` }}>
          <iframe src="/?feed=parent" title="배마중 폰 화면" className="block border-0" style={{ width: PW, height: PH }} />
        </div>
      </div>
      <div className="shrink-0" style={{ width: WW * ws, height: h }}>
        <div className="origin-top-left overflow-hidden rounded-2xl bg-white shadow-2xl" style={{ width: WW, height: webH, transform: `scale(${ws})` }}>
          <div aria-hidden className="flex items-center gap-2 bg-[#e3e8e7] px-4" style={{ height: BAR }}>
            <span className="h-3 w-3 rounded-full bg-[#ff5f57]" /><span className="h-3 w-3 rounded-full bg-[#febc2e]" /><span className="h-3 w-3 rounded-full bg-[#28c840]" />
            <span className="ml-4 rounded-md bg-white px-4 py-0.5 text-[14px] text-[#4f6169]">bmj.kr</span>
          </div>
          <iframe src="/?feed=parent" title="배마중 웹 화면" className="block border-0" style={{ width: WW, height: WH }} />
        </div>
      </div>
    </div>
  )
}
