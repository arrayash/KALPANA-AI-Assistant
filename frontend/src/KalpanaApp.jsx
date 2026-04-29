import { useState, useRef, useEffect, useCallback } from "react";

// ─── Constants ────────────────────────────────────────────────────────────────
const API_BASE = "https://specially-unvolatile-latricia.ngrok-free.dev";
const MAX_HISTORY_TURNS = 6;
const SESSION_ID = "session_" + Math.random().toString(36).slice(2, 10);

const QUERY_TEMPLATES = [
  { tag: "Comparison",    text: "What is the difference between INSAT-3D and INSAT-3DR spacecraft?" },
  { tag: "Technical",     text: "What is the downlink data rate of INSAT-3DR imager?" },
  { tag: "Multi-mission", text: "Compare the payloads of OCEANSAT-2 and OCEANSAT-3" },
  { tag: "Specs",         text: "What is the orbital altitude and location of INSAT-3DR?" },
  { tag: "Overview",      text: "What are the objectives and payloads of MeghaTropiques?" },
  { tag: "Specs",         text: "What is the launch mass of INSAT-3DS?" },
  { tag: "Technical",     text: "What is the IFOV of the INSAT-3D sounder?" },
  { tag: "Cross-mission", text: "Which ISRO missions have a Data Relay Transponder?" },
  { tag: "Mission life",  text: "What is the mission life of INSAT-3D?" },
  { tag: "Intro",         text: "Introduction to KALPANA-1 satellite" },
];

const MISSIONS = [
  "INSAT-3DR","INSAT-3D","INSAT-3DS","INSAT-3A","KALPANA-1",
  "OCEANSAT-2","OCEANSAT-3","MeghaTropiques","SARAL-AltiKa","SCATSAT-1",
];

const WELCOME_CARDS = [
  {  text: "Compare missions side by side",   query: "What is the difference between INSAT-3D and INSAT-3DR?" },
  {  text: "Explore payload specifications", query: "What payloads does OCEANSAT-2 carry?" },
  {  text: "Look up orbital parameters",      query: "What is the orbital altitude of INSAT-3DS?" },
  { text: "Cross-mission capability search", query: "Which missions have search and rescue capabilities?" },
];

const VIZ_ICONS = {
  "3d_orbit":       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="11" ry="4.2" strokeDasharray="3 2"/><path d="M5.6 6.8A9.5 9.5 0 0 1 12 2.5a9.5 9.5 0 0 1 6.4 4.3" strokeDasharray="3 2"/></svg>,
  payload_specs:    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><circle cx="17.5" cy="17.5" r="3"/></svg>,
  comparison_chart: <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>,
};
const VIZ_LABELS = {
  "3d_orbit": "3D Orbit View", payload_specs: "Payload Dashboard", comparison_chart: "Comparison Chart",
};

// ─── CSS ──────────────────────────────────────────────────────────────────────
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&display=swap');

:root {
  --bg:            #03050a;
  --surface:       #060910;
  --glass:         rgba(8,13,22,0.75);
  --glass2:        rgba(5,9,17,0.88);
  --border:        rgba(0,210,255,0.1);
  --border-hi:     rgba(0,210,255,0.3);
  --cyan:          #00d2ff;
  --cyan-dim:      rgba(0,210,255,0.55);
  --cyan-glow:     rgba(0,210,255,0.18);
  --amber:         #ffaa00;
  --amber-dim:     rgba(255,170,0,0.6);
  --green:         #00ff88;
  --green-dim:     rgba(0,255,136,0.55);
  --red:           #ff4466;
  --text:          #d4e4f0;
  --text-dim:      #7a9bb5;
  --text-faint:    #3a5570;
  --user-bg:       rgba(0,50,80,0.42);
  --bot-bg:        rgba(0,22,12,0.48);
  --font-d:        'Orbitron', monospace;
  --font-m:        'IBM Plex Mono', monospace;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; background: var(--bg); color: var(--text); overflow: hidden; }

@keyframes spin      { to { transform: rotate(360deg); } }
@keyframes pulseDot  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.8)} }
@keyframes blink     { 0%,100%{opacity:.15;transform:scale(.8)} 50%{opacity:1;transform:scale(1)} }
@keyframes fadeUp    { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:translateY(0)} }
@keyframes aurora    { 0%,100%{opacity:.6;transform:scale(1)} 50%{opacity:.95;transform:scale(1.07)} }
@keyframes orbitA    { to{transform:rotate(360deg)} }
@keyframes orbitB    { to{transform:rotate(-360deg)} }
@keyframes sweep     { 0%{background-position:0 -100%} 100%{background-position:0 200%} }

