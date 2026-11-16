const ENDPOINT = "http://127.0.0.1:8167";
let badge, fallback;
function visibleVideoIsPlaying() {
  return [...document.querySelectorAll("video")].some(v => !v.paused && !v.ended && v.readyState >= 3 && v.offsetWidth > 40 && v.offsetHeight > 40);
}
function showStatus(state) {
  if (state.work_mode) { badge?.remove(); badge = null; fallback?.remove(); fallback = null; return; }
  if (state.locked) {
    if (!fallback) { fallback = document.createElement("div"); fallback.id = "video-study-guardian-fallback"; fallback.textContent = "学习守护已锁定：请在全屏题目中答题后继续观看"; document.documentElement.appendChild(fallback); }
    return;
  }
  fallback?.remove(); fallback = null;
  if (!badge) { badge = document.createElement("div"); badge.id = "video-study-guardian-badge"; document.documentElement.appendChild(badge); }
  const s = Math.max(0, state.remaining); badge.textContent = `学习守护：${String(Math.floor(s/60)).padStart(2,"0")}:${String(s%60).padStart(2,"0")}`;
}
const css = document.createElement("style"); css.textContent = `#video-study-guardian-badge{position:fixed!important;right:20px!important;top:76px!important;z-index:2147483647!important;background:#22213d!important;color:#fff!important;border:2px solid #fff!important;border-radius:999px!important;padding:9px 14px!important;font:700 14px system-ui!important;pointer-events:none!important}#video-study-guardian-fallback{position:fixed!important;inset:0!important;z-index:2147483647!important;display:grid!important;place-items:center!important;background:#17152ff5!important;color:#fff!important;text-align:center!important;font:700 28px/1.5 system-ui,"Microsoft YaHei",sans-serif!important;padding:40px!important}`; document.documentElement.appendChild(css);
async function heartbeat() {
  try {
    const active = document.visibilityState === "visible" && visibleVideoIsPlaying();
    const response = await fetch(`${ENDPOINT}/${active ? "activity" : "status"}`, {method: active ? "POST" : "GET", cache: "no-store"});
    showStatus(await response.json());
  } catch (_) { badge?.remove(); badge = null; }
}
// 锁定时用较高频率查询，使新打开的普通网页也马上出现遮罩。
setInterval(heartbeat, 1000); heartbeat();
