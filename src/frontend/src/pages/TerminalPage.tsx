import React, { useEffect, useRef, useState } from "react";
import { api, wsUrl } from "../api/client";
import { useToast } from "../hooks/useToast";

interface Line { text: string; type: "input"|"output"|"system"|"error"; }

const SUGGESTIONS = [
  { cmd:"ollama ps",           desc:"List running models" },
  { cmd:"ollama list",         desc:"List installed models" },
  { cmd:"ollama version",      desc:"Show Ollama version" },
  { cmd:"ollama pull llama3.2", desc:"Pull latest Llama 3.2" },
  { cmd:"ollama pull mistral", desc:"Pull Mistral 7B" },
  { cmd:"ollama run llama3.2", desc:"Run Llama 3.2 interactively" },
  { cmd:"ollama show llama3.2",desc:"Show model details" },
];

export function TerminalPage() {
  const [lines, setLines]     = useState<Line[]>([{ text:"Ollama Terminal — type an Ollama command and press Enter", type:"system" }]);
  const [input, setInput]     = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState(-1);
  const [connected, setConnected] = useState(false);
  const [running, setRunning]     = useState(false);
  const [cmdHistory, setCmdHistory] = useState<any[]>([]);
  const wsRef   = useRef<WebSocket|null>(null);
  const outRef  = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  const addLine = (text: string, type: Line["type"] = "output") => {
    setLines(p => [...p, { text, type }]);
    setTimeout(() => outRef.current?.scrollTo(0, outRef.current.scrollHeight), 0);
  };

  useEffect(() => {
    const ws = new WebSocket(wsUrl("/commands/stream"));
    wsRef.current = ws;
    ws.onopen  = () => { setConnected(true); addLine("● Connected","system"); };
    ws.onclose = () => { setConnected(false); addLine("○ Disconnected","system"); };
    ws.onerror = () => addLine("WebSocket error","error");
    ws.onmessage = evt => {
      try {
        const d = JSON.parse(evt.data);
        if (d.event_type==="connected") return;
        if (d.event_type==="started")   { setRunning(true);  addLine(`▶ ${d.payload?.command||""}`, "system"); }
        if (d.event_type==="output")    { addLine(d.payload?.line||"", "output"); }
        if (d.event_type==="done")      { setRunning(false); addLine(`✓ Exit ${d.payload?.exit_code??0}`, "system"); }
        if (d.event_type==="error")     { setRunning(false); addLine(`✕ ${d.payload?.message||"Error"}`, "error"); }
        if (d.event_type==="stopped")   { setRunning(false); addLine("⏹ Stopped", "system"); }
      } catch {}
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    api.get<any>("/commands/history?pg_size=20").then(r => setCmdHistory(r.items||[])).catch(()=>{});
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
    wsRef.current?.send(JSON.stringify({ action:"stop" }));
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
            <span className={`live-dot ${connected?"":"red"}`} />
            {connected?"Connected to Ollama":"Disconnected"}
          </div>
        </div>
        <div className="page-header-sep" />
        {running && <button className="btn btn-danger btn-sm" onClick={stopCmd}>⏹ Stop</button>}
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
              {SUGGESTIONS.map(s=>(
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
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
