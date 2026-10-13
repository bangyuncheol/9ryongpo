import { useEffect, useRef, useState } from 'react'

/** 주기 조회. 실패하면 마지막 성공 값을 유지하고 오류 문구만 바꾼다. */
export function usePoll<T>(fn: () => Promise<T>, ms: number, key: unknown = null) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    let alive = true
    const run = async () => {
      try {
        const d = await fnRef.current()
        if (alive) { setData(d); setError(null) }
      } catch (e) {
        console.error(e)
        if (alive) setError(e instanceof Error ? e.message : '알 수 없는 오류가 났습니다.')
      }
    }
    run()
    const id = setInterval(run, ms)
    // 창이 다시 보이면 바로 한 번(가려진 창은 브라우저가 타이머를 늦춘다 — /demo 시연 창, 10/13)
    const onShow = () => { if (document.visibilityState === 'visible') run() }
    document.addEventListener('visibilitychange', onShow)
    return () => { alive = false; clearInterval(id); document.removeEventListener('visibilitychange', onShow) }
  }, [ms, key])
  return { data, error }
}
