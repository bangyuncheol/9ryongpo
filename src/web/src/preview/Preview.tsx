import { useEffect, useRef, useState } from 'react'
import { api, hhmm, TOOL_LABEL } from '../api'
import type { CallState } from '../api'

/*
 * 미리보기(?preview=1, 10/11): 한 화면에서 기기(폰·웹)와 시안(버전 1·2)을 바꿔 보고, 시연 진행·통화 내역은 옆 패널에서.
 * 화면은 같은 앱을 iframe 으로 띄운다(같은 주소라 카카오 지도·API 그대로). 진행 버튼은 화면 밖에 두어
 * 실제 사용자가 보는 모습 그대로 볼 수 있게 했다. 팀 내부 도구 — 사용자에게 안내하지 않는다.
 * 제품 화면이 아니라 시연 도구라 색은 토큰 대신 2차 시안 팔레트 값을 직접 쓴다(ui-design 규칙의 예외).
 */
type Device = 'phone' | 'web'
type Version = 1 | 2 | 3
const WEB_W = 1440
const WEB_H = 900
const STATUS: Record<string, string> = {
  idle: '', dialing: '전화 거는 중', 'in-progress': '통화 중', completed: '통화 끝남',
  'no-answer': '받지 않음', busy: '통화 중이라 연결 안 됨', rejected: '거절됨', canceled: '취소됨', failed: '연결 실패',
}

const load = <T,>(k: string, d: T): T => { try { const v = localStorage.getItem(k); return v ? (JSON.parse(v) as T) : d } catch { return d } }
const save = (k: string, v: unknown) => { try { localStorage.setItem(k, JSON.stringify(v)) } catch { /* 기억만 못 함 */ } }

export default function Preview() {
  const [device, setDevice] = useState<Device>(() => load('pv_device', 'phone'))
  const [version, setVersion] = useState<Version>(() => load('pv_version', 2))
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => save('pv_device', device), [device])
  useEffect(() => save('pv_version', version), [version])
  const src = version === 1 ? '/' : `/?v=${version}`

  return (
    <div className="min-h-screen bg-[#d9dde0] text-[#263238]">
      <div className="flex flex-wrap items-center gap-3 border-b border-black/10 bg-white px-5 py-3">
        <b className="mr-2 text-main">배마중 미리보기</b>
        <Seg label="기기" value={device} onChange={setDevice} items={[['phone', '📱 폰'], ['web', '🖥 웹']]} />
        <Seg label="시안" value={version} onChange={setVersion} items={[[1, '버전 1 (지금 화면)'], [2, '버전 2 (한 페이지)'], [3, '버전 3 (폰 홈+탭)']]} />
        <button onClick={() => setReloadKey((k) => k + 1)} className="rounded-full bg-[#edf1ee] px-3 py-1.5 text-sub font-bold">↻ 새로고침</button>
        <a href={src} target="_blank" rel="noreferrer" className="text-sub font-bold text-[#193b50] underline">새 탭에서 열기</a>
      </div>
      <div className="flex items-start gap-6 p-5">
        <div className="flex min-w-0 flex-1 justify-center">
          {device === 'phone' ? <PhoneFrame src={src} k={reloadKey} /> : <WebFrame src={src} k={reloadKey} />}
        </div>
        <Panel />
      </div>
    </div>
  )
}

function Seg<T extends string | number>({ label, value, onChange, items }: {
  label: string; value: T; onChange: (v: T) => void; items: [T, string][]
}) {
  return (
    <div className="flex items-center gap-1 rounded-full bg-[#edf1ee] p-1" role="radiogroup" aria-label={label}>
      {items.map(([v, t]) => (
        <button key={String(v)} role="radio" aria-checked={value === v} onClick={() => onChange(v)}
          className={`rounded-full px-3 py-1 text-sub font-bold ${value === v ? 'bg-[#193b50] text-white' : ''}`}>{t}</button>
      ))}
    </div>
  )
}

function PhoneFrame({ src, k }: { src: string; k: number }) {
  return (
    <div className="h-[844px] w-[390px] shrink-0 overflow-hidden rounded-[48px] border-[12px] border-[#111] bg-white shadow-2xl">
      <iframe key={`${src}-${k}`} src={src} title="폰 화면" className="h-full w-full border-0" />
    </div>
  )
}

