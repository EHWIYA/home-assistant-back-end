# Push API — 서버 공조 메일 (발송 완료)

**제목:** `[공조 요청] Web Push API Phase 4~6 — NAS Push 서비스 구현·스펙 합의`  
**상태:** 2026-07-09 발송·서버 배포 완료 → [from-server.md](from-server.md)

기술 상세: [spec.md](spec.md) · 프론트 회신: [to-frontend.md](to-frontend.md)

---

<details>
<summary>발송 본문 (참고용)</summary>

```text
[공조 요청] → 서버 담당

발신: 백엔드(iot-api) — 프론트 요청 + 백엔드 검토 종합
수신: 서버(NAS) — Push API / nginx / Firebase
목적: Web Push Phase 4~6 REST API 구현 범위·스펙·우선순위 합의

Base URL: https://iot.iwhya.kr/api/push/*
인증: Authorization: Bearer {IOT_API_KEY}
CORS Origin: https://iot.iwhya.kr

기존: POST /register, DELETE /unregister
신규 P1: GET /status, POST /test
신규 P2: GET /tokens, GET /history?limit=30

백엔드 판단: iot-api 범위 밖, NAS 별도 Push 서비스에서 구현.
iot-api Docker 이미지 갱신 불필요.

(상세 스펙·curl 스모크는 spec.md 참고)
```

</details>
