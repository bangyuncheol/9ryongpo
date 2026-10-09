import type { Today } from '../api'
import { pct } from '../api'
import Card from './Card'

export default function SpeciesCard({ today }: { today: Today | null }) {
  const sp = today?.species
  const basis = sp?.by_biz.find((b) => b.basis)?.basis
  const basisText = basis ? `최근 ${basis.years.length}년 ${basis.month}월 구룡포 위판 실적 기준` : undefined
  return (
    <Card id="species" title="오늘 뭐가 들어오나" aside={basisText}>
      {!sp || sp.overall.length === 0 ? (
        <p className="text-sub text-muted">입항 예정 배가 생기면 어종을 추정합니다.</p>
      ) : (
        <ul className="space-y-2">
          {sp.overall.map((s) => (
            <li key={s.name} className="flex items-center gap-3">
              <span className="w-20 shrink-0 text-body">{s.name}</span>
              <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-primary-soft" aria-hidden>
                <span className="block h-full rounded-full bg-primary-dark transition-[width] duration-500 ease-oneui" style={{ width: pct(s.share) }} />
              </span>
              <span className="w-11 text-right text-sub tabular-nums text-muted">{pct(s.share)}</span>
            </li>
          ))}
        </ul>
      )}
      {sp && sp.category_only_biz.length > 0 && (
        <p className="mt-3 text-small text-muted">
          {sp.category_only_biz.map((b) => b.replace(/어업$/, '')).join(', ')}은 해마다 잡는 어종이 달라 비율에서 뺐습니다.
        </p>
      )}
      <p className="mt-2 text-small text-muted">배의 어업 종류로 추정한 가능성입니다. 실제 어획과 다를 수 있습니다.</p>
    </Card>
  )
}