/* ── Backgrounds ── */
.bg-deep   { position:fixed;inset:0;z-index:0;background:radial-gradient(ellipse 90% 60% at 20% 5%,rgba(0,38,76,.6) 0%,transparent 55%),radial-gradient(ellipse 70% 50% at 80% 85%,rgba(0,18,45,.5) 0%,transparent 55%),linear-gradient(175deg,#020408 0%,#030610 50%,#020509 100%); }
.bg-aurora { position:fixed;inset:0;z-index:0;pointer-events:none;background:radial-gradient(ellipse 140% 45% at 50% -5%,rgba(0,210,255,.05) 0%,transparent 55%),radial-gradient(ellipse 80% 35% at 10% 55%,rgba(0,255,136,.028) 0%,transparent 50%),radial-gradient(ellipse 60% 28% at 92% 72%,rgba(0,180,255,.038) 0%,transparent 50%);animation:aurora 14s ease-in-out infinite; }
.bg-grid   { position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.038;background-image:linear-gradient(rgba(0,210,255,.7) 1px,transparent 1px),linear-gradient(90deg,rgba(0,210,255,.7) 1px,transparent 1px);background-size:48px 48px; }
.bg-scan   { position:fixed;inset:0;z-index:0;pointer-events:none;opacity:.02;background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,210,255,.2) 2px,rgba(0,210,255,.2) 3px);animation:sweep 16s linear infinite; }
.bg-stars  { position:fixed;inset:0;z-index:0;pointer-events:none;background-image:radial-gradient(1px 1px at 11% 17%,rgba(255,255,255,.55) 0%,transparent 100%),radial-gradient(1px 1px at 83% 9%,rgba(255,255,255,.4) 0%,transparent 100%),radial-gradient(1px 1px at 47% 73%,rgba(255,255,255,.35) 0%,transparent 100%),radial-gradient(1px 1px at 7% 84%,rgba(255,255,255,.5) 0%,transparent 100%),radial-gradient(1px 1px at 91% 61%,rgba(255,255,255,.3) 0%,transparent 100%),radial-gradient(1px 1px at 32% 13%,rgba(255,255,255,.5) 0%,transparent 100%),radial-gradient(1.5px 1.5px at 72% 44%,rgba(0,210,255,.65) 0%,transparent 100%),radial-gradient(1.5px 1.5px at 23% 56%,rgba(0,210,255,.5) 0%,transparent 100%),radial-gradient(1px 1px at 56% 36%,rgba(255,255,255,.3) 0%,transparent 100%),radial-gradient(1px 1px at 17% 61%,rgba(0,255,136,.4) 0%,transparent 100%),radial-gradient(1px 1px at 89% 27%,rgba(255,255,255,.3) 0%,transparent 100%); }

/* ── App ── */
.app-root { position:relative;z-index:1;display:flex;flex-direction:column;height:100vh;overflow:hidden;font-family:var(--font-m); }

/* ── Header ── */
.header {
  display:flex;align-items:center;justify-content:space-between;
  padding:0 32px; height:64px; flex-shrink:0;
  background:var(--glass2); backdrop-filter:blur(28px) saturate(1.5);
  border-bottom:1px solid var(--border); position:relative; z-index:20;
}
.header::after {
  content:''; position:absolute; bottom:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg,transparent 0%,var(--cyan) 30%,var(--cyan-dim) 70%,transparent 100%);
  opacity:.28;
}

.logo { display:flex;align-items:center;gap:16px; }
.logo-emblem { position:relative;width:44px;height:44px;flex-shrink:0; }
.orbit-a { animation:orbitA 10s linear infinite;transform-origin:21px 21px; }
.orbit-b { animation:orbitB 7s linear infinite;transform-origin:21px 21px;position:absolute;inset:0; }

.logo-word { display:flex;flex-direction:column;gap:2px; }
.logo-name { font-family:var(--font-d);font-size:17px;font-weight:900;letter-spacing:.18em;color:var(--text);text-shadow:0 0 24px rgba(0,210,255,.45),0 0 48px rgba(0,210,255,.18); }
.logo-name span { color:var(--cyan); }
.logo-sub  { font-size:8.5px;letter-spacing:.22em;text-transform:uppercase;color:var(--text-faint); }

.hd-center {
  display:flex;align-items:center;gap:16px;
  position:absolute;left:50%;transform:translateX(-50%);
}
.telem {
  display:flex;align-items:center;gap:7px;
  padding:5px 13px;
  background:rgba(0,210,255,.03);
  border:1px solid var(--border);border-radius:4px;
}
.telem-k { font-size:8.5px;color:var(--text-faint);letter-spacing:.12em;text-transform:uppercase; }
.telem-v { font-size:10px;color:var(--cyan);letter-spacing:.08em; }
.telem-sep { width:1px;height:13px;background:var(--border); }

.hd-right { display:flex;align-items:center;gap:12px; }

.status-chip {
  display:flex;align-items:center;gap:7px;padding:5px 14px;
  background:rgba(0,255,136,.04);border:1px solid rgba(0,255,136,.15);border-radius:20px;
  font-size:9.5px;color:var(--green-dim);letter-spacing:.1em;text-transform:uppercase;
}
.status-dot { width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 10px var(--green);animation:pulseDot 2.2s ease-in-out infinite; }

.new-chat-btn {
  display:flex;align-items:center;gap:6px;padding:6px 15px;
  background:transparent;border:1px solid var(--border-hi);border-radius:4px;
  color:var(--text-dim);font-family:var(--font-m);font-size:9.5px;
  letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:all .18s;
}
.new-chat-btn:hover { background:var(--cyan-glow);border-color:var(--cyan);color:var(--cyan);box-shadow:0 0 18px rgba(0,210,255,.12); }

/* ── Layout ── */
.main { display:flex;flex:1;overflow:hidden; }

/* ── Sidebar ── */
.sidebar {
  width:274px;flex-shrink:0;
  background:var(--glass2);backdrop-filter:blur(22px);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow:hidden;position:relative;
}
.sidebar::after {
  content:'';position:absolute;top:0;right:-1px;bottom:0;width:1px;
  background:linear-gradient(180deg,transparent 0%,var(--cyan) 35%,var(--cyan-dim) 65%,transparent 100%);
  opacity:.15;pointer-events:none;
}

