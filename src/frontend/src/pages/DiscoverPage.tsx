import React, { useEffect, useRef, useState } from "react";
import { api, API_BASE } from "../api/client";

import { useToast } from "../hooks/useToast";
import type { PopularModel, PullProgress } from "../common/types";

const TAGS_FILTER = ["recommended","code","fast","reasoning","multilingual","embedding","large","tiny"];

export function DiscoverPage() {
  const [models, setModels]     = useState<PopularModel[]>([]);
  const [families, setFamilies] = useState<string[]>([]);
  const [family, setFamily]     = useState("All");
  const [search, setSearch]     = useState("");
  const [tag, setTag]           = useState("");
  const [pulling, setPulling]   = useState<Record<string,PullProgress>>({});
  const [loading, setLoading]   = useState(true);
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState({ pg_no:1, pg_size:24, total_records:0, total_pg:0 });
  const latestRequest = useRef(0);
  const { toast } = useToast();
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

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => window.clearTimeout(id);
  }, [search]);

  useEffect(() => {
    const requestId = latestRequest.current + 1;
    latestRequest.current = requestId;
    setLoading(true);
    (async () => {
      try {
        const params = new URLSearchParams();
        if (family !== "All") params.set("family", family);
        if (debouncedSearch) params.set("search", debouncedSearch);
        if (tag) params.set("tag", tag);
        params.set("pg_no", String(page.pg_no));
        params.set("pg_size", String(page.pg_size));
        const r = await api.get<any>(`/models/popular?${params}`);
        if (latestRequest.current !== requestId) return;
        setModels(r.items || []);
        setFamilies(r.families || []);
        if (r.page) setPage(r.page);
      } catch (e:any) { toast(e.message,"error"); }
      finally { if (latestRequest.current === requestId) setLoading(false); }
    })();
  }, [family, debouncedSearch, tag, page.pg_no, page.pg_size]);

  const startPull = async (modelId: string) => {
    if (pulling[modelId]) return;
    setPulling(p => ({...p, [modelId]:{ status:"connecting",completed:0,total:0,percent:0,speed_mbps:0,eta_seconds:null,size_gb:null }}));
    try {
      const res = await fetch(`${API_BASE}/models/pull`,{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({model:modelId}),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || "Pull failed");
      }
      if (!res.body) throw new Error("Pull stream unavailable");
      const reader = res.body!.getReader(); const dec = new TextDecoder(); let buf="";
      while(true){
        const{done,value}=await reader.read(); if(done) break;
        buf+=dec.decode(value,{stream:true});
        const lines=buf.split("\n\n"); buf=lines.pop()||"";
        for(const line of lines){
          const data=line.replace(/^data: /,"").trim(); if(!data) continue;
          try{ const ev=JSON.parse(data); setPulling(p=>({...p,[modelId]:normalizeProgress(ev,p[modelId])})); if(ev.status==="success"){ toast(`${modelId} pulled!`,"success"); } if(ev.status==="error"){ toast(ev.error || `Pull failed for ${modelId}`,"error"); } }catch{}
        }
      }
    } catch(e:any){ toast(`Pull failed: ${e.message}`,"error"); }
    finally{ setPulling(p=>{ const current=p[modelId]; if(current && !["success","error","cancelled"].includes(current.status)) return p; const n={...p}; delete n[modelId]; return n; }); }
  };

  const cancelPull = async (modelId: string) => {
    const rid = pulling[modelId]?.request_id;
    if (!rid) return;
    await api.post(`/models/pull/${rid}/stop`).catch((e:any)=>toast(e.message,"error"));
    setPulling(p=>({...p,[modelId]:normalizeProgress({status:"cancelled"},p[modelId])}));
  };

  return (
    <div style={{display:"flex",flexDirection:"column",height:"100%",overflow:"hidden"}}>
      <div className="page-header">
        <div>
          <div className="page-title">◎ Discover Models</div>
          <div className="page-subtitle">Curated Ollama model catalog · {page.total_records || models.length} models</div>
        </div>
      </div>

      <div className="page-body">
        <div className="page-inner">
          {/* Filters */}
          <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
            <input className="input" placeholder="Search models…" value={search} onChange={e=>{ setSearch(e.target.value); setPage(p=>({...p, pg_no:1})); }} style={{width:240}} />
            <select className="select" value={family} onChange={e=>{ setFamily(e.target.value); setPage(p=>({...p, pg_no:1})); }}>
              {["All",...families].map(f=><option key={f}>{f}</option>)}
            </select>
            <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
              {TAGS_FILTER.map(t=>(
                <button key={t} className={`btn btn-sm ${tag===t?"btn-primary":"btn-secondary"}`} onClick={()=>{ setTag(tag===t?"":t); setPage(p=>({...p, pg_no:1})); }}>{t}</button>
              ))}
            </div>
          </div>

          {/* Grid */}
          {loading ? (
            <div className="grid-3">{[1,2,3,4,5,6].map(i=><div key={i} className="skeleton" style={{height:180,borderRadius:14}}/>)}</div>
          ) : models.length===0 ? (
            <div className="empty-state"><div className="empty-state-icon">◎</div><div className="empty-state-title">No matches</div></div>
          ) : (
            <>
            <div className="grid-3">
              {models.map(m=>(
                <ModelCard key={m.id} model={m}
                  pullState={pulling[m.id]||null}
                  onPull={()=>startPull(m.id)}
                  onCancel={()=>cancelPull(m.id)}
                />
              ))}
            </div>
            {page.total_pg > 1 && (
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"12px 0"}}>
                <button className="btn btn-secondary btn-sm" disabled={page.pg_no<=1} onClick={()=>setPage(p=>({...p, pg_no:p.pg_no-1}))}>Previous</button>
                <span style={{fontSize:12,color:"var(--text-muted)",fontFamily:"var(--font-mono)"}}>Page {page.pg_no} / {page.total_pg}</span>
                <button className="btn btn-secondary btn-sm" disabled={page.pg_no>=page.total_pg} onClick={()=>setPage(p=>({...p, pg_no:p.pg_no+1}))}>Next</button>
              </div>
            )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ModelCard({model,pullState,onPull,onCancel}:{model:PopularModel;pullState:PullProgress|null;onPull:()=>void;onCancel:()=>void}) {
  const isPulling = !!pullState && pullState.status !== "success";
  const isDone    = model.installed || pullState?.status === "success";
  const sizeLabel = model.size_gb ? `${model.size_gb} GB` : "Size unknown";
  return (
    <div className="card" style={{display:"flex",flexDirection:"column",gap:0,transition:"border-color 150ms",borderColor: model.recommended ? "var(--border-accent)":"var(--border-soft)"}}>
      <div style={{padding:"14px 16px",display:"flex",flexDirection:"column",gap:8,flex:1}}>
        {model.recommended && <span className="badge badge-accent" style={{alignSelf:"flex-start"}}>★ Recommended</span>}
        <div style={{fontFamily:"var(--font-mono)",fontSize:13,fontWeight:600,color:"var(--text-primary)"}}>{model.id}</div>
        <div style={{fontSize:12,color:"var(--text-secondary)",lineHeight:1.6,flex:1}}>{model.description}</div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",marginTop:4}}>
          <span className="badge badge-muted">{model.params || "unknown"}</span>
          <span className="badge badge-muted">{sizeLabel}</span>
          <span className="badge badge-cyan">{model.family}</span>
          {model.tags.slice(0,2).map(t=><span key={t} className="badge badge-muted">{t}</span>)}
        </div>
        {isPulling && pullState && (
          <div style={{marginTop:6}}>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:"var(--text-muted)",fontFamily:"var(--font-mono)",marginBottom:4}}>
              <span>{pullState.status}</span>
              <span>{pullState.percent.toFixed(1)}% {pullState.speed_mbps>0?`· ${pullState.speed_mbps} MB/s`:""}</span>
            </div>
            <div className="progress-wrap"><div className="progress-fill" style={{width:`${pullState.percent}%`}}/></div>
            {pullState.eta_seconds && <div style={{fontSize:10,color:"var(--text-muted)",marginTop:3}}>ETA {pullState.eta_seconds>60?`${Math.round(pullState.eta_seconds/60)}m`:`${pullState.eta_seconds}s`}</div>}
          </div>
        )}
      </div>
      <div style={{padding:"10px 16px",borderTop:"1px solid var(--border-soft)",display:"flex",gap:6}}>
        {isDone ? (
          <span className="badge badge-green" style={{padding:"4px 10px"}}>✓ Installed</span>
        ) : isPulling ? (
          <button className="btn btn-secondary btn-sm" onClick={onCancel}>Cancel</button>
        ) : (
          <button className="btn btn-primary btn-sm" onClick={onPull}>⬇ Pull {sizeLabel}</button>
        )}
      </div>
    </div>
  );
}
