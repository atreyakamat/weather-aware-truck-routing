const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function postPlan(payload) {
  const res = await fetch(`${BASE}/api/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || Object.values(body).flat().join("; ") || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}