.sb-hdr {
  padding:15px 18px 13px;border-bottom:1px solid var(--border);flex-shrink:0;
  display:flex;align-items:center;gap:8px;
}
.sb-hdr-icon { color:var(--cyan-dim); }
.sb-hdr-text { font-family:var(--font-d);font-size:8.5px;font-weight:700;color:var(--text-faint);letter-spacing:.22em;text-transform:uppercase; }

.query-list { padding:10px 11px;display:flex;flex-direction:column;gap:5px;overflow-y:auto;flex:1; }
.query-list::-webkit-scrollbar { width:3px; }
.query-list::-webkit-scrollbar-thumb { background:rgba(0,210,255,.13);border-radius:2px; }

.query-chip {
  padding:10px 12px 10px 11px;
  background:rgba(0,210,255,.022);
  border:1px solid rgba(0,210,255,.07);
  border-left:2px solid transparent;
  border-radius:5px;font-family:var(--font-m);font-size:10.5px;color:var(--text-dim);
  cursor:pointer;transition:all .16s;text-align:left;line-height:1.5;
  position:relative;overflow:hidden;
}
.query-chip::after {
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,rgba(0,210,255,.07),transparent);
  opacity:0;transition:opacity .16s;
}
.query-chip:hover { border-left-color:var(--cyan);border-color:var(--border-hi);color:var(--text);transform:translateX(2px); }
.query-chip:hover::after { opacity:1; }
.chip-tag { display:block;font-size:8px;color:var(--text-faint);margin-bottom:4px;letter-spacing:.14em;text-transform:uppercase; }

.missions-sec { border-top:1px solid var(--border);padding:13px 11px;flex-shrink:0; }
.missions-hdr { display:flex;align-items:center;gap:7px;font-family:var(--font-d);font-size:8.5px;font-weight:700;color:var(--text-faint);letter-spacing:.2em;text-transform:uppercase;margin-bottom:10px; }
.mission-tags { display:flex;flex-wrap:wrap;gap:5px; }
.mission-tag {
  padding:3px 9px;
  background:rgba(255,170,0,.025);
  border:1px solid rgba(255,170,0,.14);border-radius:3px;
  font-size:9px;color:var(--amber-dim);cursor:pointer;transition:all .15s;
  font-family:var(--font-m);letter-spacing:.04em;
}
.mission-tag:hover { background:rgba(255,170,0,.08);border-color:var(--amber);color:var(--amber);box-shadow:0 0 10px rgba(255,170,0,.1); }

/* ── Chat ── */
.chat-area { flex:1;display:flex;flex-direction:column;overflow:hidden; }

.messages {
  flex:1;overflow-y:auto;padding:28px 36px;
  display:flex;flex-direction:column;gap:22px;scroll-behavior:smooth;
}
.messages::-webkit-scrollbar { width:4px; }
.messages::-webkit-scrollbar-thumb { background:rgba(0,210,255,.12);border-radius:2px; }

/* ── Welcome ── */
.welcome {
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  flex:1;text-align:center;padding:40px 20px;gap:18px;min-height:340px;
}
.welcome-emblem { position:relative;margin-bottom:4px; }
.w-ring-a { animation:orbitA 18s linear infinite;transform-origin:45px 45px; }
.w-ring-b { animation:orbitB 11s linear infinite;transform-origin:45px 45px; }
.welcome-title {
  font-family:var(--font-d);font-size:36px;font-weight:900;letter-spacing:.26em;
  background:linear-gradient(135deg,var(--cyan) 0%,#7ef9ff 40%,var(--text) 72%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  filter:drop-shadow(0 0 28px rgba(0,210,255,.38));
}
.welcome-div { width:110px;height:1px;background:linear-gradient(90deg,transparent,var(--cyan-dim),transparent); }
.welcome-sub { font-size:11.5px;color:var(--text-dim);max-width:460px;line-height:1.8;letter-spacing:.025em; }

.welcome-grid { display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:6px;width:100%;max-width:500px; }
.welcome-card {
  padding:16px;background:rgba(0,210,255,.022);
  border:1px solid rgba(0,210,255,.09);border-radius:8px;
  text-align:left;cursor:pointer;transition:all .18s;position:relative;overflow:hidden;
}
.welcome-card::after {
  content:'';position:absolute;bottom:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--cyan),transparent);
  opacity:0;transition:opacity .18s;
}
.welcome-card:hover { background:rgba(0,210,255,.055);border-color:rgba(0,210,255,.3);transform:translateY(-2px);box-shadow:0 8px 32px rgba(0,210,255,.07); }
.welcome-card:hover::after { opacity:.55; }
.welcome-card-icon { font-size:20px;margin-bottom:8px; }
.welcome-card-text { font-size:11px;color:var(--text-dim);line-height:1.55; }

/* ── Messages ── */
.message {
  display:flex;flex-direction:column;gap:7px;
  animation:fadeUp .3s cubic-bezier(.22,.8,.4,1) forwards;
  opacity:0;transform:translateY(14px);
}
.message.user { align-items:flex-end; }
.message.bot  { align-items:flex-start; }

.msg-label { font-family:var(--font-d);font-size:8px;letter-spacing:.22em;text-transform:uppercase;padding:0 6px; }
.message.user .msg-label { color:var(--cyan-dim); }
.message.bot  .msg-label { color:var(--green-dim); }

.msg-bubble {
  max-width:74%;padding:15px 20px;border-radius:10px;
  font-size:13px;line-height:1.76;letter-spacing:.01em;
  position:relative;overflow:hidden;
  color: var(--text);
}
.message.user .msg-bubble {
  background:var(--user-bg);border:1px solid rgba(0,210,255,.2);
  border-bottom-right-radius:2px;backdrop-filter:blur(12px);
}
.message.user .msg-bubble::before {
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(0,210,255,.45),transparent);
}
.message.bot .msg-bubble {
  background:var(--bot-bg);border:1px solid rgba(0,255,136,.11);
  border-bottom-left-radius:2px;backdrop-filter:blur(12px);white-space:pre-wrap;
}
.message.bot .msg-bubble::before {
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,rgba(0,255,136,.3),transparent 65%);
}

