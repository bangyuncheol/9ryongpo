import { useEffect, useRef, useState } from 'react'

/*
 * 물어보기 음성 입력(10/13 오너). 마이크 소리를 받아 16kHz 16비트 PCM 한 덩어리로 만든다(CLOVA 가 받는 형식이라
 * 서버에서 변환하지 않는다). 말을 시작한 뒤 1.5초 조용하면 저절로 끝내고, 아무리 길어도 15초에서 끝낸다.
 */
const RATE = 16000
const MAX_MS = 15000
const QUIET_MS = 1500
const SPEECH_RMS = 0.02 // 이보다 크면 말하는 중으로 본다

export type VoiceState = 'idle' | 'listening' | 'busy'

export const voiceSupported = () => typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof AudioContext !== 'undefined'

/** 녹음 → onPcm(16kHz PCM16) 으로 넘긴다. 다시 부르면(stop) 그때까지 녹음한 것으로 끝낸다. */
export function useVoice(onPcm: (pcm: ArrayBuffer) => Promise<void>) {
  const [state, setState] = useState<VoiceState>('idle')
  const [error, setError] = useState<string | null>(null)
  const stopRef = useRef<(() => void) | null>(null)
  useEffect(() => () => stopRef.current?.(), [])

  const start = async () => {
    setError(null)
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
    } catch (e) {
      console.error(e)
      setError('마이크를 쓸 수 없습니다. 크롬 설정 › 사이트 설정 › 마이크에서 허용해 주세요.')
      return
    }
    const ctx = new AudioContext()
    const src = ctx.createMediaStreamSource(stream)
    const node = ctx.createScriptProcessor(4096, 1, 1)
    const chunks: Float32Array[] = []
    const t0 = performance.now()
    let spoke = false, lastLoud = t0, done = false
    const finish = async () => {
      if (done) return
      done = true; stopRef.current = null
      node.disconnect(); src.disconnect(); stream.getTracks().forEach((t) => t.stop())
      const rate = ctx.sampleRate
      void ctx.close()
      setState('busy')
      try { await onPcm(toPcm16(chunks, rate)) } catch (e) { setError(e instanceof Error ? e.message : '음성을 보내지 못했습니다.') }
      setState('idle')
    }
    node.onaudioprocess = (ev) => {
      const d = ev.inputBuffer.getChannelData(0)
      chunks.push(new Float32Array(d))
      let sum = 0
      for (let i = 0; i < d.length; i++) sum += d[i] * d[i]
      const now = performance.now()
      if (Math.sqrt(sum / d.length) > SPEECH_RMS) { spoke = true; lastLoud = now }
      if (now - t0 > MAX_MS || (spoke && now - lastLoud > QUIET_MS)) void finish()
    }
    src.connect(node); node.connect(ctx.destination)
    stopRef.current = () => void finish()
    setState('listening')
  }
  const toggle = () => (state === 'listening' ? stopRef.current?.() : state === 'idle' ? void start() : undefined)
  return { state, error, setError, toggle }
}

/** 마이크 표본(보통 48kHz float)을 16kHz 16비트 PCM 으로(구간 평균으로 줄인다). */
function toPcm16(chunks: Float32Array[], rate: number): ArrayBuffer {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const all = new Float32Array(total)
  let o = 0
  for (const c of chunks) { all.set(c, o); o += c.length }
  const ratio = rate / RATE
  const n = Math.floor(total / ratio)
  const out = new DataView(new ArrayBuffer(n * 2))
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * ratio), b = Math.min(total, Math.floor((i + 1) * ratio))
    let s = 0
    for (let j = a; j < b; j++) s += all[j]
    const v = Math.max(-1, Math.min(1, s / Math.max(1, b - a)))
    out.setInt16(i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true)
  }
  return out.buffer
}
