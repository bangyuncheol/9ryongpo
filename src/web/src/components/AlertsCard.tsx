import { useEffect, useState } from 'react'
import { api, hhmm, postJson } from '../api'
import Card, { Button } from './Card'
import More from './More'
import { phoneDisplay, phoneOnlyDigits, phoneValid } from '../phone'

/*
 * 알림 카드 = 알림 받기(구독) + 알림함(보낸 알림). "켜고, 온 것을 보는 곳"을 한자리에(10/10 변경).
 * 알림함은 폰 푸시가 늦거나 막혀도 같은 내용을 보는 폴백이기도 하다(설계 §11).
 */
type State = 'idle' | 'busy' | 'on' | 'unsupported' | 'denied'
type Item = { vts: string; title: string; body: string }
const KEY = 'wipan_sub_species'
const PHONE_KEY = 'wipan_call_phone' // 가린 번호(예: 010-****-5678). 표시와 해지에 쓴다(전체 번호는 저장하지 않음)
const SHOW = 2

function b64ToBytes(b64: string) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
const saved = () => { try { return localStorage.getItem(KEY) } catch { return null } }
const savedPhone = () => { try { return localStorage.getItem(PHONE_KEY) } catch { return null } }

export default function AlertsCard({ items, preset, phone = false }: { items: Item[]; preset?: { species: string; at: number } | null; phone?: boolean }) {
  const [species, setSpecies] = useState<string>(() => saved() ?? '붉은대게')
  const [options, setOptions] = useState<string[]>(['붉은대게'])
  const [state, setState] = useState<State>(supported() ? 'idle' : 'unsupported')
  const [editing, setEditing] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [tel, setTel] = useState('') // 숫자만(하이픈은 화면이 넣는다, 10/11)
  const [telTouched, setTelTouched] = useState(false)
  const [telOn, setTelOn] = useState<string | null>(savedPhone)
  const [telMsg, setTelMsg] = useState<string | null>(null)
  const [telBusy, setTelBusy] = useState(false)

  // 앞자리가 01 이 아니면 바로, 덜 쳤으면 칸을 벗어났을 때 알려 준다(버튼이 왜 안 눌리는지 보이게)
  const telHint = tel && !phoneValid(tel) && (!tel.startsWith('01'.slice(0, tel.length)) || telTouched)
    ? '010으로 시작하는 휴대폰 번호를 끝까지 입력해 주세요.' : null

  const callOn = async () => {
    if (!phoneValid(tel)) { setTelTouched(true); return } // 틀린 번호는 보내지 않는다
    setTelMsg(null); setTelBusy(true)
    try {
      const r = await fetch('/api/call/subscribe', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: tel, species: species === '전체' ? null : species }) })
      const b = await r.json().catch(() => null)
      if (!r.ok) throw new Error(b?.detail ?? '전화 알림을 켜지 못했습니다. 잠시 후 다시 시도해 주세요.')
      try { localStorage.setItem(PHONE_KEY, b.phone) } catch { /* 표시만 못 함 */ }
      setTelOn(b.phone); setTel(''); setTelTouched(false)
    } catch (e) {
      setTelMsg(e instanceof Error ? e.message : '전화 알림을 켜지 못했습니다.')
    } finally { setTelBusy(false) }
  }

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

  const callOff = async () => {
    if (!telOn) return
    setTelMsg(null); setTelBusy(true)
    try {
      await postJson('/api/call/unsubscribe', { phone: telOn }) // 가린 번호로 끈다(번호를 다시 묻지 않음, 10/11)
      try { localStorage.removeItem(PHONE_KEY) } catch { /* 표시만 남음 */ }
      setTelOn(null)
    } catch (e) {
      setTelMsg(e instanceof Error ? e.message : '전화 알림을 끄지 못했습니다. 잠시 후 다시 시도해 주세요.')
    } finally { setTelBusy(false) }
  }

  const unsubscribe = async () => {
    setMsg(null); setState('busy')
    try {
      const reg = await navigator.serviceWorker.getRegistration()
      const sub = reg ? await reg.pushManager.getSubscription() : null
      if (sub) {
        await postJson('/api/unsubscribe', { endpoint: sub.endpoint })
        await sub.unsubscribe()
      }
      try { localStorage.removeItem(KEY) } catch { /* 표시만 남음 */ }
      setState('idle'); setEditing(false)
    } catch (e) {
      console.error(e)
      setState('on')
      setMsg(e instanceof Error && e.message ? e.message : '알림을 끄지 못했습니다. 잠시 후 다시 시도해 주세요.')
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
            <Button compact onClick={unsubscribe}>끄기</Button>{/* 어종을 바꾸려면 끄고 다시 켠다(10/11 '바꾸기' 제거) */}
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

        {phone && (telOn ? (
          <div className="mt-3 flex items-center justify-between gap-2">
            <p role="status" className="text-sub font-bold text-arrived">✓ 전화로도 알려 드립니다 · {telOn}</p>
            <Button compact onClick={callOff} disabled={telBusy}>전화 끄기</Button>
          </div>
        ) : (
          <form className="mt-3 flex flex-wrap items-center gap-2" onSubmit={(e) => { e.preventDefault(); callOn() }}>
            <label className="text-sub text-muted" htmlFor="call-phone">전화로도 받기</label>
            {/* 숫자만 받고 하이픈은 화면이 넣는다(숫자 키패드엔 하이픈 키가 없거나 찾기 어렵다). 010 은 11자리만(10/11) */}
            <input id="call-phone" name="tel" type="tel" inputMode="numeric" autoComplete="tel-national" placeholder="숫자만 입력 (예: 01012345678)"
              value={phoneDisplay(tel)} onChange={(e) => { setTel(phoneOnlyDigits(e.target.value)); setTelMsg(null) }} onBlur={() => setTelTouched(true)}
              aria-invalid={!!telHint} aria-describedby={telHint ? 'call-phone-hint' : undefined}
              className="min-h-[var(--spacing-touch)] min-w-0 flex-1 rounded-button border border-line bg-card px-3 text-body tabular-nums tracking-wide text-ink placeholder:tracking-normal placeholder:text-muted" />
            <Button type="submit" disabled={telBusy || !phoneValid(tel)}>전화 알림 받기</Button>
            {telHint && <p id="call-phone-hint" className="basis-full text-sub text-arriving">{telHint}</p>}
          </form>
        ))}
        {telMsg && <p role="alert" className="mt-2 text-sub text-arriving">{telMsg}</p>}

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
