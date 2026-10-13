import { useEffect, useState } from 'react'
import type { Clock, Ship, Source, Today } from '../api'

/*
 * 발표 시연(/demo, 10/13 오너): 부모 창이 서버를 한 번 읽어 폰·웹 화면에 같은 값을 같은 순간 보낸다.
 * 화면은 주소에 ?feed=parent 가 있고 iframe 안일 때만 이 값을 쓰고, 시각·입항·배 위치를 직접 조회하지 않는다.
 * 그래야 두 화면의 시계·남은 분·배 위치가 어긋나지 않는다. 같은 출처(origin)에서 온 메시지만 받는다.
 */
export type Feed = {
  type: 'bmj-feed'
  today: Today
  ships: { clock: Clock; source: Source; ships: Ship[] }
  inbox: { vts: string; title: string; body: string }[]
  at: number // 부모가 서버 값을 받은 때(Date.now). 두 화면이 같은 기준으로 시계를 굴린다
}

export const FED = new URLSearchParams(location.search).get('feed') === 'parent' && window.self !== window.top

export function useParentFeed() {
  const [feed, setFeed] = useState<Feed | null>(null)
  useEffect(() => {
    if (!FED) return
    const on = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.source !== window.parent) return
      const d = e.data as Feed | null
      if (d?.type === 'bmj-feed') setFeed(d)
    }
    window.addEventListener('message', on)
    window.parent.postMessage({ type: 'bmj-feed-ready' }, location.origin) // 늦게 뜬 화면도 바로 마지막 값을 받게
    return () => window.removeEventListener('message', on)
  }, [])
  return feed
}
