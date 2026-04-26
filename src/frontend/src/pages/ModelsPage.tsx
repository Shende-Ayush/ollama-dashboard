import React, { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, API_BASE } from "../api/client";

import { useToast } from "../hooks/useToast";
import type { InstalledModel, RunningModel, PullProgress } from "../common/types";

function bytes(b: number) { if (!b) return "–"; const gb = b / 1024**3; return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(b/1024**2).toFixed(0)} MB`; }
function fmt(n: number|null, unit="") { return n != null ? `${n}${unit}` : "–"; }

function GaugeBar({ value, max, color="accent" }: { value: number|null; max: number|null; color?: string }) {
  const pct = value && max ? Math.min(100, (value/max)*100) : 0;
  return (
    <div style={{ display:"flex", alignItems:"center", gap:6 }}>
      <div className="progress-wrap" style={{ flex:1, height:4 }}>
        <div className="progress-fill" style={{ width:`${pct}%`, background: color==="red"?"var(--red)":color==="amber"?"var(--amber)":"var(--accent)" }} />
      </div>
      <span style={{ fontFamily:"var(--font-mono)", fontSize:10, color:"var(--text-muted)", minWidth:32 }}>{pct.toFixed(0)}%</span>
    </div>
  );
}

export function ModelsPage() {
  const [installed, setInstalled]   = useState<InstalledModel[]>([]);
  const [running, setRunning]       = useState<RunningModel[]>([]);
  const [gpu, setGpu]               = useState<any>(null);
  const [container, setContainer]   = useState<any>(null);
  const [search, setSearch]         = useState("");
  const [pulling, setPulling]       = useState<Record<string, PullProgress>>({});
  const [pullInput, setPullInput]   = useState("");
  const [loading, setLoading]       = useState(true);
  const { toast } = useToast();
  const navigate  = useNavigate();
  const aborts    = useRef<Record<string, AbortController>>({});

  const load = useCallback(async () => {
    try {
      const [modRes, rtRes] = await Promise.all([
        api.get<any>("/models?pg_size=100"),
        api.get<any>("/models/runtime"),
      ]);
      setInstalled(modRes.items || []);
      setRunning(rtRes.models || []);
      setGpu(rtRes.gpu);
      setContainer(rtRes.container);
    } catch (e: any) { toast(e.message, "error"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const id = setInterval(load, 4000); return () => clearInterval(id); }, [load]);

  const stopModel = async (name: string) => {
    await api.post("/models/stop", { model: name });
    toast(`Stopped ${name}`, "success");
  };

  const clearGpu = async () => {
    await api.post("/models/clear-gpu");
    toast("GPU cleared", "success");
  };

  const deleteModel = async (name: string) => {
    if (!confirm(`Delete ${name}?`)) return;
    await api.delete(`/models/${encodeURIComponent(name)}`);
    toast(`Deleted ${name}`, "success");
    load();
  };

  const startPull = async (modelId: string) => {
    if (pulling[modelId]) return;
    const ac = new AbortController();
    aborts.current[modelId] = ac;
    setPulling(p => ({ ...p, [modelId]: { status:"connecting", completed:0, total:0, percent:0, speed_mbps:0, eta_seconds:null, size_gb:null } }));
    try {
      const res = await fetch(`${API_BASE}/models/pull`, {
        method:"POST", signal:ac.signal,
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ model: modelId }),
      });
      const reader = res.body!.getReader();
      const dec    = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          const data = line.replace(/^data: /, "").trim();
          if (!data) continue;
          try {
            const ev = JSON.parse(data);
            setPulling(p => ({ ...p, [modelId]: ev }));
            if (ev.status === "success") { toast(`${modelId} pulled!`, "success"); load(); }
          } catch {}
        }
      }
    } catch (e: any) { if (e.name !== "AbortError") toast(`Pull failed: ${e.message}`, "error"); }
    finally { setPulling(p => { const n = {...p}; delete n[modelId]; return n; }); }
  };

  const cancelPull = (id: string) => { aborts.current[id]?.abort(); };

  const filtered = installed.filter(m => !search || m.name.toLowerCase().includes(search.toLowerCase()));
  const runningNames = new Set(running.map(r => r.name));

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">⬡ Models</div>
          <div className="page-subtitle">{installed.length} installed · {running.length} running</div>
        </div>
        <div className="page-header-sep" />
        <button className="btn btn-danger btn-sm" onClick={clearGpu}>✕ Clear GPU</button>
        <button className="btn btn-primary btn-sm" onClick={() => navigate("/discover")}>+ Discover Models</button>
      </div>

      <div className="page-body">
        <div className="page-inner">

          {/* System stats */}
          <div className="grid-4" style={{ gap:12 }}>
            {[
              { label:"GPU Utilization", v:fmt(gpu?.utilization_percent, "%"), sub: `${fmt(gpu?.vram_used_mb)} / ${fmt(gpu?.vram_total_mb)} MB VRAM`, gauge:<GaugeBar value={gpu?.vram_used_mb} max={gpu?.vram_total_mb} /> },
              { label:"Container RAM",   v: container?.memory_usage ? bytes(container.memory_usage) : "–", sub: container?.memory_limit ? `of ${bytes(container.memory_limit)}` : "n/a", gauge:<GaugeBar value={container?.memory_usage} max={container?.memory_limit} color="amber" /> },
              { label:"Running Models",  v: String(running.length),   sub:"currently loaded in GPU", gauge:null },
              { label:"Installed",       v: String(installed.length), sub:"locally available",       gauge:null },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <div className="stat-label">{s.label}</div>
                <div className="stat-value">{s.v}</div>
                <div className="stat-sub">{s.sub}</div>
                {s.gauge}
              </div>
            ))}
          </div>

          {/* Pull by ID */}
          <div className="card">
            <div className="card-header"><span className="card-title">⬇ Pull by Model ID</span></div>
            <div className="card-body">
              <div style={{ display:"flex", gap:8 }}>
                <input className="input input-mono" placeholder="e.g. llama3.2:3b  or  qwen2.5:14b" value={pullInput} onChange={e => setPullInput(e.target.value)} onKeyDown={e => e.key==="Enter" && startPull(pullInput.trim())} style={{ flex:1 }} />
                <button className="btn btn-primary" onClick={() => startPull(pullInput.trim())} disabled={!pullInput.trim()}>Pull</button>
              </div>
              {pulling[pullInput] && (
                <div style={{ marginTop:12 }}>
                  <PullProgressCard id={pullInput} p={pulling[pullInput]} onCancel={() => cancelPull(pullInput)} />
                </div>
              )}
            </div>
          </div>

          {/* Active pulls */}
          {Object.entries(pulling).filter(([id]) => id !== pullInput).length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title"><span className="live-dot" style={{ marginRight:6 }} />Active Downloads</span></div>
              <div className="card-body" style={{ display:"flex", flexDirection:"column", gap:10 }}>
                {Object.entries(pulling).filter(([id]) => id !== pullInput).map(([id, p]) => (
                  <PullProgressCard key={id} id={id} p={p} onCancel={() => cancelPull(id)} />
                ))}
              </div>
            </div>
          )}

          {/* Installed models */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Installed Models</span>
              <input className="input" placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)} style={{ width:200, padding:"4px 10px", fontSize:12 }} />
            </div>
            {loading ? (
              <div className="card-body" style={{ display:"flex", flexDirection:"column", gap:8 }}>
                {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height:60, borderRadius:8 }} />)}
              </div>
            ) : filtered.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">⬡</div>
                <div className="empty-state-title">No models yet</div>
                <div className="empty-state-desc">Pull a model above or visit Discover to browse the catalog.</div>
              </div>
            ) : (
              <div style={{ padding:"4px 0" }}>
                {filtered.map(m => (
                  <ModelRow key={m.name} model={m}
                    isRunning={runningNames.has(m.name)}
                    onStop={() => stopModel(m.name)}
                    onDelete={() => deleteModel(m.name)}
                    onChat={() => navigate(`/chat?model=${encodeURIComponent(m.name)}`)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ModelRow({ model, isRunning, onStop, onDelete, onChat }: { model: InstalledModel; isRunning: boolean; onStop: () => void; onDelete: () => void; onChat: () => void; }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:12, padding:"12px 18px", borderBottom:"1px solid var(--border-soft)" }}>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
          {isRunning && <span className="live-dot" title="Running" />}
          <span style={{ fontFamily:"var(--font-mono)", fontSize:13, fontWeight:600, color:"var(--text-primary)" }}>{model.name}</span>
          {isRunning && <span className="badge badge-green">running</span>}
          {model.quantization && <span className="badge badge-muted">{model.quantization}</span>}
          {model.family && <span className="badge badge-cyan">{model.family}</span>}
        </div>
        <div style={{ display:"flex", gap:16, fontSize:11, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>
          <span>{model.parameter_size || "–"}</span>
          <span>{model.size_gb ? `${model.size_gb} GB` : bytes(model.size)}</span>
          {model.modified_at && <span>modified {new Date(model.modified_at).toLocaleDateString()}</span>}
        </div>
      </div>
      <div style={{ display:"flex", gap:6 }}>
        <button className="btn btn-primary btn-sm" onClick={onChat}>Chat</button>
        {isRunning && <button className="btn btn-secondary btn-sm" onClick={onStop}>Stop</button>}
        <button className="btn btn-danger btn-sm" onClick={onDelete}>Delete</button>
      </div>
    </div>
  );
}

function PullProgressCard({ id, p, onCancel }: { id: string; p: PullProgress; onCancel: () => void }) {
  const done = p.status === "success" || p.percent >= 100;
  return (
    <div style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)", borderRadius:10, padding:"12px 14px", display:"flex", flexDirection:"column", gap:8 }}>
      <div style={{ display:"flex", alignItems:"center", gap:8 }}>
        {!done && <span className="live-dot" />}
        <span style={{ fontFamily:"var(--font-mono)", fontSize:12, flex:1 }}>{id}</span>
        <span style={{ fontFamily:"var(--font-mono)", fontSize:11, color:"var(--text-muted)" }}>{p.percent.toFixed(1)}%</span>
        {!done && <button className="btn btn-ghost btn-sm" onClick={onCancel}>✕</button>}
        {done && <span className="badge badge-green">✓ Done</span>}
      </div>
      <div className="progress-wrap"><div className="progress-fill" style={{ width:`${p.percent}%` }} /></div>
      <div style={{ display:"flex", gap:16, fontSize:10, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>
        {p.size_gb && <span>{p.size_gb} GB total</span>}
        {p.speed_mbps > 0 && <span>{p.speed_mbps} MB/s</span>}
        {p.eta_seconds && <span>ETA {p.eta_seconds > 60 ? `${Math.round(p.eta_seconds/60)}m` : `${p.eta_seconds}s`}</span>}
        <span style={{ marginLeft:"auto" }}>{p.status}</span>
      </div>
    </div>
  );
}
