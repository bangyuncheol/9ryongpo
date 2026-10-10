/** 긴 목록 접기. 폰에서 카드 안 스크롤(손가락이 갇힘) 대신 페이지 스크롤 하나만 쓰기 위해. */
export default function More({ open, hidden, label, onToggle }: { open: boolean; hidden: number; label: string; onToggle: () => void }) {
  if (hidden <= 0 && !open) return null
  return (
    <button onClick={onToggle} aria-expanded={open}
      className="mt-2 flex min-h-[var(--spacing-touch)] w-full items-center justify-center gap-1 rounded-button text-sub font-bold text-primary-dark hover:bg-primary-soft">
      {open ? '접기' : `${label} ${hidden}개 더보기`}
      <svg aria-hidden width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
        strokeLinecap="round" className={`transition-transform duration-200 ease-oneui ${open ? 'rotate-180' : ''}`}><path d="m6 9 6 6 6-6" /></svg>
    </button>
  )
}
