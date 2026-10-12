/*
 * 버전 2·3 아이콘 한 벌(10/11). 이모지는 기기마다 모양이 달라 선 아이콘으로 통일한다(선 2px, 둥근 끝).
 * phone·arrow-right·truck: Rune Icons outline — Copyright (c) 2026 Rune Icons Team, Apache License 2.0
 * (https://runeicons.com). bell: 같은 세트의 bell-off 에서 사선을 빼 이 제품이 만든 것.
 */
const PATHS = {
  phone: 'M13.832 16.568a1 1 0 0 0 1.213-.303l.355-.465A2 2 0 0 1 17 15h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v3a2 2 0 0 1-.8 1.6l-.468.351a1 1 0 0 0-.292 1.233 14 14 0 0 0 6.392 6.384',
  bell: 'M10.268 21a2 2 0 0 0 3.464 0M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326',
  arrow: 'M5 12h14M12 19l7-7-7-7',
  truck: 'M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2m0 0a2 2 0 0 0 4 0m-4 0a2 2 0 0 1 4 0m6 0H9m6 0a2 2 0 0 0 4 0m-4 0a2 2 0 0 1 4 0m0 0h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14',
} as const

export type IconName = keyof typeof PATHS

/** 장식용이면 label 없이(aria-hidden), 뜻을 전하면 label 을 준다. 크기는 글자 크기를 따른다(1em). */
export default function Icon({ name, label, className = '' }: { name: IconName; label?: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
      className={`inline-block h-[1.1em] w-[1.1em] shrink-0 ${className}`}
      role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <path d={PATHS[name]} />
    </svg>
  )
}
