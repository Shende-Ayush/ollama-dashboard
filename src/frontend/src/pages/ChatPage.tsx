import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { api, API_BASE } from "../api/client";
import { useToast } from "../hooks/useToast";
import type { ChatMessage } from "../common/types";

const MODELS_FALLBACK = ["llama3.2:3b","mistral:7b","qwen2.5:7b","gemma3:4b","phi4","codellama:7b"];
const CTX_OPTIONS = [2048, 4096, 8192, 16384, 32768];

function CodeBlock({ language, text }: { language: string; text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div style={{ position:"relative", margin:"8px 0", borderRadius:10, overflow:"hidden", border:"1px solid var(--border)" }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", padding:"5px 12px", background:"var(--bg-overlay)", borderBottom:"1px solid var(--border)" }}>
        <span style={{ fontFamily:"var(--font-mono)", fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.1em", color:"var(--accent)" }}>{language || "text"}</span>
        <button className="btn btn-ghost btn-sm" style={{ fontSize:11 }}
          onClick={async () => { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>
      <SyntaxHighlighter language={language} style={vscDarkPlus}
        customStyle={{ margin:0, background:"var(--bg-base)", fontSize:12, lineHeight:1.65 }}>
        {text}
      </SyntaxHighlighter>
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  return (
    <div style={{ fontSize:14, lineHeight:1.75, color:"var(--text-primary)" }}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        code(props) {
          const { className, children } = props;
          const match = /language-(\w+)/.exec(className || "");
          const text = String(children ?? "").replace(/\n$/, "");
          if (!match) return <code style={{ fontFamily:"var(--font-mono)", fontSize:12, background:"var(--bg-elevated)", border:"1px solid var(--border)", borderRadius:4, padding:"1px 5px" }}>{children}</code>;
          return <CodeBlock language={match[1]} text={text} />;
        },
        p: ({children}) => <p style={{ marginBottom:8 }}>{children}</p>,
        ul: ({children}) => <ul style={{ paddingLeft:20, marginBottom:8 }}>{children}</ul>,
        ol: ({children}) => <ol style={{ paddingLeft:20, marginBottom:8 }}>{children}</ol>,
        blockquote: ({children}) => <blockquote style={{ borderLeft:"3px solid var(--accent)", padding:"8px 12px", margin:"8px 0", color:"var(--text-secondary)", background:"var(--bg-elevated)", borderRadius:"0 6px 6px 0" }}>{children}</blockquote>,
        table: ({children}) => <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13, margin:"8px 0" }}>{children}</table>,
        th: ({children}) => <th style={{ border:"1px solid var(--border)", padding:"6px 10px", background:"var(--bg-elevated)", fontWeight:600, textAlign:"left" }}>{children}</th>,
        td: ({children}) => <td style={{ border:"1px solid var(--border)", padding:"6px 10px" }}>{children}</td>,
      }}>{content}</ReactMarkdown>
    </div>
  );
}

export function ChatPage() {
  const { convId }   = useParams<{ convId?: string }>();
  const [sp]         = useSearchParams();
  const navigate     = useNavigate();
  const { toast }    = useToast();

  const [models, setModels]         = useState<string[]>([]);
  const [model, setModel]           = useState(sp.get("model") || "llama3.2:3b");
  const [contextTokens, setCtx]     = useState(4096);
  const [conversationId, setConvId] = useState<string | null>(convId || null);
  const [messages, setMessages]     = useState<ChatMessage[]>([]);
  const [input, setInput]           = useState("");
  const [status, setStatus]         = useState<"idle" | "loading" | "streaming">("idle");
  const [requestId, setRequestId]   = useState("");
  const esRef        = useRef<EventSource | null>(null);
  const msgsEndRef   = useRef<HTMLDivElement>(null);
  const textareaRef  = useRef<HTMLTextAreaElement>(null);
  const msgContainer = useRef<HTMLDivElement>(null);
  const isNearBottom = useRef(true);

  // Load models
  useEffect(() => {
    api.get<any>("/models?pg_size=100")
      .then(r => { const names = (r.items || []).map((m: any) => m.name); setModels(names.length ? names : MODELS_FALLBACK); if (!sp.get("model") && names.length) setModel(names[0]); })
      .catch(() => setModels(MODELS_FALLBACK));
  }, []);

  // Load conversation
  useEffect(() => {
    if (!convId) return;
    api.get<any>(`/conversations/${convId}`).then(r => {
      setConvId(r.id); setModel(r.model_name); setCtx(r.context_window);
      setMessages(r.messages.map((m: any) => ({ id: m.id, role: m.role, content: m.content, token_count: m.token_count })));
    }).catch(e => toast(e.message, "error"));
  }, [convId]);

  useEffect(() => { if (isNearBottom.current) msgsEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleScroll = () => {
    const el = msgContainer.current;
    if (el) isNearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const usedTokens = useMemo(() => Math.round(messages.reduce((a, m) => a + m.content.length / 4, 0)), [messages]);
  const ctxPct = Math.min(100, (usedTokens / contextTokens) * 100);

  const send = async () => {
    if (!input.trim() || status === "streaming") return;
    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: input.trim() };
    const asstId = crypto.randomUUID();
    const newMessages = [...messages, userMsg];
    setMessages([...newMessages, { id: asstId, role: "assistant", content: "" }]);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "44px";
    setStatus("loading");
    isNearBottom.current = true;

    try {
      const startRes = await api.post<any>("/chat/start-auth", {
        model,
        messages: newMessages.map(m => ({ role: m.role, content: m.content })),
        context_tokens: contextTokens,
        conversation_id: conversationId,
      });
      const rid = startRes.request_id;
      setRequestId(rid);
      if (startRes.conversation_id && !conversationId) {
        setConvId(startRes.conversation_id);
        navigate(`/chat/${startRes.conversation_id}`, { replace: true });
      }

      setStatus("streaming");
      const es = new EventSource(`${API_BASE}/chat/stream?request_id=${rid}`);
      esRef.current = es;
      es.onmessage = evt => {
        try {
          const data = JSON.parse(evt.data);
          if (data.event_type === "token") setMessages(prev => prev.map(m => m.id === asstId ? { ...m, content: m.content + data.payload.token } : m));
          if (data.event_type === "done" || data.event_type === "stopped") { es.close(); esRef.current = null; setStatus("idle"); }
        } catch {}
      };
      es.onerror = () => { es.close(); esRef.current = null; setStatus("idle"); toast("Stream error", "error"); };
    } catch (e: any) { setStatus("idle"); toast(e.message, "error"); }
  };

  const stop = async () => {
    esRef.current?.close(); esRef.current = null;
    if (requestId) await api.post("/chat/stop", { request_id: requestId }).catch(() => {});
    setStatus("idle");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };
  const handleInput   = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "44px";
    e.target.style.height = Math.min(e.target.scrollHeight, 180) + "px";
  };

  const newChat = () => { setMessages([]); setConvId(null); setStatus("idle"); navigate("/chat", { replace: true }); };

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      {/* Header */}
      <div className="page-header" style={{ gap:8, flexWrap:"wrap" }}>
        <div className="page-title">⌁ Chat</div>
        <div style={{ display:"flex", alignItems:"center", gap:6, background:"var(--bg-elevated)", border:"1px solid var(--border)", borderRadius:10, padding:"4px 10px" }}>
          <span style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em", color:"var(--text-muted)" }}>Model</span>
          <select className="select" value={model} onChange={e => setModel(e.target.value)} style={{ border:"none", background:"transparent", padding:"2px 20px 2px 4px" }}>
            {models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:6 }}>
          <span style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em", color:"var(--text-muted)" }}>Context</span>
          <select className="select btn-sm" value={contextTokens} onChange={e => setCtx(Number(e.target.value))}>
            {CTX_OPTIONS.map(c => <option key={c} value={c}>{c >= 1024 ? `${c / 1024}K` : c}</option>)}
          </select>
          <div style={{ display:"flex", alignItems:"center", gap:4 }}>
            <div className="progress-wrap" style={{ width:60, height:3 }}>
              <div className="progress-fill" style={{ width:`${ctxPct}%`, background: ctxPct > 85 ? "var(--red)" : ctxPct > 65 ? "var(--amber)" : "var(--accent)" }} />
            </div>
            <span style={{ fontFamily:"var(--font-mono)", fontSize:10, color:"var(--text-muted)" }}>{usedTokens}/{contextTokens}</span>
          </div>
        </div>
        <div className="page-header-sep" />
        <button className="btn btn-secondary btn-sm" onClick={newChat}>+ New Chat</button>
      </div>

      {/* Messages */}
      <div ref={msgContainer} onScroll={handleScroll} style={{ flex:1, overflowY:"auto", padding:"20px 0", display:"flex", flexDirection:"column" }}>
        {messages.length === 0 ? (
          <div className="empty-state" style={{ flex:1 }}>
            <div className="empty-state-icon" style={{ fontSize:52 }}>⌁</div>
            <div className="empty-state-title">Start a conversation</div>
            <div className="empty-state-desc">Ask anything. Markdown, code highlighting, and streaming are included.</div>
          </div>
        ) : (
          <div style={{ maxWidth:820, margin:"0 auto", width:"100%", padding:"0 20px", display:"flex", flexDirection:"column", gap:16 }}>
            {messages.map((m, i) => (
              <div key={m.id} className="animate-slideup" style={{ display:"flex", flexDirection:"column", alignItems: m.role === "user" ? "flex-end" : "flex-start", maxWidth:"85%", alignSelf: m.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em", color: m.role === "user" ? "var(--accent)" : "var(--text-muted)", marginBottom:4, padding:"0 4px", display:"flex", alignItems:"center", gap:6 }}>
                  {m.role === "user" ? "You" : "Assistant"}
                  {status === "streaming" && i === messages.length - 1 && m.role === "assistant" && (
                    <span className="live-dot" style={{ width:5, height:5 }} />
                  )}
                </div>
                <div style={{ padding:"12px 16px", borderRadius: m.role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px", background: m.role === "user" ? "var(--bg-overlay)" : "var(--bg-surface)", border: m.role === "user" ? "1px solid var(--border-accent)" : "1px solid var(--border-soft)", color: m.role === "user" ? "#c7d2fe" : "var(--text-primary)" }}>
                  {m.content === "" && status === "streaming" ? (
                    <span style={{ color:"var(--text-muted)", fontStyle:"italic", fontSize:13 }}>Thinking…</span>
                  ) : (
                    <MarkdownContent content={m.content} />
                  )}
                </div>
                <div style={{ display:"flex", gap:4, marginTop:4, padding:"0 4px", opacity:0.6 }}>
                  <button className="btn btn-ghost btn-sm" style={{ fontSize:11 }}
                    onClick={() => navigator.clipboard.writeText(m.content).then(() => {})}>Copy</button>
                  {m.token_count != null && <span style={{ fontSize:10, color:"var(--text-muted)", fontFamily:"var(--font-mono)", paddingTop:3 }}>{m.token_count} tokens</span>}
                </div>
              </div>
            ))}
            <div ref={msgsEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ padding:"12px 20px", borderTop:"1px solid var(--border-soft)", background:"var(--bg-surface)", flexShrink:0 }}>
        <div style={{ maxWidth:820, margin:"0 auto" }}>
          <div style={{ display:"flex", gap:8, alignItems:"flex-end", background:"var(--bg-elevated)", border:`1px solid ${input ? "var(--accent)" : "var(--border-strong)"}`, borderRadius:14, padding:"8px 8px 8px 14px", boxShadow: input ? "0 0 0 3px var(--accent-glow)" : "none", transition:"border-color 150ms, box-shadow 150ms" }}>
            <textarea ref={textareaRef} value={input} onChange={handleInput} onKeyDown={handleKeyDown}
              placeholder="Message… (Enter to send · Shift+Enter for newline)"
              style={{ flex:1, background:"transparent", border:"none", color:"var(--text-primary)", fontFamily:"var(--font-ui)", fontSize:14, lineHeight:1.55, outline:"none", resize:"none", height:44, maxHeight:180, overflowY:"auto" }} />
            {status === "streaming" || status === "loading" ? (
              <button className="btn btn-danger btn-sm" style={{ height:36, flexShrink:0 }} onClick={stop}>◼ Stop</button>
            ) : (
              <button className="btn btn-primary btn-icon-only" style={{ width:36, height:36, flexShrink:0, borderRadius:10 }} onClick={send} disabled={!input.trim()}>↑</button>
            )}
          </div>
          <div style={{ marginTop:5, textAlign:"center", fontSize:11, color:"var(--text-muted)" }}>
            {conversationId ? `Saved · ${messages.length} messages` : "New conversation — saved automatically"}
          </div>
        </div>
      </div>
    </div>
  );
}
