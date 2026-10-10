import { useEffect, useState } from 'react'
import { api, hhmm, postJson } from '../api'
import Card, { Button } from './Card'
import More from './More'

/*
 * 알림 카드 = 알림 받기(구독) + 알림함(보낸 알림). "켜고, 온 것을 보는 곳"을 한자리에(10/10 변경).
 * 알림함은 폰 푸시가 늦거나 막혀도 같은 내용을 보는 폴백이기도 하다(설계 §11).
 */
type State = 'idle' | 'busy' | 'on' | 'unsupported' | 'denied'
type Item = { vts: string; title: string; body: string }
const KEY = 'wipan_sub_species'
const SHOW = 2

function b64ToBytes(b64: string) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
const saved = () => { try { return localStorage.getItem(KEY) } catch { return null } }

export default function AlertsCard({ items, preset }: { items: Item[]; preset?: { species: string; at: number } | null }) {
  const [species, setSpecies] = useState<string>(() => saved() ?? '붉은대게')
  const [options, setOptions] = useState<string[]>(['붉은대게'])
  const [state, setState] = useState<State>(supported() ? 'idle' : 'unsupported')
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!preset) return
    setSpecies(preset.species)
    setEditing(true)
    document.getElementById('alerts-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [preset])

  useEffect(() => {
    api.pushKey().then((k) => setOptions(k.species)).catch(console.error)
    if (!supported()) return
    if (Notification.permission === 'denied') setState('denied')
    navigator.serviceWorker.getRegistration().then(async (reg) => {
      if (reg && (await reg.pushManager.getSubscription())) setState('on')
    }).catch(console.error)
  }, [])

  const subscribe = async () => {
    setMsg(null); setState('busy')
    try {
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') { setState('denied'); return }
      const reg = await navigator.serviceWorker.register('/sw.js')
      await navigator.serviceWorker.ready
      const { publicKey } = await api.pushKey()
      const sub = (await reg.pushManager.getSubscription())
        ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(publicKey) }))
      await postJson('/api/subscribe', { subscription: sub.toJSON(), species: species === '전체' ? null : species })
      try { localStorage.setItem(KEY, species) } catch { /* 저장 못 해도 구독은 됨 */ }
      setState('on'); setEditing(false)
    } catch (e) {
      console.error(e)
      setState('idle')
      setMsg(e instanceof Error && e.message ? e.message : '알림을 켜지 못했습니다. 크롬에서 다시 시도해 주세요.')
    }
  }

  const label = species === '전체' ? '배가 들어오면' : `${species} 들어오면`
  const current = saved() ?? species
  const shown = open ? items : items.slice(0, SHOW)
  return (
    <div id="alerts-card">
      <Card id="alerts" title="알림" aside="새벽에 배가 들어오면 폰으로 알려 드립니다">
        {state === 'unsupported' && <p className="text-sub text-muted">이 브라우저는 알림을 지원하지 않습니다. 안드로이드 크롬에서 열어 주세요.</p>}
        {state === 'denied' && <p className="text-sub text-muted">알림이 차단돼 있습니다. 크롬 설정 › 사이트 설정 › 알림에서 이 사이트를 허용해 주세요.</p>}
        {state === 'on' && !editing ? (
          <div className="flex items-center justify-between gap-2">
            <p role="status" className="text-body font-bold text-arrived">✓ {current === '전체' ? '모든 입항' : current} 알림 켜짐</p>
            <Button compact onClick={() => setEditing(true)}>바꾸기</Button>
          </div>
        ) : (state === 'idle' || state === 'busy' || state === 'on') && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-sub text-muted" htmlFor="sub-species">어종</label>
            <select id="sub-species" value={species} onChange={(e) => setSpecies(e.target.value)}
              className="min-h-[var(--spacing-touch)] rounded-button border border-line bg-card px-3 text-body text-ink">
              {[...options, '전체'].map((o) => <option key={o}>{o}</option>)}
            </select>
            <Button emphasis="high" onClick={subscribe} disabled={state === 'busy'} className="flex-1 sm:flex-none" aria-label={`${label} 알림 켜기`}>
              알림 켜기
            </Button>
          </div>
        )}
        {msg && <p role="alert" className="mt-2 text-sub text-arriving">{msg}</p>}

        <h3 className="mt-5 text-sub font-bold text-muted">보낸 알림</h3>
        {items.length === 0 ? (
          <p className="mt-1 text-sub text-muted">아직 보낸 알림이 없습니다.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {shown.map((n) => (
              <li key={n.vts + n.body} className="flex gap-3 text-sub">
                <span className="shrink-0 font-bold tabular-nums text-primary-dark">{hhmm(n.vts)}</span>
                <span>{n.body}</span>
              </li>
            ))}
          </ul>
        )}
        <More open={open} hidden={items.length - SHOW} label="이전 알림" onToggle={() => setOpen(!open)} />
      </Card>
    </div>
  )
}
