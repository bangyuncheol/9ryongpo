// 휴대폰 번호 입력 공용(버전 1 AlertsCard · 버전 2~4 WaitFish, 10/11): 숫자만 11자리까지 받고 010-1234-5678 처럼 끊어 보인다.
// 맞는 번호 기준은 서버 config.phone_digits 와 같다.
export const phoneOnlyDigits = (raw: string) => raw.replace(/\D/g, '').slice(0, 11)
export const phoneValid = (d: string) => /^(010\d{8}|01[16-9]\d{7,8})$/.test(d) // 010 은 11자리만, 옛 번호(011·016~019)는 10자리도
export function phoneDisplay(d: string) {
  if (d.length <= 3) return d
  if (d.length <= 7) return `${d.slice(0, 3)}-${d.slice(3)}`
  const mid = d.length === 10 && !d.startsWith('010') ? 3 : 4 // 옛 번호 10자리만 3-3-4. 010 은 늘 3-4-4(덜 쳐도 다 친 것처럼 보이지 않게)
  return `${d.slice(0, 3)}-${d.slice(3, 3 + mid)}-${d.slice(3 + mid)}`
}
