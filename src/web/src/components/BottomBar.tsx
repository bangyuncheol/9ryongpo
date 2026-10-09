/** 하단 바(One UI bottom bar): 폰에서만. 2개 버튼, 아이콘+글자. 가장 중요한 행동을 엄지 닿는 곳에. */
const go = (id: string, focus?: string) => {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  if (focus) setTimeout(() => (document.getElementById(focus) as HTMLElement | null)?.focus({ preventScroll: true }), 350)
}

export default function BottomBar() {
  const item = 'flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-small font-bold text-ink active:bg-chip'
  return (
    <nav aria-label="주요 행동" className="fixed inset-x-0 bottom-0 z-[1000] flex border-t border-line bg-card pb-[env(safe-area-inset-bottom)] sm:hidden">
      <button className={item} onClick={() => go('subscribe-card')}>
        <svg aria-hidden width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
        알림 받기
      </button>
      <button className={item} onClick={() => go('chat-card', 'chat-input')}>
        <svg aria-hidden width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
        물어보기
      </button>
    </nav>
  )
}