/** 1440×900 화면을 남는 폭에 맞춰 축소해서 보여 준다(실제 웹 배치 그대로). */
function WebFrame({ src, k }: { src: string; k: number }) {
  const box = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.6)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(() => setScale(Math.min(1, el.clientWidth / WEB_W)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return (
    <div ref={box} className="w-full max-w-[1440px]">
      <div className="overflow-hidden rounded-xl bg-white shadow-2xl" style={{ height: WEB_H * scale + 36 }}>
        <div className="flex h-9 items-center gap-2 bg-[#eceff1] px-3">
          <span className="h-3 w-3 rounded-full bg-[#ff5f57]" /><span className="h-3 w-3 rounded-full bg-[#febc2e]" /><span className="h-3 w-3 rounded-full bg-[#28c840]" />
          <span className="ml-3 flex-1 truncate rounded-md bg-white px-3 py-0.5 text-small text-[#55636b]">baemajung · {src}</span>
          <span className="text-small text-[#55636b]">{Math.round(scale * 100)}%</span>
        </div>
        <iframe key={`${src}-${k}`} src={src} title="웹 화면" className="origin-top-left border-0"
          style={{ width: WEB_W, height: WEB_H, transform: `scale(${scale})` }} />
      </div>
    </div>
  )
}

/** 시연 진행 + 실시간 통화 내역. 화면 밖에 두어 사용자 화면을 가리지 않는다. */
function Panel() {
  const [clock, setClock] = useState<{ now: string; playing: boolean; speed: number } | null>(null)
  const [call, setCall] = useState<CallState | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null) // 한 번 실행하는 버튼은 누른 뒤 1초 강조(10/11)
  useEffect(() => {
    if (!flash) return
    const id = setTimeout(() => setFlash(null), 1000)
    return () => clearTimeout(id)
  }, [flash])
  const refresh = async () => {
    try { setClock(await (await fetch('/api/sim/state')).json()) } catch (e) { console.error(e) }
    try { setCall(await api.callState(true)) } catch (e) { console.error(e) }
  }
  useEffect(() => { refresh(); const id = setInterval(refresh, 1500); return () => clearInterval(id) }, [])
  const post = async (path: string) => {
    setMsg(null); setFlash(path)
    const r = await fetch(path, { method: 'POST' })
    if (!r.ok) setMsg(((await r.json().catch(() => null)) as { detail?: string } | null)?.detail ?? '실패했습니다.')
    refresh()
  }
  const btnBase = 'rounded-full px-3 py-1.5 text-sub font-bold transition-colors duration-200'
  /** 상태가 이어지는 버튼은 지금 상태와 맞으면 계속, 한 번 실행하는 버튼은 누른 뒤 1초 파랗게 */
  const cls = (path: string, active = false) => `${btnBase} ${active || flash === path ? 'bg-[#0072de] text-white' : 'bg-[#edf1ee]'}`
  const b = (path: string, label: string, active = false) => (
    <button className={cls(path, active)} aria-pressed={active || undefined} onClick={() => post(path)}>{label}</button>
  )
  const playing = !!clock?.playing
  return (
    <aside className="sticky top-5 w-[320px] shrink-0 space-y-3 text-sub">
      <section className="rounded-2xl bg-white p-4">
        <h2 className="font-bold text-[#55636b]">시연 진행</h2>
        <p className="mt-1"><span className="text-[28px] font-extrabold tabular-nums text-[#193b50]">{hhmm(clock?.now)}</span>{' '}
          <span className="text-[#55636b]">{clock ? (clock.playing ? `재생 ×${clock.speed}` : '정지') : ''}</span></p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {['03:00', '03:10', '03:50', '04:30'].map((t) => <span key={t}>{b(`/api/sim/seek?t=${t}`, t)}</span>)}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {b('/api/sim/play?speed=60', '재생 60배', playing && clock?.speed === 60)}
          {b('/api/sim/play?speed=300', '재생 300배', playing && clock?.speed === 300)}
          {b('/api/sim/pause', '일시정지', !!clock && !playing)}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {call?.enabled && <>
            {b(`/api/call/toggle?on=${!call.calls_on}`, call.calls_on ? '전화 켜짐 · 끄기' : '전화 켜기', call.calls_on)}
            {b('/api/call/test', '시험 전화')}
          </>}
          {b('/api/push/test', '시험 알림')}
        </div>
        {msg && <p role="alert" className="mt-2 text-[#b4501d]">{msg}</p>}
      </section>
      <section className="rounded-2xl bg-white p-4">
        <h2 className="font-bold text-[#55636b]">실시간 통화 내역 {call?.status && STATUS[call.status] ? `· ${STATUS[call.status]}` : ''}{call?.who ? ` · ${call.who}` : ''}</h2>
        <div className="mt-2 max-h-[420px] space-y-1.5 overflow-auto">
          {!call?.lines.length ? <p className="text-[#55636b]">{call?.enabled ? '통화가 없습니다.' : '전화 기능이 꺼져 있습니다(PHONE_ENABLED).'}</p>
            : call.lines.map((l, i) => l.role === 'tool' ? (
              <p key={i} className="rounded-md bg-[#d9eae5] px-2 py-0.5 font-mono text-small text-[#55636b]">→ {TOOL_LABEL[l.text.split(': ')[0]] ?? l.text.split(': ')[0]}: {l.text.split(': ').slice(1).join(': ')}</p>
            ) : (
              <p key={i}><b className={l.role === 'ai' ? 'text-[#193b50]' : ''}>{l.role === 'ai' ? '배마중' : '상대방'}</b> {l.text}</p>
            ))}
        </div>
      </section>
    </aside>
  )
}
