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
  const [deleting, setDeleting]     = useState<Record<string, boolean>>({});
  const [page, setPage]             = useState({ pg_no:1, pg_size:20, total_records:0, total_pg:0 });
  const [pullInput, setPullInput]   = useState("");
  const [pullInfo, setPullInfo]     = useState<any>(null);
  const [previewModel, setPreviewModel] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [loading, setLoading]       = useState(true);
  const { toast } = useToast();
  const navigate  = useNavigate();
  const normalizeProgress = (ev: Partial<PullProgress>, previous?: PullProgress): PullProgress => ({
    request_id: ev.request_id || previous?.request_id,
    model: ev.model || ev.model_name || previous?.model,
    model_name: ev.model_name || ev.model || previous?.model_name,
    status: ev.status || previous?.status || "connecting",
    completed: ev.completed ?? previous?.completed ?? 0,
    total: ev.total ?? previous?.total ?? 0,
    percent: ev.percent ?? previous?.percent ?? 0,
    speed_mbps: ev.speed_mbps ?? previous?.speed_mbps ?? 0,
    eta_seconds: ev.eta_seconds ?? previous?.eta_seconds ?? null,
    size_gb: ev.size_gb ?? previous?.size_gb ?? null,
    error: ev.error ?? previous?.error ?? null,
  });

  const load = useCallback(async () => {
    try {
      const [modRes, rtRes, dlRes] = await Promise.all([
        api.get<any>(`/models?pg_no=${page.pg_no}&pg_size=${page.pg_size}${search ? `&search=${encodeURIComponent(search)}` : ""}`),
        api.get<any>("/models/runtime"),
        api.get<any>("/models/downloads?active_only=true&pg_size=100"),
      ]);
      setInstalled(modRes.items || []);
      if (modRes.page) setPage(modRes.page);
      setRunning(rtRes.models || []);
      setGpu(rtRes.gpu);
      setContainer(rtRes.container);
      setPulling(prev => {
        const activePulls: Record<string, PullProgress> = {};
        (dlRes.items || []).forEach((d: PullProgress) => {
          const id = d.model_name || d.model || "";
          if (id) activePulls[id] = normalizeProgress(d, prev[id]);
        });
        return activePulls;
      });
    } catch (e: any) { toast(e.message, "error"); }
    finally { setLoading(false); }
  }, [page.pg_no, page.pg_size, search]);

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
    setDeleting(p => ({ ...p, [name]: true }));
    try {
      await api.delete(`/models/${encodeURIComponent(name)}`);
      setInstalled(p => p.filter(m => m.name !== name));
      toast(`Deleted ${name}`, "success");
      load();
    } catch (e: any) {
      toast(e.message || `Delete failed for ${name}`, "error");
    } finally {
      setDeleting(p => { const n = { ...p }; delete n[name]; return n; });
    }
  };

  const fetchPullInfo = async (modelId: string) => {
    const trimmed = modelId.trim();
    if (!trimmed) return;
    setPreviewLoading(true);
    setPreviewError("");
    setPullInfo(null);
    try {
      const info = await api.get<any>(`/models/pull-info?model=${encodeURIComponent(trimmed)}`);
      setPullInfo(info);
      setPreviewModel(trimmed);
    } catch (e: any) {
      setPreviewError(e.message || "Unable to preview model");
    } finally {
      setPreviewLoading(false);
    }
  };

  const confirmPull = async () => {
    if (!previewModel) return;
    setPullInfo(null);
    setPreviewModel("");
    await startPull(previewModel);
  };

  const startPull = async (modelId: string) => {
    if (!modelId.trim() || pulling[modelId]) return;
    setPulling(p => ({ ...p, [modelId]: { status:"connecting", completed:0, total:0, percent:0, speed_mbps:0, eta_seconds:null, size_gb:null } }));
    try {
      const res = await fetch(`${API_BASE}/models/pull`, {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ model: modelId }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || "Pull failed");
      }
      if (!res.body) throw new Error("Pull stream unavailable");
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
            setPulling(p => ({ ...p, [modelId]: normalizeProgress(ev, p[modelId]) }));
            if (ev.status === "success") { toast(`${modelId} pulled!`, "success"); load(); }
            if (ev.status === "error") { toast(ev.error || `Pull failed for ${modelId}`, "error"); }
          } catch {}
        }
      }
    } catch (e: any) {
      toast(`Pull failed: ${e.message}`, "error");
    } finally {
      setPulling(p => {
        const current = p[modelId];
        if (current && !["success", "error", "cancelled"].includes(current.status)) return p;
        const n = {...p}; delete n[modelId]; return n;
      });
    }
  };

  const cancelPull = async (id: string) => {
    const rid = pulling[id]?.request_id;
    if (!rid) return;
    await api.post(`/models/pull/${rid}/stop`).catch((e: any) => toast(e.message, "error"));
    setPulling(p => ({ ...p, [id]: normalizeProgress({ status: "cancelled" }, p[id]) }));
  };

  const filtered = installed;
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
              { label:"CPU Usage",     v: fmt(container?.cpu_percent, "%"), sub: "Host CPU load", gauge:<GaugeBar value={container?.cpu_percent} max={100} /> },
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
                <input className="input input-mono" placeholder="e.g. llama3.2:3b  or  qwen2.5:14b" value={pullInput} onChange={e => setPullInput(e.target.value)} onKeyDown={e => e.key==="Enter" && !previewLoading && fetchPullInfo(pullInput.trim())} style={{ flex:1 }} />
                <button className="btn btn-primary" onClick={() => fetchPullInfo(pullInput.trim())} disabled={!pullInput.trim() || previewLoading}>
                  {previewLoading ? "Checking…" : "Preview"}
                </button>
              </div>
              {previewError && (
                <div style={{ marginTop:10, color:"var(--red)", fontSize:12 }}>{previewError}</div>
              )}
              {pullInfo && previewModel === pullInput.trim() && (
                <div style={{ marginTop:12, padding:14, border:"1px solid var(--border)", borderRadius:10, background:"var(--bg-elevated)" }}>
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", gap:10, marginBottom:12 }}>
                    <div>
                      <div style={{ fontSize:12, color:"var(--text-muted)" }}>Confirm pull</div>
                      <div style={{ fontFamily:"var(--font-mono)", fontSize:14, fontWeight:600 }}>{pullInfo.model_name}</div>
                    </div>
                    <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
                      <button className="btn btn-primary btn-sm" onClick={confirmPull} disabled={!!pulling[previewModel]}>
                        {pulling[previewModel] ? "Pulling…" : "Start Pull"}
                      </button>
                      <button className="btn btn-secondary btn-sm" onClick={() => { setPullInfo(null); setPreviewModel(""); setPreviewError(""); }}>
                        Change
                      </button>
                    </div>
                  </div>
                  <div style={{ display:"grid", gap:6, fontSize:12, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>
                    <div>Size: {pullInfo.download_size_gb ? `${pullInfo.download_size_gb} GB` : "Unknown"}</div>
                    <div>Disk after pull: {pullInfo.estimated_disk_after_pull_gb ? `${pullInfo.estimated_disk_after_pull_gb} GB` : "Unknown"}</div>
                    <div>Status: {pullInfo.downloaded ? "Already installed" : "Not installed"}</div>
                    {pullInfo.pulled_at && <div>Last pulled: {new Date(pullInfo.pulled_at).toLocaleString()}</div>}
                  </div>
                </div>
              )}
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
              <input className="input" placeholder="Search…" value={search} onChange={e => { setSearch(e.target.value); setPage(p => ({ ...p, pg_no:1 })); }} style={{ width:200, padding:"4px 10px", fontSize:12 }} />
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
                    isDeleting={!!deleting[m.name]}
                    onStop={() => stopModel(m.name)}
                    onDelete={() => deleteModel(m.name)}
                    onChat={() => navigate(`/chat?model=${encodeURIComponent(m.name)}`)}
                  />
                ))}
                {page.total_pg > 1 && (
                  <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"12px 18px", borderTop:"1px solid var(--border-soft)" }}>
                    <button className="btn btn-secondary btn-sm" disabled={page.pg_no <= 1} onClick={() => setPage(p => ({ ...p, pg_no:p.pg_no-1 }))}>Previous</button>
                    <span style={{ fontSize:12, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>Page {page.pg_no} / {page.total_pg} · {page.total_records} models</span>
                    <button className="btn btn-secondary btn-sm" disabled={page.pg_no >= page.total_pg} onClick={() => setPage(p => ({ ...p, pg_no:p.pg_no+1 }))}>Next</button>
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

function ModelRow({ model, isRunning, isDeleting, onStop, onDelete, onChat }: { model: InstalledModel; isRunning: boolean; isDeleting: boolean; onStop: () => void; onDelete: () => void; onChat: () => void; }) {
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
          {model.pulled_at && <span>pulled {new Date(model.pulled_at).toLocaleDateString()}</span>}
        </div>
        {model.download && <div style={{ marginTop:8 }}><PullProgressCard id={model.name} p={model.download} onCancel={() => {}} /></div>}
      </div>
      <div style={{ display:"flex", gap:6 }}>
        <button className="btn btn-primary btn-sm" onClick={onChat} disabled={isDeleting}>Chat</button>
        {isRunning && <button className="btn btn-secondary btn-sm" onClick={onStop} disabled={isDeleting}>Stop</button>}
        <button className="btn btn-danger btn-sm" onClick={onDelete} disabled={isDeleting}>{isDeleting ? "Deleting…" : "Delete"}</button>
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