.citation {
  display:inline-flex;align-items:center;gap:5px;margin:8px 4px 0 0;
  padding:3px 10px;background:rgba(0,210,255,.07);
  border:1px solid rgba(0,210,255,.22);border-radius:3px;
  font-size:10px;color:var(--cyan);letter-spacing:.04em;
}

/* ── Thinking ── */
.thinking {
  display:flex;align-items:center;gap:12px;padding:14px 18px;
  background:var(--bot-bg);border:1px solid rgba(0,255,136,.11);
  border-radius:10px;border-bottom-left-radius:2px;backdrop-filter:blur(12px);
}
.thinking-dots { display:flex;gap:5px; }
.thinking-dots span { width:5px;height:5px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:blink 1.3s ease-in-out infinite; }
.thinking-dots span:nth-child(2){animation-delay:.22s}
.thinking-dots span:nth-child(3){animation-delay:.44s}
.thinking-label { font-size:10px;color:var(--text-faint);letter-spacing:.07em; }

/* ── Error ── */
.error-bubble {
  max-width:74%;padding:13px 18px;
  background:rgba(255,68,102,.06);border:1px solid rgba(255,68,102,.22);border-radius:8px;
  font-size:12.5px;color:#ff8099;line-height:1.65;
}

/* ── Rewrite ── */
.rewrite-pill {
  display:flex;align-items:center;gap:6px;padding:4px 12px;
  font-size:10px;color:var(--text-faint);max-width:74%;
  background:rgba(0,210,255,.025);border:1px solid rgba(0,210,255,.08);border-radius:3px;
}
.rewrite-pill em { font-style:normal;color:var(--cyan-dim); }

/* ── Debug ── */
.debug-panel {
  max-width:74%;background:rgba(0,0,0,.52);border:1px solid rgba(0,210,255,.1);
  border-radius:7px;padding:11px 14px;backdrop-filter:blur(8px);
}
.debug-title { display:flex;align-items:center;gap:6px;font-family:var(--font-d);font-size:8px;color:var(--text-faint);letter-spacing:.18em;text-transform:uppercase;margin-bottom:9px; }
.debug-chunks { display:flex;flex-direction:column;gap:4px; }
.debug-chunk { display:flex;align-items:center;gap:8px;font-size:10px;padding:5px 9px;background:rgba(0,210,255,.022);border:1px solid rgba(0,210,255,.07);border-radius:4px; }
.debug-mission { color:var(--cyan);font-weight:600;white-space:nowrap;min-width:88px; }
.debug-section  { color:var(--amber-dim);white-space:nowrap;flex:1;overflow:hidden;text-overflow:ellipsis; }
.dist-bar { width:55px;height:3px;background:var(--border);border-radius:2px;overflow:hidden;margin-left:auto;flex-shrink:0; }
.dist-fill { height:100%;border-radius:2px; }
.debug-dist { font-size:9px;white-space:nowrap;flex-shrink:0;width:46px;text-align:right; }
.chunk-url { color:var(--cyan-dim);text-decoration:none;font-size:10.5px;opacity:.7;transition:opacity .15s;flex-shrink:0; }
.chunk-url:hover{opacity:1}

/* ── Sources ── */
.sources-panel { max-width:74%;padding:10px 14px;background:rgba(0,0,0,.36);border:1px solid rgba(0,210,255,.1);border-radius:6px;backdrop-filter:blur(8px); }
.sources-title { display:flex;align-items:center;gap:6px;font-family:var(--font-d);font-size:8px;color:var(--text-faint);letter-spacing:.18em;text-transform:uppercase;margin-bottom:8px; }
.sources-list { display:flex;flex-wrap:wrap;gap:6px; }
.source-link { padding:3px 10px;background:rgba(0,210,255,.05);border:1px solid rgba(0,210,255,.18);border-radius:3px;font-size:10px;color:var(--cyan-dim);text-decoration:none;transition:all .15s;font-family:var(--font-m); }
.source-link:hover { background:rgba(0,210,255,.12);border-color:var(--cyan);color:var(--cyan); }

/* ── Viz btns ── */
.viz-buttons { display:flex;flex-wrap:wrap;gap:8px;max-width:74%;margin-top:4px; }
.viz-btn {
  display:flex;align-items:center;gap:7px;padding:7px 14px;
  background:rgba(0,210,255,.035);border:1px solid rgba(0,210,255,.2);border-radius:5px;
  color:var(--cyan-dim);font-family:var(--font-m);font-size:10px;cursor:pointer;transition:all .16s;
  letter-spacing:.04em;position:relative;overflow:hidden;
}
.viz-btn::before { content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(0,210,255,.07),transparent);transform:translateX(-100%);transition:transform .32s; }
.viz-btn:hover { background:rgba(0,210,255,.1);border-color:var(--cyan);color:var(--cyan);box-shadow:0 0 16px rgba(0,210,255,.1); }
.viz-btn:hover::before { transform:translateX(100%); }
.viz-btn:disabled { opacity:.38;cursor:not-allowed; }
.viz-spin { animation:spin .85s linear infinite; }

