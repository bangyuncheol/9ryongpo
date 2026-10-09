import { useEffect, useState } from 'react'
import { api, postJson } from '../api'
import Card, { Button } from './Card'

type State = 'idle' | 'busy' | 'on' | 'unsupported' | 'denied'
const KEY = 'wipan_sub_species'

function b64ToBytes(b64: string) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

export default function SubscribeCard({ preset }: { preset?: { species: string; at: number } | null }) {
  const [species, setSpecies] = useState<string>(() => { try { return localStorage.getItem(KEY) ?? '붉은대게' } catch { return '붉은대게' } })
  const [options, setOptions] = useState<string[]>(['붉은대게'])
  const [state, setState] = useState<State>(supported() ? 'idle' : 'unsupported')
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!preset) return
    setSpecies(preset.species)
    document.getElementById('subscribe-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
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
      setState('on')
    } catch (e) {
      console.error(e)
      setState('idle')
      setMsg(e instanceof Error && e.message ? e.message : '알림을 켜지 못했습니다. 크롬에서 다시 시도해 주세요.')
    }
  }

  const label = species === '전체' ? '배가 들어오면' : `${species} 들어오면`
  return (
    <div id="subscribe-card">
    <Card id="subscribe" title="알림 받기" aside="새벽에 배가 들어오면 폰으로 알려 드립니다">
      {state === 'unsupported' && <p className="text-sub text-muted">이 브라우저는 알림을 지원하지 않습니다. 안드로이드 크롬에서 열어 주세요.</p>}
      {state === 'denied' && <p className="text-sub text-muted">알림이 차단돼 있습니다. 크롬 설정 › 사이트 설정 › 알림에서 이 사이트를 허용해 주세요.</p>}
      {(state === 'idle' || state === 'busy' || state === 'on') && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sub text-muted" htmlFor="sub-species">어종</label>
          <select id="sub-species" value={species} onChange={(e) => setSpecies(e.target.value)}
            className="min-h-[var(--spacing-touch)] rounded-button border border-line bg-card px-3 text-body text-ink">
            {[...options, '전체'].map((o) => <option key={o}>{o}</option>)}
          </select>
          <Button emphasis="high" onClick={subscribe} disabled={state === 'busy'} className="flex-1 sm:flex-none">
            {label} 알려줘
          </Button>
        </div>
      )}
      {state === 'on' && <p role="status" className="mt-2 text-sub font-bold text-arrived">✓ 알림이 켜져 있습니다</p>}
      {msg && <p role="alert" className="mt-2 text-sub text-arriving">{msg}</p>}
    </Card>
    </div>
  )
}
