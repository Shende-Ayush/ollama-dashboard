import React, { useEffect, useRef, useState } from "react";
import { api, wsUrl } from "../api/client";
import { useToast } from "../hooks/useToast";

interface Line { text: string; type: "input"|"output"|"system"|"error"; }

const FALLBACK_SUGGESTIONS = [
  { cmd:"ollama ps",           desc:"List running models" },
  { cmd:"ollama list",         desc:"List installed models" },
  { cmd:"ollama version",      desc:"Show Ollama version" },
  { cmd:"ollama pull llama3.2", desc:"Pull latest Llama 3.2" },
  { cmd:"ollama show llama3.2",desc:"Show model details" },
];

export function TerminalPage() {
  const [lines, setLines]     = useState<Line[]>([{ text:"Ollama Terminal — type an Ollama command and press Enter", type:"system" }]);
  const [input, setInput]     = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const [connected, setConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"connecting"|"connected"|"disconnected">("connecting");
  const [connectError, setConnectError] = useState<string | null>(null);
  const [running, setRunning]     = useState(false);
  const [cmdHistory, setCmdHistory] = useState<any[]>([]);
  const [historyPage, setHistoryPage] = useState({ pg_no:1, pg_size:10, total_records:0, total_pg:0 });
  const [suggestions, setSuggestions] = useState(FALLBACK_SUGGESTIONS);
  const [activeRequestId, setActiveRequestId] = useState("");
  const wsRef   = useRef<WebSocket|null>(null);
  const outRef  = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const addLine = (text: string, type: Line["type"] = "output") => {
    setLines(p => [...p, { text, type }]);
    setTimeout(() => outRef.current?.scrollTo(0, outRef.current.scrollHeight), 0);
  };

  const connect = () => {
    wsRef.current?.close();
    setConnectionStatus("connecting");
    setConnectError(null);
    const ws = new WebSocket(wsUrl("/commands/stream"));
    wsRef.current = ws;
    ws.onopen = () => {
      setConnected(true);
      setConnectionStatus("connected");
      setConnectError(null);
      addLine("● Connected","system");
    };
    ws.onclose = () => {
      setConnected(false);
      setConnectionStatus("disconnected");
      addLine("○ Disconnected","system");
    };
    ws.onerror = () => {
      setConnectionStatus("disconnected");
      setConnectError("WebSocket connection failed");
      addLine("WebSocket error","error");
    };
    ws.onmessage = evt => {
      try {
        const d = JSON.parse(evt.data);
        if (d.event_type==="connected") return;
        if (d.event_type==="started")   { setRunning(true); setActiveRequestId(d.request_id||""); addLine(`▶ ${d.payload?.command||""}`, "system"); }
        if (d.event_type==="output")    { addLine(d.payload?.line||"", "output"); }
        if (d.event_type==="done")      { setRunning(false); setActiveRequestId(""); addLine(`✓ Exit ${d.payload?.exit_code??0}`, "system"); loadHistory(); }
        if (d.event_type==="error")     { setRunning(false); setActiveRequestId(""); addLine(`✕ ${d.payload?.message||"Error"}`, "error"); loadHistory(); }
        if (d.event_type==="stopped")   { setRunning(false); setActiveRequestId(""); addLine("⏹ Stopped", "system"); loadHistory(); }
      } catch {}
    };
  };

  const loadHistory = () => {
    api.get<any>(`/commands/history?pg_no=${historyPage.pg_no}&pg_size=${historyPage.pg_size}`)
      .then(r => { setCmdHistory(r.items||[]); if (r.page) setHistoryPage(r.page); })
      .catch(()=>{});
  };

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, []);

  useEffect(() => { loadHistory(); }, [historyPage.pg_no, historyPage.pg_size]);
  useEffect(() => {
    api.get<any>("/commands/suggestions")
      .then(r => setSuggestions((r.items || []).map((s:any) => ({ cmd:s.cmd, desc:s.description }))))
      .catch(()=>setSuggestions(FALLBACK_SUGGESTIONS));
  }, []);

  const run = () => {
    const cmd = input.trim();
    if (!cmd || !connected) return;
    addLine(`$ ${cmd}`, "input");
    wsRef.current?.send(JSON.stringify({ action:"run", command:cmd }));
    setHistory(p => [cmd, ...p.slice(0,49)]);
    setHistIdx(-1);
    setInput("");
  };

  const stopCmd = () => {
    wsRef.current?.send(JSON.stringify({ action:"stop", request_id: activeRequestId }));
  };

  const clear = () => setLines([{ text:"Terminal cleared","type":"system" }]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key==="Enter") { run(); return; }
    if (e.key==="ArrowUp"   && history.length) { e.preventDefault(); const i=Math.min(histIdx+1,history.length-1); setHistIdx(i); setInput(history[i]||""); }
    if (e.key==="ArrowDown") { e.preventDefault(); const i=Math.max(histIdx-1,-1); setHistIdx(i); setInput(i===-1?"":history[i]||""); }
  };

  const lineColor = (t: Line["type"]) => {
    if (t==="input")  return "var(--accent)";
    if (t==="system") return "var(--cyan)";
    if (t==="error")  return "var(--red)";
    return "var(--text-primary)";
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <div className="page-header">
        <div>
          <div className="page-title">$ Terminal</div>
          <div className="page-subtitle" style={{ display:"flex", alignItems:"center", gap:6 }}>
            <span className={`live-dot ${connectionStatus==="connected"?"":"red"}`} />
            {connectionStatus==="connecting" ? "Connecting…" : connectionStatus==="connected" ? "Connected to Ollama" : "Disconnected"}
          </div>
          {connectError && <div style={{ fontSize:11, color:"var(--red)", marginTop:4 }}>{connectError}</div>}
        </div>
        <div className="page-header-sep" />
        {running && <button className="btn btn-danger btn-sm" onClick={stopCmd}>⏹ Stop</button>}
        {connectionStatus==="disconnected" && !running && <button className="btn btn-primary btn-sm" onClick={connect}>Reconnect</button>}
        <button className="btn btn-ghost btn-sm" onClick={()=>navigator.clipboard.writeText(lines.map(l=>l.text).join("\n")).then(()=>toast("Copied","success"))}>Copy Output</button>
        <button className="btn btn-secondary btn-sm" onClick={clear}>Clear</button>
      </div>

      <div style={{ display:"flex", flex:1, overflow:"hidden", gap:0 }}>
        {/* Terminal output */}
        <div style={{ flex:1, display:"flex", flexDirection:"column", background:"#030810", overflow:"hidden" }}>
          <div ref={outRef} style={{ flex:1, overflowY:"auto", padding:"14px 18px", fontFamily:"var(--font-mono)", fontSize:12.5, lineHeight:1.75 }}>
            {lines.map((l, i) => (
              <div key={i} style={{ color: lineColor(l.type), whiteSpace:"pre-wrap", wordBreak:"break-all" }}>
                {l.type==="input" ? <span style={{ opacity:0.6 }}>{l.text}</span> : l.text}
              </div>
            ))}
            {running && (
              <div style={{ display:"inline-flex", gap:3, alignItems:"center", marginTop:4 }}>
                {[0,1,2].map(i=>(
                  <span key={i} style={{ width:5, height:5, borderRadius:"50%", background:"var(--accent)", display:"inline-block", animation:`livepulse 1.2s ${i*0.2}s ease-in-out infinite` }} />
                ))}
              </div>
            )}
          </div>

          {/* Input row */}
          <div style={{ borderTop:"1px solid #1a2438", padding:"10px 18px", display:"flex", alignItems:"center", gap:8, background:"#030810" }}>
            <span style={{ fontFamily:"var(--font-mono)", fontSize:13, color:"var(--accent)", flexShrink:0 }}>$</span>
            <input
              ref={inputRef}
              className="input-mono"
              value={input}
              onChange={e=>{ setInput(e.target.value); setHistIdx(-1); }}
              onKeyDown={handleKeyDown}
              disabled={!connected}
              placeholder={connected?"Type an Ollama command…":"Connecting…"}
              spellCheck={false}
              autoComplete="off"
              style={{ flex:1, background:"transparent", border:"none", color:"var(--text-primary)", fontFamily:"var(--font-mono)", fontSize:12.5, outline:"none" }}
            />
            <button className="btn btn-primary btn-sm" onClick={run} disabled={!connected||!input.trim()}>Run ↵</button>
          </div>
        </div>

        {/* Right panel: suggestions + history */}
        <div style={{ width:260, borderLeft:"1px solid var(--border-soft)", background:"var(--bg-surface)", display:"flex", flexDirection:"column", overflow:"hidden", flexShrink:0 }}>
          <div style={{ padding:"12px 14px", borderBottom:"1px solid var(--border-soft)" }}>
            <div className="card-title" style={{ marginBottom:10 }}>Quick Commands</div>
            <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
              {suggestions.map(s=>(
                <button key={s.cmd} style={{ background:"transparent", border:"1px solid var(--border-soft)", borderRadius:8, padding:"7px 10px", cursor:"pointer", textAlign:"left", transition:"all 120ms" }}
                  onClick={()=>{ setInput(s.cmd); inputRef.current?.focus(); }}
                  onMouseEnter={e=>(e.currentTarget.style.borderColor="var(--border-accent)")}
                  onMouseLeave={e=>(e.currentTarget.style.borderColor="var(--border-soft)")}>
                  <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--accent)", marginBottom:2 }}>{s.cmd}</div>
                  <div style={{ fontSize:11, color:"var(--text-muted)" }}>{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div style={{ flex:1, overflowY:"auto", padding:"12px 14px" }}>
            <div className="card-title" style={{ marginBottom:10 }}>Recent History</div>
            {cmdHistory.length===0 ? (
              <div style={{ fontSize:12, color:"var(--text-muted)", fontStyle:"italic" }}>No commands yet</div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
                {cmdHistory.map(c=>(
                  <div key={c.id} style={{ background:"var(--bg-elevated)", border:"1px solid var(--border-soft)", borderRadius:7, padding:"6px 9px", cursor:"pointer" }}
                    onClick={()=>{ setInput(c.command); inputRef.current?.focus(); }}>
                    <div style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--text-primary)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{c.command}</div>
                    <div style={{ display:"flex", gap:8, marginTop:3, fontSize:10, color:"var(--text-muted)" }}>
                      <span className={`badge badge-${c.status==="done"?"green":c.status==="error"?"red":"amber"}`}>{c.status}</span>
                      {c.duration_ms>0 && <span>{c.duration_ms}ms</span>}
                    </div>
                  </div>
                ))}
                {historyPage.total_pg > 1 && (
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginTop:8 }}>
                    <button className="btn btn-secondary btn-sm" disabled={historyPage.pg_no<=1} onClick={()=>setHistoryPage(p=>({...p, pg_no:p.pg_no-1}))}>Prev</button>
                    <span style={{ fontSize:10, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>{historyPage.pg_no}/{historyPage.total_pg}</span>
                    <button className="btn btn-secondary btn-sm" disabled={historyPage.pg_no>=historyPage.total_pg} onClick={()=>setHistoryPage(p=>({...p, pg_no:p.pg_no+1}))}>Next</button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