/* ── Input ── */
.input-area {
  padding:18px 36px 20px;
  border-top:1px solid var(--border);
  background:var(--glass2);backdrop-filter:blur(28px);flex-shrink:0;position:relative;
}
.input-area::before {
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent 0%,var(--cyan-dim) 50%,transparent 100%);opacity:.2;
}
.debug-toggle { display:flex;align-items:center;gap:8px;font-size:10px;color:var(--text-faint);cursor:pointer;user-select:none;margin-bottom:12px;letter-spacing:.03em; }
.debug-toggle input { accent-color:var(--cyan); }

.input-row { display:flex;gap:10px;align-items:flex-end; }
.input-wrap {
  flex:1;position:relative;background:rgba(0,210,255,.025);
  border:1px solid var(--border);border-radius:10px;
  padding:13px 18px 10px;transition:border-color .2s,box-shadow .2s;
}
.input-wrap:focus-within { border-color:rgba(0,210,255,.4);box-shadow:0 0 0 3px rgba(0,210,255,.055),0 0 24px rgba(0,210,255,.07); }

.q-textarea {
  width:100%;background:transparent;border:none;outline:none;
  color:var(--text);font-family:var(--font-m);font-size:13px;
  resize:none;line-height:1.6;max-height:120px;overflow-y:auto;letter-spacing:.015em;
}
.q-textarea::placeholder { color:var(--text-faint); }

.input-footer { display:flex;align-items:center;justify-content:space-between;margin-top:7px; }
.input-hint  { font-size:9px;color:var(--text-faint);letter-spacing:.07em; }
.input-chars { font-size:9px;color:var(--text-faint);letter-spacing:.04em; }

.send-btn {
  width:50px;height:50px;flex-shrink:0;
  background:linear-gradient(135deg,rgba(0,210,255,.22),rgba(0,210,255,.1));
  border:1px solid rgba(0,210,255,.38);border-radius:10px;
  cursor:pointer;display:flex;align-items:center;justify-content:center;
  color:var(--cyan);transition:all .18s;
  box-shadow:0 0 16px rgba(0,210,255,.1);
}
.send-btn:hover { background:linear-gradient(135deg,rgba(0,210,255,.35),rgba(0,210,255,.18));border-color:var(--cyan);box-shadow:0 0 26px rgba(0,210,255,.22),inset 0 0 14px rgba(0,210,255,.05);transform:translateY(-1px); }
.send-btn:active { transform:translateY(0) scale(.97); }
.send-btn:disabled { background:rgba(255,255,255,.02);border-color:var(--border);color:var(--text-faint);cursor:not-allowed;transform:none;box-shadow:none; }

