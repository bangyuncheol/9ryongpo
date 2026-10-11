import { useEffect, useState } from 'react'
import { adminPost } from '../api'
import type { CallState, Clock } from '../api'
import { Button } from './Card'

/**
 * 데모 진행용. 주소에 ?admin=1 을 붙였을 때만 보인다. 토큰 없음(10/10 결정, 우리만 쓰는 데모 도구).
 * 누른 표시(10/11): 상태가 이어지는 버튼(재생 60·300배, 일시정지, 전화 켜기)은 지금 상태와 맞으면 계속 강조,
 * 한 번 실행하는 버튼(시각 이동, 시험 알림·전화, 데이터 전환)은 누른 뒤 1초 강조.
 */
export default function AdminBar({ clock, feed, call }: { clock: Clock | null; feed: string | null; call?: CallState | null }) {
  const [msg, setMsg] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [now, setNow] = useState<Clock | null>(null) // 누른 직후 서버 응답의 시계(2초 폴링을 기다리지 않게)
  const [callsOn, setCallsOn] = useState<boolean | null>(null)
  useEffect(() => { setNow(null) }, [clock?.playing, clock?.speed])
  useEffect(() => { setCallsOn(null) }, [call?.calls_on])
  useEffect(() => {
    if (!flash) return
    const id = setTimeout(() => setFlash(null), 1000)
    return () => clearTimeout(id)
  }, [flash])

  const run = async (path: string) => {
    setFlash(path)
    try {
      const r = (await adminPost(path)) as unknown as Partial<Clock & CallState>
      if (typeof r?.playing === 'boolean') setNow(r as Clock)
      if (typeof r?.calls_on === 'boolean') setCallsOn(r.calls_on)
      setMsg(null)
    } catch (e) { setMsg(e instanceof Error ? e.message : '실패했습니다.') }
  }
  const c = now ?? clock
  const on = callsOn ?? call?.calls_on ?? false
  const hi = (path: string, active = false) => (active || flash === path ? 'high' : 'medium') as 'high' | 'medium'
  const b = (path: string, label: string, active = false) => (
    <Button compact emphasis={hi(path, active)} aria-pressed={active || undefined} onClick={() => run(path)}>{label}</Button>
  )
  const feedPath = `/api/sim/feed?mode=${feed === 'sim' ? 'live' : 'sim'}`
  return (
    <div className="mx-[var(--spacing-side)] flex flex-wrap items-center gap-2 rounded-card border border-dashed border-line bg-card p-3 text-small">
      <span className="font-bold">진행</span>
      {b('/api/sim/seek?t=03:00', '03:00')}
      {b('/api/sim/seek?t=03:10', '03:10')}
      {b('/api/sim/play?speed=60', '재생 60배', !!c?.playing && c.speed === 60)}
      {b('/api/sim/play?speed=300', '재생 300배', !!c?.playing && c.speed === 300)}
      {b('/api/sim/pause', '일시정지', !!c && !c.playing)}
      {b(feedPath, feed === 'sim' ? '실데이터로 전환' : '시뮬레이션으로 전환')}
      {b('/api/push/test', '시험 알림')}
      {call?.enabled && <>
        {b(`/api/call/toggle?on=${!on}`, on ? '전화 켜짐 · 끄기' : '전화 켜기', on)}
        {b('/api/call/test', '시험 전화')}
      </>}
      <span className="text-muted">{c ? `${c.playing ? '재생' : '정지'} ×${c.speed}` : ''}</span>
      {msg && <span role="alert" className="text-arriving">{msg}</span>}
    </div>
  )
}
