import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";
import type { Conversation } from "../common/types";

function relTime(s: string) {
  const diff = Date.now() - new Date(s).getTime();
  const m = Math.floor(diff/60000), h = Math.floor(m/60), d = Math.floor(h/24);
  if (d>0) return `${d}d ago`; if (h>0) return `${h}h ago`; if (m>0) return `${m}m ago`; return "just now";
}

export function ConversationsPage() {
  const [convs, setConvs]     = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch]   = useState("");
  const [archived, setArchived] = useState(false);
  const [page, setPage] = useState({ pg_no:1, pg_size:20, total_records:0, total_pg:0 });
  const [editing, setEditing] = useState<string|null>(null);
  const [editTitle, setEditTitle] = useState("");
  const { toast } = useToast();
  const navigate  = useNavigate();

  const load = async () => {
    try {
      const params = new URLSearchParams({ pg_no:String(page.pg_no), pg_size:String(page.pg_size), archived: String(archived) });
      if (search) params.set("q", search);
      const r = await api.get<any>(`/conversations?${params}`);
      setConvs(r.items || []);
      if (r.page) setPage(r.page);
    } catch (e:any) { toast(e.message,"error"); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [archived, search, page.pg_no, page.pg_size]);

  const deleteConv = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    await api.delete(`/conversations/${id}`);
    toast("Deleted","success");
    load();
  };

  const archiveConv = async (id: string, val: boolean, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.patch(`/conversations/${id}`, { is_archived: val });
    toast(val?"Archived":"Unarchived","success");
    load();
  };

  const saveTitle = async (id: string) => {
    if (!editTitle.trim()) return;
    await api.patch(`/conversations/${id}`, { title: editTitle.trim() });
    toast("Renamed","success");
    setEditing(null);
    load();
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      <div className="page-header">
        <div>
          <div className="page-title">≡ Conversations</div>
          <div className="page-subtitle">{page.total_records} conversation{page.total_records!==1?"s":""}</div>
        </div>
        <div className="page-header-sep" />
        <input className="input" placeholder="Search…" value={search} onChange={e=>{ setSearch(e.target.value); setPage(p=>({...p, pg_no:1})); }} style={{ width:200 }} />
        <button className={`btn btn-sm ${!archived?"btn-primary":"btn-secondary"}`} onClick={()=>{ setArchived(false); setPage(p=>({...p, pg_no:1})); }}>Active</button>
        <button className={`btn btn-sm ${archived?"btn-primary":"btn-secondary"}`} onClick={()=>{ setArchived(true); setPage(p=>({...p, pg_no:1})); }}>Archived</button>
        <button className="btn btn-primary btn-sm" onClick={()=>navigate("/chat")}>+ New Chat</button>
      </div>

      <div className="page-body">
        {loading ? (
          <div className="page-inner">{[1,2,3,4].map(i=><div key={i} className="skeleton" style={{ height:72, borderRadius:12, marginBottom:8 }}/>)}</div>
        ) : convs.length===0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">≡</div>
            <div className="empty-state-title">{archived?"No archived conversations":"No conversations yet"}</div>
            <div className="empty-state-desc">{archived?"Archive chats from the active tab.":"Start a chat to see conversations here."}</div>
            {!archived && <button className="btn btn-primary" onClick={()=>navigate("/chat")}>+ Start Chat</button>}
          </div>
        ) : (
          <div style={{ padding:"8px 24px", display:"flex", flexDirection:"column", gap:6 }}>
            {convs.map(c => (
              <div key={c.id} onClick={()=>navigate(`/chat/${c.id}`)}
                style={{ display:"flex", alignItems:"center", gap:12, padding:"14px 16px", background:"var(--bg-surface)", border:"1px solid var(--border-soft)", borderRadius:12, cursor:"pointer", transition:"border-color 150ms, background 150ms" }}
                onMouseEnter={e=>{(e.currentTarget as HTMLDivElement).style.borderColor="var(--border-strong)"; (e.currentTarget as HTMLDivElement).style.background="var(--bg-elevated)";}}
                onMouseLeave={e=>{(e.currentTarget as HTMLDivElement).style.borderColor="var(--border-soft)"; (e.currentTarget as HTMLDivElement).style.background="var(--bg-surface)";}}
              >
                <div style={{ flex:1, minWidth:0 }}>
                  {editing===c.id ? (
                    <input className="input" style={{ padding:"4px 8px", fontSize:14 }} value={editTitle}
                      onChange={e=>setEditTitle(e.target.value)} autoFocus
                      onKeyDown={e=>{ if(e.key==="Enter") saveTitle(c.id); if(e.key==="Escape") setEditing(null); }}
                      onClick={e=>e.stopPropagation()}
                    />
                  ) : (
                    <div style={{ fontWeight:600, fontSize:14, color:"var(--text-primary)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{c.title}</div>
                  )}
                  <div style={{ display:"flex", gap:10, marginTop:4, fontSize:11, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>
                    <span className="badge badge-muted">{c.model_name}</span>
                    <span>{c.context_window/1024}K ctx</span>
                    <span>{c.total_tokens.toLocaleString()} tokens</span>
                    <span>{(c.message_count || 0).toLocaleString()} messages</span>
                    <span>{relTime(c.updated_at)}</span>
                  </div>
                </div>
                <div style={{ display:"flex", gap:4 }} onClick={e=>e.stopPropagation()}>
                  <button className="btn btn-ghost btn-sm" onClick={()=>{ setEditing(c.id); setEditTitle(c.title); }}>Rename</button>
                  <button className="btn btn-ghost btn-sm" onClick={e=>archiveConv(c.id, !c.is_archived, e)}>{c.is_archived?"Unarchive":"Archive"}</button>
                  <button className="btn btn-danger btn-sm" onClick={e=>deleteConv(c.id,e)}>Delete</button>
                </div>
              </div>
            ))}
            {page.total_pg > 1 && (
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"12px 2px" }}>
                <button className="btn btn-secondary btn-sm" disabled={page.pg_no<=1} onClick={()=>setPage(p=>({...p, pg_no:p.pg_no-1}))}>Previous</button>
                <span style={{ fontSize:12, color:"var(--text-muted)", fontFamily:"var(--font-mono)" }}>Page {page.pg_no} / {page.total_pg}</span>
                <button className="btn btn-secondary btn-sm" disabled={page.pg_no>=page.total_pg} onClick={()=>setPage(p=>({...p, pg_no:p.pg_no+1}))}>Next</button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