/* ── Viz Panel ── */
.viz-panel {
  width:45vw;max-width:800px;min-width:350px;
  background:var(--glass2);backdrop-filter:blur(28px);
  border-left:1px solid var(--border-hi);
  display:flex;flex-direction:column;overflow:hidden;
  box-shadow:-20px 0 80px rgba(0,210,255,.04);
  animation:slideIn .3s cubic-bezier(.22,.8,.4,1) forwards;
  z-index: 50;
}
@keyframes slideIn { from{opacity:0;transform:translateX(30px)} to{opacity:1;transform:translateX(0)} }
.viz-modal-hdr {
  display:flex;align-items:center;justify-content:space-between;
  padding:13px 22px;background:rgba(0,210,255,.025);
  border-bottom:1px solid var(--border);flex-shrink:0;position:relative;
}
.viz-modal-hdr::after { content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--cyan-dim),transparent);opacity:.3; }
.viz-modal-title { display:flex;align-items:center;gap:10px;font-family:var(--font-d);font-size:11px;font-weight:700;color:var(--cyan);letter-spacing:.15em;text-transform:uppercase; }
.viz-modal-actions { display:flex;align-items:center;gap:8px; }
.viz-act-btn { display:flex;align-items:center;gap:5px;padding:5px 12px;background:transparent;border:1px solid var(--border);border-radius:4px;color:var(--text-dim);font-family:var(--font-m);font-size:9px;cursor:pointer;transition:all .15s;letter-spacing:.07em; }
.viz-act-btn:hover { border-color:var(--border-hi);color:var(--cyan); }
.viz-x { width:30px;height:30px;background:transparent;border:1px solid var(--border);border-radius:4px;color:var(--text-dim);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;font-size:14px; }
.viz-x:hover { border-color:rgba(255,68,102,.4);color:#ff8099; }
.viz-body { flex:1;overflow:hidden;position:relative; }
.viz-iframe { width:100%;height:100%;border:none;background:#04070e; }
.viz-state { position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;background:rgba(4,7,14,.97); }
.viz-ring svg { animation:orbitA 2.5s linear infinite; }
.viz-loading-lbl { font-family:var(--font-d);font-size:10.5px;color:var(--text-faint);letter-spacing:.22em; }
.viz-err-msg { font-size:12px;color:#ff8099;max-width:440px;text-align:center;line-height:1.65; }
.viz-retry { padding:7px 20px;background:transparent;border:1px solid rgba(255,68,102,.32);border-radius:4px;color:#ff8099;font-family:var(--font-m);font-size:10px;cursor:pointer;transition:all .15s;letter-spacing:.06em; }
.viz-retry:hover { background:rgba(255,68,102,.07); }
`;

// ─── Icons / SVG helpers ──────────────────────────────────────────────────────

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);

const TrashIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
  </svg>
);

function SpinSVG({ sz = 13 }) {
  return (
    <svg className="viz-spin" width={sz} height={sz} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
  );
}

function LogoEmblem() {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
      <circle cx="22" cy="22" r="20" stroke="rgba(0,210,255,0.1)" strokeWidth="1.5"/>
      <ellipse cx="22" cy="22" rx="20" ry="8.5"
        stroke="rgba(0,210,255,0.6)" strokeWidth="1.5" strokeDasharray="4 3" className="orbit-a"/>
      <ellipse cx="22" cy="22" rx="12" ry="20"
        stroke="rgba(0,210,255,0.2)" strokeWidth="1" strokeDasharray="3 4" className="orbit-b"/>
      <circle cx="22" cy="22" r="3.8" fill="rgba(0,210,255,0.92)"/>
      <circle cx="22" cy="22" r="1.6" fill="#04070e"/>
      <circle cx="40" cy="22" r="2.6" fill="#ffaa00"/>
    </svg>
  );
}

function WelcomeEmblem() {
  return (
    <svg width="92" height="92" viewBox="0 0 92 92" fill="none">
      <circle cx="46" cy="46" r="43" stroke="rgba(0,210,255,0.07)" strokeWidth="2"/>
      <ellipse cx="46" cy="46" rx="43" ry="18"
        stroke="rgba(0,210,255,0.5)" strokeWidth="1.5" strokeDasharray="5 3" opacity=".7" className="w-ring-a"/>
      <ellipse cx="46" cy="46" rx="30" ry="43"
        stroke="rgba(0,210,255,0.2)" strokeWidth="1" strokeDasharray="4 5" opacity=".5" className="w-ring-b"/>
      <circle cx="46" cy="46" r="7.5" fill="rgba(0,210,255,0.88)"/>
      <circle cx="46" cy="46" r="3.5" fill="#03050a"/>
      <circle cx="87" cy="46" r="4.5" fill="#ffaa00"/>
      <circle cx="26" cy="8"  r="2.5" fill="rgba(0,255,136,0.82)"/>
      <circle cx="75" cy="80" r="2"   fill="rgba(0,210,255,0.6)"/>
    </svg>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function DebugPanel({ chunks }) {
  return (
    <div className="debug-panel">
      <div className="debug-title">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        Retrieved {chunks.length} chunks
      </div>
      <div className="debug-chunks">
        {chunks.map((c, i) => {
          const pct = Math.max(0, Math.min(100, (1 - c.distance) * 100));
          const col = c.distance < 0.35 ? "var(--green)" : c.distance < 0.55 ? "var(--cyan)" : "var(--amber)";
          return (
            <div key={i} className="debug-chunk">
              <span className="debug-mission">{c.mission}</span>
              <span className="debug-section">{c.section}</span>
              {c.source_url && <a href={c.source_url} target="_blank" rel="noreferrer" className="chunk-url" title={c.source_url}>↗</a>}
              <div className="dist-bar"><div className="dist-fill" style={{ width: `${pct}%`, background: col }}/></div>
              <span className="debug-dist" style={{ color: col }}>{c.distance.toFixed(4)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SourcesPanel({ sources }) {
  return (
    <div className="sources-panel">
      <div className="sources-title">
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
        </svg>
        Sources
      </div>
      <div className="sources-list">
        {sources.map((url, i) => (
          <a key={i} href={url} target="_blank" rel="noreferrer" className="source-link">
            {url.split("/").filter(Boolean).slice(-2).join(" › ")}
          </a>
        ))}
      </div>
    </div>
  );
}

function VizButtons({ buttons, userQuery, answer, onTrigger }) {
  const [loading, setLoading] = useState(null);
  const handle = async (btn) => {
    if (loading) return;
    setLoading(btn.type);
    await onTrigger(btn.type, btn.label, userQuery, answer);
    setLoading(null);
  };
  return (
    <div className="viz-buttons">
      {buttons.map(btn => {
        const isL = loading === btn.type;
        return (
          <button key={btn.type} className={`viz-btn${isL ? " loading" : ""}`}
            disabled={!!loading} onClick={() => handle(btn)}>
            {isL ? <SpinSVG sz={13}/> : VIZ_ICONS[btn.type]}
            <span>{isL ? "Generating…" : btn.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function BotMessage({ content, chunks, sources, rewrittenQuery, vizButtons, showDebug, onVizTrigger, userQuery }) {
  const html = content
    .replace(/\[Mission: ([^\]]+)\]/g, '<span class="citation">📍 $1</span>')
    .replace(/\n/g, "<br/>");
  return (
    <div className="message bot">
      <div className="msg-label">▸ KALPANA</div>
      <div className="msg-bubble" dangerouslySetInnerHTML={{ __html: html }}/>
      {rewrittenQuery && (
        <div className="rewrite-pill">
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-3.63"/>
          </svg>
          Searched as:&nbsp;<em>{rewrittenQuery}</em>
        </div>
      )}
      {showDebug && chunks?.length > 0 && <DebugPanel chunks={chunks}/>}
      {sources?.length > 0 && <SourcesPanel sources={sources}/>}
      {vizButtons?.length > 0 && <VizButtons buttons={vizButtons} userQuery={userQuery} answer={content} onTrigger={onVizTrigger}/>}
    </div>
  );
}

// ─── Viz Panel ────────────────────────────────────────────────────────────────

function VizPanel({ state, onClose, onRetry }) {
  const { isOpen, label, html, error, isLoading, currentQuery, currentAnswer, currentType } = state;
  const ifrRef = useRef(null);

  useEffect(() => {
    if (!isOpen) setTimeout(() => { if (ifrRef.current) ifrRef.current.srcdoc = ""; }, 250);
  }, [isOpen]);

  if (!isOpen) return null;

  const openNew  = () => html && window.open(URL.createObjectURL(new Blob([html], { type: "text/html" })), "_blank");
  const download = () => {
    if (!html) return;
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([html], { type: "text/html" })),
      download: `kalpana_${currentType}_${Date.now()}.html`,
    });
    a.click();
  };

  return (
    <div className="viz-panel">
      <div className="viz-modal-hdr">
        <div className="viz-modal-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
            <line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/>
            <line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/>
          </svg>
          {label}
        </div>
        <div className="viz-modal-actions">
          <button className="viz-act-btn" onClick={openNew} disabled={!html || isLoading}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            New tab
          </button>
          <button className="viz-act-btn" onClick={download} disabled={!html || isLoading}>
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download
          </button>
          <button className="viz-x" onClick={onClose}>✕</button>
        </div>
      </div>
      <div className="viz-body">
        {isLoading && (
          <div className="viz-state">
            <div className="viz-ring">
              <svg width="62" height="62" viewBox="0 0 62 62" fill="none">
                <circle cx="31" cy="31" r="29" stroke="rgba(0,210,255,0.1)" strokeWidth="2"/>
                <ellipse cx="31" cy="31" rx="29" ry="12" stroke="rgba(0,210,255,0.7)" strokeWidth="2" strokeDasharray="6 4"/>
                <circle cx="31" cy="31" r="4.5" fill="rgba(0,210,255,0.9)"/>
                <circle cx="58" cy="31" r="3" fill="#ffaa00"/>
              </svg>
            </div>
            <div className="viz-loading-lbl">Building Visualization…</div>
          </div>
        )}
        {html && !isLoading && !error && (
    <iframe
      ref={ifrRef}
      className="viz-iframe"
      srcDoc={html}
      sandbox="allow-scripts allow-same-origin"
      title="Visualization"
    />
  )}
        {error && !isLoading && (
          <div className="viz-state">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--red)" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div className="viz-err-msg">{error}</div>
            <button className="viz-retry" onClick={() => onRetry(currentQuery, currentAnswer, currentType)}>
              Retry
            </button>
          </div>
        )}
        {html && !isLoading && !error && (
          <iframe ref={ifrRef} className="viz-iframe" srcDoc={html}
            sandbox="allow-scripts allow-same-origin" title="Visualization"/>
        )}
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function KalpanaApp() {
  const [messages,   setMessages]   = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading,  setIsLoading]  = useState(false);
  const [showDebug,  setShowDebug]  = useState(true);
  const [history,    setHistory]    = useState([]);
  const [vizState,   setVizState]   = useState({
    isOpen: false, label: "", html: "", error: "", isLoading: false,
    currentQuery: "", currentAnswer: "", currentType: "",
  });

  const bottomRef = useRef(null);
  const textaRef  = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleSend = useCallback(async () => {
    const query = inputValue.trim();
    if (!query || isLoading) return;
    setInputValue("");
    setIsLoading(true);
    setMessages(p => [...p, { id: Date.now(), role: "user", content: query }]);
    const hist = [...history, { role: "user", content: query }];
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, session_id: SESSION_ID, history: hist.slice(-MAX_HISTORY_TURNS).slice(0, -1) }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || "Server error"); }
      const data = await res.json();
      setMessages(p => [...p, {
        id: Date.now() + 1, role: "bot",
        content: data.answer, chunks: data.chunks || [], sources: data.sources || [],
        rewrittenQuery: data.rewritten_query || null, vizButtons: data.viz_buttons || [], userQuery: query,
      }]);
      setHistory(h => [...h, { role: "user", content: query }, { role: "assistant", content: data.answer }].slice(-MAX_HISTORY_TURNS));
    } catch (err) {
      const msg = err.message.includes("fetch")
        ? "Cannot connect to KALPANA API at localhost:8000. Make sure your FastAPI server is running."
        : `Error: ${err.message}`;
      setMessages(p => [...p, { id: Date.now() + 1, role: "error", content: msg }]);
    } finally {
      setIsLoading(false);
      textaRef.current?.focus();
    }
  }, [inputValue, isLoading, history]);

  const handleKey   = e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const useQuery    = t  => { setInputValue(t); textaRef.current?.focus(); };
  const handleClear = () => {
    setMessages([]); setHistory([]);
    fetch(`${API_BASE}/memory/clear/${SESSION_ID}`, { method: "POST" }).catch(() => {});
  };

  // Visualization trigger — no Gemini key check needed; backend is self-contained
  const handleVizTrigger = useCallback(async (vizType, vizLabel, query, answer) => {
    const label = vizLabel || VIZ_LABELS[vizType] || "Visualization";
    setVizState({
      isOpen: true, label, html: "", error: "", isLoading: true,
      currentQuery: query, currentAnswer: answer, currentType: vizType,
    });
    try {
      const res = await fetch(`${API_BASE}/visualize`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, answer, viz_type: vizType }),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || "Visualization error");
      }
      const data = await res.json();
      setVizState(p => ({ ...p, html: data.html, isLoading: false }));
    } catch (err) {
      setVizState(p => ({ ...p, error: err.message, isLoading: false }));
    }
  }, []);

  const handleVizRetry = (q, a, t) => handleVizTrigger(t, VIZ_LABELS[t], q, a);

  // Live UTC clock
  const [utc, setUtc] = useState(() => new Date().toUTCString().slice(17, 25));
  useEffect(() => {
    const id = setInterval(() => setUtc(new Date().toUTCString().slice(17, 25)), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <>
      <style>{CSS}</style>

      {/* Backgrounds */}
      <div className="bg-deep"/>
      <div className="bg-aurora"/>
      <div className="bg-grid"/>
      <div className="bg-scan"/>
      <div className="bg-stars"/>

      <div className="app-root">

        {/* ── Header ── */}
        <header className="header">
          <div className="logo">
            <div className="logo-emblem"><LogoEmblem/></div>
            <div className="logo-word">
              <div className="logo-name"><span>KALPANA</span></div>
              <div className="logo-sub">AI Assistant · MOSDAC Portal · ISRO</div>
            </div>
          </div>

          <div className="hd-center">
            <div className="telem">
              <span className="telem-k">Missions</span>
              <div className="telem-sep"/>
              <span className="telem-v">10 indexed</span>
            </div>
            <div className="telem">
              <span className="telem-k">Session</span>
              <div className="telem-sep"/>
              <span className="telem-v">{SESSION_ID.slice(-6).toUpperCase()}</span>
            </div>
            <div className="telem">
              <span className="telem-k">UTC</span>
              <div className="telem-sep"/>
              <span className="telem-v">{utc}</span>
            </div>
          </div>

          <div className="hd-right">
            <div className="status-chip">
              <div className="status-dot"/>
              System Online
            </div>
            <button className="new-chat-btn" onClick={handleClear}>
              <TrashIcon/>&nbsp;New Chat
            </button>
          </div>
        </header>

        <div className="main">

          {/* ── Sidebar ── */}
          <aside className="sidebar">
            <div className="sb-hdr">
              <svg className="sb-hdr-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <span className="sb-hdr-text">Query Templates</span>
            </div>

            <div className="query-list">
              {QUERY_TEMPLATES.map((q, i) => (
                <button key={i} className="query-chip" onClick={() => useQuery(q.text)}>
                  <span className="chip-tag">{q.tag}</span>
                  {q.text}
                </button>
              ))}
            </div>

            <div className="missions-sec">
              <div className="missions-hdr">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
                  <line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/>
                  <line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/>
                </svg>
                Indexed Missions
              </div>
              <div className="mission-tags">
                {MISSIONS.map(m => (
                  <button key={m} className="mission-tag" onClick={() => useQuery(`Tell me about ${m}`)}>
                    {m}
                  </button>
                ))}
              </div>
            </div>
          </aside>

          {/* ── Chat ── */}
          <div className="chat-area">
            <div className="messages">

              {messages.length === 0 && (
                <div className="welcome">
                  <div className="welcome-emblem"><WelcomeEmblem/></div>
                  <div className="welcome-title">KALPANA</div>
                  <div className="welcome-div"/>
                  <p className="welcome-sub">
                    AI Mission Intelligence for the MOSDAC Portal — inspired by astronaut Kalpana Chawla.
                    Query satellite data across 10 ISRO missions using natural language.
                  </p>
                  <div className="welcome-grid">
                    {WELCOME_CARDS.map((c, i) => (
                      <button key={i} className="welcome-card" onClick={() => useQuery(c.query)}>
                        <div className="welcome-card-icon">{c.icon}</div>
                        <div className="welcome-card-text">{c.text}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map(msg => {
                if (msg.role === "user") return (
                  <div key={msg.id} className="message user">
                    <div className="msg-label">▸ You</div>
                    <div className="msg-bubble">{msg.content}</div>
                  </div>
                );
                if (msg.role === "error") return (
                  <div key={msg.id} className="message bot">
                    <div className="msg-label" style={{ color: "var(--red)" }}>▸ System</div>
                    <div className="error-bubble">{msg.content}</div>
                  </div>
                );
                return (
                  <BotMessage key={msg.id} content={msg.content} chunks={msg.chunks}
                    sources={msg.sources} rewrittenQuery={msg.rewrittenQuery}
                    vizButtons={msg.vizButtons} showDebug={showDebug}
                    onVizTrigger={handleVizTrigger} userQuery={msg.userQuery}/>
                );
              })}

              {isLoading && (
                <div className="message bot">
                  <div className="msg-label">▸ KALPANA</div>
                  <div className="thinking">
                    <div className="thinking-dots"><span/><span/><span/></div>
                    <span className="thinking-label">Processing query…</span>
                  </div>
                </div>
              )}

              <div ref={bottomRef}/>
            </div>

            {/* ── Input ── */}
            <div className="input-area">
              <label className="debug-toggle">
                <input type="checkbox" checked={showDebug} onChange={e => setShowDebug(e.target.checked)}/>
                Show retrieval debug (chunks + distances)
              </label>
              <div className="input-row">
                <div className="input-wrap">
                  <textarea
                    ref={textaRef}
                    className="q-textarea"
                    rows={1}
                    placeholder="Ask KALPANA anything about ISRO satellite missions…"
                    value={inputValue}
                    onChange={e => {
                      setInputValue(e.target.value);
                      e.target.style.height = "auto";
                      e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
                    }}
                    onKeyDown={handleKey}
                  />
                  <div className="input-footer">
                    <span className="input-hint">Enter to send · Shift+Enter for new line</span>
                    {inputValue.length > 0 && <span className="input-chars">{inputValue.length} chars</span>}
                  </div>
                </div>
                <button className="send-btn" disabled={isLoading || !inputValue.trim()} onClick={handleSend}>
                  <SendIcon/>
                </button>
              </div>
            </div>
          </div>

          {/* ── Viz Panel ── */}
          <VizPanel
            state={vizState}
            onClose={() => setVizState(p => ({ ...p, isOpen: false }))}
            onRetry={handleVizRetry}
          />
        </div>
      </div>
    </>
  );
}