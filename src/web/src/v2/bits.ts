// 2차 시안(?v=2) 공용 계산. 화면 문구는 여기서 만든다(숫자는 서버 값 그대로).
import type { Arrival, Species, Today } from '../api'

/** 지금(가상)부터 ETA까지 분. 지났으면 0. */
export function minutesUntil(now?: string, eta?: string) {
  if (!now || !eta) return null
  return Math.max(0, Math.round((new Date(eta).getTime() - new Date(now).getTime()) / 60000))
}

/** 비율을 말로 먼저(물량처럼 읽히지 않게). 숫자는 작게 따로 붙인다. */
export function likelihood(share: number) {
  if (share >= 0.6) return '가능성 높음'
  if (share >= 0.3) return '가능성 있음'
  return '가능성 낮음'
}

export function shortBiz(biz?: string | null) {
  if (!biz) return '어선'
  for (const k of ['채낚기', '자망', '통발', '선망', '트롤', '정치망', '연승', '안강망', '복합']) if (biz.includes(k)) return k
  return biz.replace(/어업$/, '')
}

/** 이 배의 업종으로 추정한 어종 1위. 해마다 어종이 바뀌는 업종이면 null + categoryOnly. */
export function shipSpecies(today: Today | null, a: Arrival): { top: Species | null; categoryOnly: boolean } {
  const b = today?.species.by_biz.find((x) => x.biz === a.biz)
  if (!b) return { top: null, categoryOnly: false }
  return { top: b.category_only ? null : b.species[0] ?? null, categoryOnly: b.category_only }
}

export const byEta = (a: Arrival, b: Arrival) => (a.eta ?? '').localeCompare(b.eta ?? '')

/** 방문 권장 '오늘 하루 중 붐비는 편입니다' → '붐비는 편' */
export function trafficWord(now?: string | null) {
  if (!now) return null
  return now.replace(/^오늘 하루 중 /, '').replace(/(입니다|합니다)\.?$/, '').trim()
}

export const telHref = (num: string) => `tel:${num.replace(/\D/g, '')}`
export const telText = (num: string) => num.replace(/^(\d{3})(\d{3,4})(\d{4})$/, '$1-$2-$3')
