import React, { useEffect, useRef, useState } from "react";
import { api, API_BASE } from "../api/client";
import { getAuthHeaders } from "../common/auth";
import { useToast } from "../hooks/useToast";
import type { PopularModel, PullProgress } from "../common/types";

const FAMILIES = ["All","Llama","Mistral","CodeLlama","DeepSeek","Qwen","Phi","Gemma","Embedding"];
const TAGS_FILTER = ["recommended","code","fast","reasoning","multilingual","embedding","large","tiny"];

export function DiscoverPage() {
  const [models, setModels]     = useState<PopularModel[]>([]);
  const [families, setFamilies] = useState<string[]>([]);
  const [family, setFamily]     = useState("All");
  const [search, setSearch]     = useState("");
  const [tag, setTag]           = useState("");
  const [pulling, setPulling]   = useState<Record<string,PullProgress>>({});
  const [loading, setLoading]   = useState(true);
  const { toast } = useToast();
  const aborts = useRef<Record<string,AbortController>>({});

  useEffect(() => {
    (async () => {
      try {
        const params = new URLSearchParams();
        if (family !== "All") params.set("family", family);
        if (search) params.set("search", search);
        const r = await api.get<any>(`/models/popular?${params}`);
        setModels(r.items || []);
        setFamilies(r.families || []);
      } catch (e:any) { toast(e.message,"error"); }
      finally { setLoading(false); }
    })();
  }, [family, search]);

  const startPull = async (modelId: string) => {
    if (pulling[modelId]) return;
    const ac = new AbortController();
    aborts.current[modelId] = ac;
    setPulling(p => ({...p, [modelId]:{ status:"connecting",completed:0,total:0,percent:0,speed_mbps:0,eta_seconds:null,size_gb:null }}));
    try {
      const res = await fetch(`${API_BASE}/models/pull`,{
        method:"POST", signal:ac.signal,
        headers:{"Content-Type":"application/json",...getAuthHeaders()},
        body: JSON.stringify({model:modelId}),
      });
      const reader = res.body!.getReader(); const dec = new TextDecoder(); let buf="";
      while(true){
        const{done,value}=await reader.read(); if(done) break;
        buf+=dec.decode(value,{stream:true});
        const lines=buf.split("\n\n"); buf=lines.pop()||"";
        for(const line of lines){
          const data=line.replace(/^data: /,"").trim(); if(!data) continue;
          try{ const ev=JSON.parse(data); setPulling(p=>({...p,[modelId]:ev})); if(ev.status==="success"){ toast(`${modelId} pulled!`,"success"); } }catch{}
        }
      }
    } catch(e:any){ if(e.name!=="AbortError") toast(`Pull failed: ${e.message}`,"error"); }
    finally{ setPulling(p=>{ const n={...p}; delete n[modelId]; return n; }); }
  };

  const filtered = models.filter(m => !tag || m.tags.includes(tag));

  return (
    <div style={{display:"flex",flexDirection:"column",height:"100%",overflow:"hidden"}}>
      <div className="page-header">
        <div>
          <div className="page-title">◎ Discover Models</div>
          <div className="page-subtitle">Curated Ollama model catalog · {filtered.length} models</div>
        </div>
      </div>

      <div className="page-body">
        <div className="page-inner">
          {/* Filters */}
          <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
            <input className="input" placeholder="Search models…" value={search} onChange={e=>setSearch(e.target.value)} style={{width:240}} />
            <select className="select" value={family} onChange={e=>setFamily(e.target.value)}>
              {["All",...families].map(f=><option key={f}>{f}</option>)}
            </select>
            <div style={{display:"flex",gap:4,flexWrap:"wrap"}}>
              {TAGS_FILTER.map(t=>(
                <button key={t} className={`btn btn-sm ${tag===t?"btn-primary":"btn-secondary"}`} onClick={()=>setTag(tag===t?"":t)}>{t}</button>
              ))}
            </div>
          </div>

          {/* Grid */}
          {loading ? (
            <div className="grid-3">{[1,2,3,4,5,6].map(i=><div key={i} className="skeleton" style={{height:180,borderRadius:14}}/>)}</div>
          ) : filtered.length===0 ? (
            <div className="empty-state"><div className="empty-state-icon">◎</div><div className="empty-state-title">No matches</div></div>
          ) : (
            <div className="grid-3">
              {filtered.map(m=>(
                <ModelCard key={m.id} model={m}
                  pullState={pulling[m.id]||null}
                  onPull={()=>startPull(m.id)}
                  onCancel={()=>aborts.current[m.id]?.abort()}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ModelCard({model,pullState,onPull,onCancel}:{model:PopularModel;pullState:PullProgress|null;onPull:()=>void;onCancel:()=>void}) {
  const isPulling = !!pullState && pullState.status !== "success";
  const isDone    = model.installed || pullState?.status === "success";
  return (
    <div className="card" style={{display:"flex",flexDirection:"column",gap:0,transition:"border-color 150ms",borderColor: model.recommended ? "var(--border-accent)":"var(--border-soft)"}}>
      <div style={{padding:"14px 16px",display:"flex",flexDirection:"column",gap:8,flex:1}}>
        {model.recommended && <span className="badge badge-accent" style={{alignSelf:"flex-start"}}>★ Recommended</span>}
        <div style={{fontFamily:"var(--font-mono)",fontSize:13,fontWeight:600,color:"var(--text-primary)"}}>{model.id}</div>
        <div style={{fontSize:12,color:"var(--text-secondary)",lineHeight:1.6,flex:1}}>{model.description}</div>
        <div style={{display:"flex",gap:6,flexWrap:"wrap",marginTop:4}}>
          <span className="badge badge-muted">{model.params}</span>
          <span className="badge badge-muted">{model.size_gb} GB</span>
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
          <button className="btn btn-primary btn-sm" onClick={onPull}>⬇ Pull {model.size_gb} GB</button>
        )}
      </div>
    </div>
  );
}
