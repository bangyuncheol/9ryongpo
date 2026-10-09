import { useEffect, useState } from 'react'
import { api, postJson } from '../api'
import Card from './Card'

type State = 'idle' | 'busy' | 'on' | 'unsupported' | 'denied'
const KEY = 'wipan_sub_species'

function b64ToBytes(b64: string) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

export default function SubscribeCard() {
  const [species, setSpecies] = useState<string>(() => { try { return localStorage.getItem(KEY) ?? '붉은대게' } catch { return '붉은대게' } })
  const [options, setOptions] = useState<string[]>(['붉은대게'])
  const [state, setState] = useState<State>(supported() ? 'idle' : 'unsupported')
  const [msg, setMsg] = useState<string | null>(null)

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
    <Card title="알림 받기">
      {state === 'unsupported' && <p className="text-sm text-muted">이 브라우저는 알림을 지원하지 않습니다. 안드로이드 크롬에서 열어 주세요.</p>}
      {state === 'denied' && <p className="text-sm text-muted">알림이 차단돼 있습니다. 크롬 설정 › 사이트 설정 › 알림에서 이 사이트를 허용해 주세요.</p>}
      {(state === 'idle' || state === 'busy' || state === 'on') && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm" htmlFor="sub-species">어종</label>
          <select id="sub-species" value={species} onChange={(e) => setSpecies(e.target.value)}
            className="rounded border border-line bg-card px-2 py-1 text-sm">
            {[...options, '전체'].map((o) => <option key={o}>{o}</option>)}
          </select>
          <button onClick={subscribe} disabled={state === 'busy'}
            className="rounded-lg bg-sea px-3 py-1.5 text-sm font-bold text-white disabled:opacity-60">
            🔔 {label} 알려줘
          </button>
          {state === 'on' && <span className="text-sm text-arrived">알림이 켜져 있습니다</span>}
        </div>
      )}
      {msg && <p role="alert" className="mt-2 text-sm text-arriving">{msg}</p>}
    </Card>
  )
}
