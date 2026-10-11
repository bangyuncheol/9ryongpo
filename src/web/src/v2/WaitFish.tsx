import { useEffect, useState } from 'react'
import { api, postJson } from '../api'
import { Button } from '../components/Card'
import Icon from './Icon'
import { phoneDisplay, phoneOnlyDigits, phoneValid } from '../phone'

/*
 * 2차 시안 알림 카드: '알림 설정' 대신 "기다리는 생선이 있나요?" — 어종을 고르고, 휴대폰 알림·전화를 한 번에 신청.
 * 저장값(localStorage 키)은 기존 화면 AlertsCard 와 같다 → 두 화면의 켜짐 상태가 어긋나지 않는다.
 */
const KEY = 'wipan_sub_species'
const PHONE_KEY = 'wipan_call_phone'

const supported = () => 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window
const read = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const write = (k: string, v: string | null) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v) } catch { /* 표시만 못 함 */ } }

function b64ToBytes(b64: string) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4)
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

export default function WaitFish({ phoneEnabled, onChange }: {
  phoneEnabled: boolean
  /** 켜짐 상태가 바뀌면 알린다(버전 4 '생선 알림 받기' 버튼이 '붉은대게 알림 켜짐'으로 바뀜, 10/11) */
  onChange?: (s: { on: boolean; species: string }) => void
}) {
  const [options, setOptions] = useState<string[]>(['붉은대게'])
  const [species, setSpecies] = useState(() => read(KEY) ?? '붉은대게')
  const [pushOn, setPushOn] = useState(false)
  const [phoneOn, setPhoneOn] = useState<string | null>(() => read(PHONE_KEY))
  const [wantPush, setWantPush] = useState(supported())
  const [wantPhone, setWantPhone] = useState(false)
  const [tel, setTel] = useState('') // 숫자만
  const [telTouched, setTelTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  useEffect(() => {
    // 구룡포 10월 대표 어종을 앞에(나머지는 가나다순)
    const lead = ['붉은대게', '살오징어']
    api.pushKey().then((k) => setOptions([...lead.filter((x) => k.species.includes(x)), ...k.species.filter((x) => !lead.includes(x))])).catch(console.error)
    if (!supported()) return
    navigator.serviceWorker.getRegistration()
      .then(async (reg) => setPushOn(!!(reg && (await reg.pushManager.getSubscription()))))
      .catch(console.error)
  }, [])

  const subscribePush = async (sp: string | null) => {
    const perm = await Notification.requestPermission()
    if (perm !== 'granted') throw new Error('알림이 차단돼 있습니다. 크롬 설정 › 사이트 설정 › 알림에서 허용해 주세요.')
    const reg = await navigator.serviceWorker.register('/sw.js')
    await navigator.serviceWorker.ready
    const { publicKey } = await api.pushKey()
    const sub = (await reg.pushManager.getSubscription())
      ?? (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(publicKey) }))
    await postJson('/api/subscribe', { subscription: sub.toJSON(), species: sp })
  }

  const apply = async () => {
    if (wantPhone && !phoneOn && !phoneValid(tel)) { setTelTouched(true); return } // 아무것도 보내지 않는다
    setMsg(null); setBusy(true)
    const sp = species === '전체' ? null : species
    try {
      if (wantPush && !pushOn) { await subscribePush(sp); setPushOn(true) }
      if (wantPhone && !phoneOn) {
        const r = await fetch('/api/call/subscribe', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone: tel, species: sp }) })
        const b = await r.json().catch(() => null)
        if (!r.ok) throw new Error(b?.detail ?? '전화 알림을 신청하지 못했습니다. 잠시 후 다시 시도해 주세요.')
        write(PHONE_KEY, b.phone); setPhoneOn(b.phone); setTel(''); setTelTouched(false)
      }
      write(KEY, species)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : '알림을 신청하지 못했습니다. 잠시 후 다시 시도해 주세요.')
    } finally { setBusy(false) }
  }

  const pushOff = async () => {
    setBusy(true)
    try {
      const reg = await navigator.serviceWorker.getRegistration()
      const sub = reg ? await reg.pushManager.getSubscription() : null
      if (sub) { await postJson('/api/unsubscribe', { endpoint: sub.endpoint }); await sub.unsubscribe() }
      setPushOn(false)
    } catch (e) { setMsg(e instanceof Error ? e.message : '알림을 끄지 못했습니다.') } finally { setBusy(false) }
  }
  const phoneOff = async () => {
    if (!phoneOn) return
    setBusy(true)
    try { await postJson('/api/call/unsubscribe', { phone: phoneOn }); write(PHONE_KEY, null); setPhoneOn(null) }
    catch (e) { setMsg(e instanceof Error ? e.message : '전화 알림을 끄지 못했습니다.') } finally { setBusy(false) }
  }

  const waiting = pushOn || !!phoneOn
  const current = read(KEY) ?? species
  useEffect(() => { onChange?.({ on: waiting, species: current }) }, [onChange, waiting, current])
  // 전화를 골랐으면 번호가 맞아야만 신청한다. 휴대폰 알림만 먼저 신청되고 전화는 거절되는 반쪽 신청을 막는다(10/11 오너 재현)
  const phoneNeeded = wantPhone && !phoneOn
  const canApply = ((wantPush && !pushOn) || phoneNeeded) && (!phoneNeeded || phoneValid(tel))
  // 앞자리가 01 이 아니면 바로, 자릿수가 모자라면 칸을 벗어났을 때 알려 준다(버튼이 왜 안 눌리는지 보이게)
  const telHint = wantPhone && !phoneOn && tel && !phoneValid(tel) && (!tel.startsWith('01'.slice(0, tel.length)) || telTouched)
    ? '010으로 시작하는 휴대폰 번호를 끝까지 입력해 주세요.' : null

  return (
    <section className="rounded-card bg-card p-5" aria-labelledby="wait-title">
      <h2 id="wait-title" className="text-title font-bold text-primary-dark">기다리는 생선이 있나요?</h2>
      <p className="mt-1 text-sub text-muted">원하는 생선이 들어오면 먼저 알려 드릴게요.</p>

      {waiting && (
        <ul className="mt-4 space-y-2">
          {pushOn && (
            <li className="flex items-center justify-between gap-2 rounded-button bg-[var(--color-sunrise-soft)] px-3 py-2">
              <span className="flex items-center gap-2 text-sub font-bold"><Icon name="bell" className="text-arriving" />{current === '전체' ? '어떤 배든' : current} 기다리는 중 · 휴대폰 알림</span>
              <Button compact onClick={pushOff} disabled={busy}>끄기</Button>
            </li>
          )}
          {phoneOn && (
            <li className="flex items-center justify-between gap-2 rounded-button bg-[var(--color-sunrise-soft)] px-3 py-2">
              <span className="flex items-center gap-2 text-sub font-bold"><Icon name="phone" className="text-arriving" />전화로도 알려 드려요 · <span className="tabular-nums">{phoneOn}</span></span>
              <Button compact onClick={phoneOff} disabled={busy}>끄기</Button>
            </li>
          )}
        </ul>
      )}

      {!(pushOn && (phoneOn || !phoneEnabled)) && (
        <>
          <div className="mt-4 flex flex-wrap gap-2" role="radiogroup" aria-label="기다리는 생선">
            {[...options, '전체'].map((o) => (
              <button key={o} role="radio" aria-checked={species === o} onClick={() => setSpecies(o)}
                disabled={waiting}
                className={`v2-press min-h-[var(--spacing-touch)] rounded-button px-4 text-button font-bold disabled:opacity-60 ${
                  species === o ? 'bg-primary-dark text-on-primary' : 'bg-chip text-ink hover:brightness-95'}`}>
                {o === '전체' ? '어떤 배든' : o}
              </button>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-body">
            {supported() && !pushOn && (
              <label className="flex min-h-[var(--spacing-touch)] items-center gap-2">
                <input type="checkbox" checked={wantPush} onChange={(e) => setWantPush(e.target.checked)} className="h-5 w-5 accent-[var(--color-primary-dark)]" />
                <Icon name="bell" className="text-muted" />휴대폰 알림
              </label>
            )}
            {phoneEnabled && !phoneOn && (
              <label className="flex min-h-[var(--spacing-touch)] items-center gap-2">
                <input type="checkbox" checked={wantPhone} onChange={(e) => setWantPhone(e.target.checked)} className="h-5 w-5 accent-[var(--color-primary-dark)]" />
                <Icon name="phone" className="text-muted" />전화
              </label>
            )}
          </div>
          {wantPhone && !phoneOn && (
            <div className="mt-2">
              <label htmlFor="wait-tel" className="text-sub font-bold">전화 받을 번호</label>
              {/* 숫자만 받고 하이픈은 화면이 넣는다: 숫자 키패드에는 하이픈 키가 없거나 찾기 어렵다(10/11 오너) */}
              <input id="wait-tel" name="tel" type="tel" inputMode="numeric" autoComplete="tel-national" placeholder="숫자만 입력 (예: 01012345678)"
                value={phoneDisplay(tel)} onChange={(e) => { setTel(phoneOnlyDigits(e.target.value)); setMsg(null) }} onBlur={() => setTelTouched(true)}
                aria-invalid={!!telHint} aria-describedby={telHint ? 'wait-tel-hint' : undefined}
                className="mt-1 min-h-[var(--spacing-touch)] w-full rounded-button border border-line bg-card px-3 text-body tabular-nums tracking-wide text-ink placeholder:tracking-normal placeholder:text-muted" />
              {telHint && <p id="wait-tel-hint" className="mt-1 text-sub text-arriving">{telHint}</p>}
            </div>
          )}
          <Button emphasis="high" onClick={apply} disabled={busy || !canApply} className="mt-4 w-full">
            {busy ? '신청하는 중…' : '알림 신청하기'}
          </Button>
        </>
      )}
      {msg && <p role="alert" className="mt-2 text-sub text-arriving">{msg}</p>}
    </section>
  )
}
