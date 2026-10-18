// 패션 접수함 워커: 도우미 입력칸이 보낸 '제품 정보'를 KV(REQ)에 쌓는다.
// 드레인 워크플로가 주기적으로 꺼내 reports/패션-요청/ 로 커밋 → 생성 세션이 글로 만든다.
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (request.method === "GET") {
      return new Response(JSON.stringify({ ok: true, msg: "fashion intake" }), {
        headers: { ...CORS, "content-type": "application/json" },
      });
    }
    if (request.method !== "POST") {
      return new Response(JSON.stringify({ ok: false, error: "method" }), {
        status: 405, headers: { ...CORS, "content-type": "application/json" },
      });
    }
    let text = "";
    try {
      const ct = request.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        const j = await request.json();
        text = (j.text || "").toString();
      } else {
        const f = await request.formData();
        text = (f.get("text") || "").toString();
      }
    } catch (e) {
      text = "";
    }
    text = text.trim();
    if (!text) {
      return new Response(JSON.stringify({ ok: false, error: "empty" }), {
        status: 400, headers: { ...CORS, "content-type": "application/json" },
      });
    }
    if (text.length > 4000) text = text.slice(0, 4000);
    const id = Date.now() + "-" + Math.random().toString(36).slice(2, 8);
    // 14일 뒤 자동 만료(미처리분 쌓임 방지)
    await env.REQ.put("req:" + id, JSON.stringify({ text, ts: new Date().toISOString() }), {
      expirationTtl: 60 * 60 * 24 * 14,
    });
    return new Response(JSON.stringify({ ok: true }), {
      headers: { ...CORS, "content-type": "application/json" },
    });
  },
};
