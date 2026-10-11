# 프로덕션 마이그레이션 대기 목록

새 마이그레이션을 만들면 여기에 추가한다. 프로덕션 적용 후 상태를 "적용 완료"로 바꾸고 적용일을 적는다.

| 파일 | 내용 | 상태 | 적용일 |
|---|---|---|---|
| `cond_json` 형식 확장(DDL 없음) | `subs`·`call_subs`의 `species`를 문자열 → 목록으로(10/12 승인). 옛 문자열도 읽어 변환 불필요. **되돌릴 때**(옛 코드로 돌아가기 전): `UPDATE subs SET cond_json=json_object('species', json_extract(cond_json,'$.species[0]')) WHERE json_type(cond_json,'$.species')='array';` 와 같은 문장을 `call_subs`에도 | 대기 | — |
| `schema.sql` `call_subs` 추가 | 전화 알림 구독 테이블(새 테이블만, 기존 데이터 영향 없음). 서버 기동 시 자동 생성 | 대기 | — |
