import React, { useEffect, useState } from "react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";

const COLORS = ["#6366f1","#10b981","#f59e0b","#ef4444","#06b6d4","#8b5cf6"];

function fmt(n: number) { return n>=1e6?`${(n/1e6).toFixed(1)}M`:n>=1e3?`${(n/1e3).toFixed(1)}K`:String(n); }

export function AnalyticsPage() {
  const [hours, setHours]       = useState(24);
  const [overview, setOverview] = useState<any>(null);
  const [byModel, setByModel]   = useState<any[]>([]);
  const [timeseries, setTs]     = useState<any[]>([]);
  const [sysMetrics, setSys]    = useState<any[]>([]);
  const [loading, setLoading]   = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get<any>(`/analytics/overview?hours=${hours}`),
      api.get<any>(`/analytics/tokens-by-model?hours=${hours}`),
      api.get<any>(`/analytics/requests-timeseries?hours=${hours}`),
      api.get<any>(`/analytics/system-metrics?minutes=${Math.min(hours*60,1440)}`),
    ]).then(([ov, bm, ts, sys]) => {
      setOverview(ov);
      setByModel(bm.items||[]);
      setTs((ts.items||[]).map((r:any)=>({
        ...r,
        time: r.bucket ? new Date(r.bucket).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}) : "",
      })));
      setSys((sys.items||[]).map((r:any)=>({
        ...r,
        time: new Date(r.timestamp).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}),
        cpu_pct: r.cpu_percent,
        gpu_util: r.gpu_utilization,
        vram_pct: r.vram_used_mb&&r.vram_total_mb ? Math.round(r.vram_used_mb/r.vram_total_mb*100) : null,
        ram_pct:  r.ram_used_mb&&r.ram_total_mb   ? Math.round(r.ram_used_mb/r.ram_total_mb*100)  : null,
      })));
    }).catch((e:any)=>toast(e.message,"error")).finally(()=>setLoading(false));
  }, [hours]);

  const kpis = overview ? [
    { label:"Total Requests",      value: fmt(overview.total_requests),       sub:`last ${hours}h` },
    { label:"Tokens Generated",    value: fmt(overview.total_tokens),         sub:`${fmt(overview.tokens_input)} in · ${fmt(overview.tokens_output)} out` },
    { label:"Conversations",       value: fmt(overview.total_conversations),  sub:`last ${hours}h` },
    { label:"Avg Latency",         value: `${overview.avg_latency_ms}ms`,     sub:"per request" },
    { label:"Error Rate",          value: `${overview.error_rate_percent}%`,  sub:`${overview.error_count} errors` },
  ] : [];

  const pieData = byModel.map((m,i)=>({ name:m.model_name, value:m.total_tokens, color:COLORS[i%COLORS.length] }));

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active||!payload?.length) return null;
    return (
      <div style={{ background:"var(--bg-elevated)", border:"1px solid var(--border)", borderRadius:8, padding:"8px 12px", fontSize:12 }}>
        <div style={{ fontWeight:600, marginBottom:4 }}>{label}</div>
        {payload.map((p:any,i:number) => (
          <div key={i} style={{ color:p.color, display:"flex", justifyContent:"space-between", gap:16 }}>
            <span>{p.name}</span><span style={{ fontFamily:"var(--font-mono)" }}>{fmt(p.value)}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <div className="page-header">
        <div><div className="page-title">◈ Analytics</div></div>
        <div className="page-header-sep" />
        <span style={{ fontSize:12, color:"var(--text-muted)" }}>Period:</span>
        {[6,24,48,168].map(h=>(
          <button key={h} className={`btn btn-sm ${hours===h?"btn-primary":"btn-secondary"}`} onClick={()=>setHours(h)}>
            {h<24?`${h}h`:h===24?"24h":h===48?"2d":"7d"}
          </button>
        ))}
      </div>

      <div className="page-body">
        <div className="page-inner">
          {/* KPI row */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12 }}>
            {loading ? [1,2,3,4,5].map(i=><div key={i} className="skeleton" style={{ height:90, borderRadius:14 }} />) :
              kpis.map(k=>(
                <div key={k.label} className="stat-card">
                  <div className="stat-label">{k.label}</div>
                  <div className="stat-value">{k.value}</div>
                  <div className="stat-sub">{k.sub}</div>
                </div>
              ))
            }
          </div>

          {/* Requests over time */}
          <div className="card">
            <div className="card-header"><span className="card-title">Requests Over Time</span></div>
            <div className="card-body" style={{ height:200 }}>
              {loading ? <div className="skeleton" style={{ height:"100%", borderRadius:8 }} /> :
              timeseries.length===0 ? <div className="empty-state" style={{ padding:20 }}><div style={{ color:"var(--text-muted)", fontSize:13 }}>No data for this period</div></div> : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timeseries}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" />
                    <XAxis dataKey="time" tick={{ fontSize:10, fill:"var(--text-muted)" }} />
                    <YAxis tick={{ fontSize:10, fill:"var(--text-muted)" }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="requests" stroke="#6366f1" fill="rgba(99,102,241,0.12)" name="Requests" />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Token usage + pie side by side */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
            <div className="card">
              <div className="card-header"><span className="card-title">Token Usage by Hour</span></div>
              <div className="card-body" style={{ height:200 }}>
                {loading ? <div className="skeleton" style={{ height:"100%", borderRadius:8 }} /> :
                timeseries.length===0 ? <div className="empty-state" style={{ padding:20 }}><div style={{ color:"var(--text-muted)", fontSize:13 }}>No data</div></div> : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={timeseries}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" />
                      <XAxis dataKey="time" tick={{ fontSize:10, fill:"var(--text-muted)" }} />
                      <YAxis tick={{ fontSize:10, fill:"var(--text-muted)" }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="tokens_in"  fill="#6366f1" name="Input" radius={[3,3,0,0]} />
                      <Bar dataKey="tokens_out" fill="#10b981" name="Output" radius={[3,3,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header"><span className="card-title">Tokens by Model</span></div>
              <div className="card-body" style={{ height:200, display:"flex", alignItems:"center", justifyContent:"center" }}>
                {loading ? <div className="skeleton" style={{ height:"100%", width:"100%", borderRadius:8 }} /> :
                pieData.length===0 ? <div style={{ color:"var(--text-muted)", fontSize:13 }}>No model usage data</div> : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} cx="40%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value">
                        {pieData.map((e,i)=><Cell key={i} fill={e.color} />)}
                      </Pie>
                      <Legend iconType="circle" formatter={(v)=><span style={{ fontSize:11, color:"var(--text-secondary)" }}>{v}</span>} />
                      <Tooltip formatter={(v:any)=>[fmt(v),"Tokens"]} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>

          {/* Model stats table */}
          {byModel.length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title">Model Performance</span></div>
              <div style={{ overflowX:"auto" }}>
                <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
                  <thead>
                    <tr style={{ borderBottom:"1px solid var(--border-soft)" }}>
                      {["Model","Requests","Input Tokens","Output Tokens","Total Tokens","Avg Latency"].map(h=>(
                        <th key={h} style={{ padding:"10px 16px", textAlign:"left", fontSize:11, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.07em", color:"var(--text-muted)" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {byModel.map(m=>(
                      <tr key={m.model_name} style={{ borderBottom:"1px solid var(--border-soft)" }}>
                        <td style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12 }}>{m.model_name}</td>
                        <td style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12 }}>{fmt(m.requests)}</td>
                        <td style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12 }}>{fmt(m.tokens_input)}</td>
                        <td style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12 }}>{fmt(m.tokens_output)}</td>
                        <td style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12, fontWeight:600 }}>{fmt(m.total_tokens)}</td>
                        <td style={{ padding:"10px 16px", fontFamily:"var(--font-mono)", fontSize:12 }}>{m.avg_latency_ms}ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* System metrics */}
          {sysMetrics.length > 0 && (
            <div className="card">
              <div className="card-header"><span className="card-title">System Health</span></div>
              <div className="card-body" style={{ height:180 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sysMetrics}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-soft)" />
                    <XAxis dataKey="time" tick={{ fontSize:10, fill:"var(--text-muted)" }} />
                    <YAxis domain={[0,100]} tick={{ fontSize:10, fill:"var(--text-muted)" }} unit="%" />
                    <Tooltip content={<CustomTooltip />} formatter={(v:any)=>[`${v}%`]} />
                    <Area type="monotone" dataKey="gpu_util" stroke="#6366f1" fill="rgba(99,102,241,0.10)" name="GPU" />
                    <Area type="monotone" dataKey="vram_pct" stroke="#10b981" fill="rgba(16,185,129,0.10)" name="VRAM" />
                    <Area type="monotone" dataKey="ram_pct"  stroke="#f59e0b" fill="rgba(245,158,11,0.10)"  name="RAM" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
