// 서버 API 타입과 호출. 응답 형식 정본은 src/server/app (engine.py, collectors/traffic.py).

export type Clock = { mode: 'sim' | 'live'; now: string; playing: boolean; speed: number }
export type Source = { feed: 'sim' | 'live'; label: string; stale: boolean; latest: string | null }
export type Species = { name: string; share: number }

export type Arrival = {
  ship_id: number; name: string | null; biz: string | null; gt: number | null
  d_km: number; lat: number; lon: number; status: '입항 중' | '입항'
  speed_kn?: number; eta?: string; confidence?: '높음' | '보통'
}

export type Today = {
  clock: Clock; source: Source; arriving: Arrival[]; arrived: Arrival[]
  species: {
    ships: number; total_gt: number; overall: Species[]; category_only_biz: string[]
    by_biz: { biz: string; count: number; gt: number; species: Species[]; category_only: boolean
      basis: { month: number; years: string[]; same_month: boolean } | null }[]
  }
}

export type Ship = {
  ship_id: number; name: string | null; biz: string | null; gt: number | null
  lat: number; lon: number; course: number | null; speed: number | null
  status: '입항 중' | '입항' | '조업·대기'
}

export type Sensor = { id: number; name: string; nickname: string | null; lat: number; lon: number; dist_m: number }
export type Place = { name: string; address?: string; lat: number; lon: number }

export type Traffic = {
  sensor: string; stale: boolean; fetched_at: string
  hours: { hour: string; truck: number; car: number; bus: number; total: number }[]
  last_hour: { hour: string; truck: number; total: number } | null
  congestion: { hour: string; value: number }[]
  vs_yesterday: { now: number | null; yesterday: number | null; hour: string | null; level: string }
  vs_day: string
}

export class ApiError extends Error {}

async function get<T>(path: string): Promise<T> {
  let r: Response
  try {
    r = await fetch(path)
  } catch {
    throw new ApiError('서버에 연결할 수 없습니다. 네트워크를 확인해 주세요.')
  }
  if (!r.ok) {
    const body = await r.json().catch(() => null)
    throw new ApiError(body?.message ?? body?.detail ?? '데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.')
  }
  return r.json() as Promise<T>
}

export const api = {
  today: () => get<Today>('/api/today'),
  ships: () => get<{ clock: Clock; source: Source; ships: Ship[] }>('/api/ships'),
  sensors: () => get<Sensor[]>('/api/sensors'),
  place: () => get<Place>('/api/place'),
  traffic: () => get<Traffic>('/api/traffic/now'),
  pushKey: () => get<{ publicKey: string; species: string[] }>('/api/push/key'),
  notifications: () => get<{ vts: string; title: string; body: string }[]>('/api/notifications'),
}

export async function adminPost(path: string, token: string): Promise<Clock & { feed: string }> {
  const r = await fetch(path, { method: 'POST', headers: { 'X-Admin-Token': token } })
  const body = await r.json().catch(() => null)
  if (!r.ok) throw new ApiError(body?.detail ?? '시계를 조작하지 못했습니다.')
  return body
}

export const hhmm = (iso?: string | null) => (iso ? iso.slice(11, 16) : '--:--')
export const pct = (v: number) => `${Math.round(v * 100)}%`

export async function postJson(path: string, body: unknown): Promise<void> {
  let r: Response
  try {
    r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    throw new ApiError('서버에 연결할 수 없습니다. 네트워크를 확인해 주세요.')
  }
  if (!r.ok) {
    const b = await r.json().catch(() => null)
    throw new ApiError(b?.detail ?? '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.')
  }
}
