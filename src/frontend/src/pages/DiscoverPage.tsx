import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import { useToast } from "../hooks/useToast";
import type { PopularModel } from "../common/types";

const TAGS_FILTER = ["tools","thinking","vision","audio"];

type ModelTag = {
  tag: string;
  size: string;
  context: string;
  input: string;
};

function normalizePopularModels(data: any[]): PopularModel[] {
  if (!Array.isArray(data)) return [];

  return data.map((meta: any) => ({
    id: meta.name,
    description: meta.description || "No description",
    params: meta.sizes?.length ? meta.sizes.join(", ") : "–",
    size_gb: null,
    tags: meta.capabilities || [],
    installed: false,
    recommended: meta.capabilities?.includes("thinking") || false,
  }));
}

export function DiscoverPage() {
  const [models, setModels] = useState<PopularModel[]>([]);
  const [search, setSearch] = useState("");
  const [capability, setCapability] = useState("");
  const [loading, setLoading] = useState(true);

  const [selectedModel, setSelectedModel] = useState<PopularModel | null>(null);
  const [tags, setTags] = useState<ModelTag[]>([]);
  const [tagsLoading, setTagsLoading] = useState(false);

  const [pulling, setPulling] = useState<string | null>(null);

  const { toast } = useToast();

  /* Fetch models */
  useEffect(() => {
    const t = setTimeout(() => {
      (async () => {
        try {
          const params = new URLSearchParams();
          if (search) params.set("search", search);

          const r = await api.get<any>(`/models/popular?${params}`);
          const normalized = normalizePopularModels((r.data || r).items);

          setModels(normalized);
        } catch (e: any) {
          console.error(e);
          toast(e.message || "Failed to load models", "error");
        } finally {
          setLoading(false);
        }
      })();
    }, 300);

    return () => clearTimeout(t);
  }, [search]);

  /* Fetch tags */
  const fetchTags = async (modelId: string) => {
    try {
      const res = await api.get(`/models/tags?model=${modelId}`);
      const raw = res?.data ?? res;

      const parsed =
        Array.isArray(raw) ? raw :
        Array.isArray(raw?.items) ? raw.items :
        Array.isArray(raw?.tags) ? raw.tags :
        [];

      setTags(parsed);
    } catch (e: any) {
      console.error(e);
      toast(e.message || "Failed to load tags", "error");
      setTags([]);
    } finally {
      setTagsLoading(false);
    }
  };

  /* Pull model */
  const pullModel = async (model: string) => {
    try {
      setPulling(model);
      toast(`Pulling ${model}...`, "info");

      await api.post("/models/pull", { model });

      toast(`Started pulling ${model}`, "success");
    } catch (e: any) {
      console.error(e);
      toast(e.message || "Failed to pull model", "error");
    } finally {
      setPulling(null);
    }
  };

  const filtered = models
    .filter(m => !search || m.id?.toLowerCase().includes(search.toLowerCase()))
    .filter(m => !capability || (m.tags || []).includes(capability));

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%", overflow:"hidden" }}>
      
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">◎ Discover Models</div>
          <div className="page-subtitle">
            Model catalog · {filtered.length} models
          </div>
        </div>
      </div>

      <div className="page-body">
        <div className="page-inner">

          {/* Filters */}
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            <input
              className="input"
              placeholder="Search models…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ width:240 }}
            />

            <select
              className="select"
              value={capability}
              onChange={e => setCapability(e.target.value)}
            >
              <option value="">All Capabilities</option>
              {TAGS_FILTER.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>

          {/* Grid */}
          {loading ? (
            <div className="grid-3">
              {[1,2,3,4,5,6].map(i => (
                <div key={i} className="skeleton" style={{ height:180, borderRadius:14 }}/>
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">◎</div>
              <div className="empty-state-title">No matches</div>
            </div>
          ) : (
            <div className="grid-3">
              {filtered.map(m => (
                <ModelCard
                  key={m.id}
                  model={m}
                  onClick={() => {
                    setTags([]);
                    setTagsLoading(true);
                    setSelectedModel(m);
                    fetchTags(m.id.split(":")[0]);
                  }}
                />
              ))}
            </div>
          )}

        </div>
      </div>

      {/* MODAL */}
      {selectedModel && (
        <div
          onClick={() => setSelectedModel(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)", // slightly softer for light mode
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 99999
          }}
        >
          <div
            key={selectedModel.id}
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "var(--bg-elevated)",
              padding: 20,
              borderRadius: 12,
              width: 700,
              maxHeight: "80vh",
              display: "flex",
              flexDirection: "column",
              color: "var(--text-primary)"
            }}
          >
            <h2>{selectedModel.id}</h2>
            <p style={{ opacity: 0.7 }}>{selectedModel.description}</p>

            <hr style={{ margin: "10px 0", borderColor: "var(--border-soft)" }} />

            {tagsLoading ? (
              <div>Loading tags...</div>
            ) : !tags || tags.length === 0 ? (
              <div style={{ opacity: 0.6 }}>No tags available</div>
            ) : (
              <div
                style={{
                  border: "1px solid var(--border-soft)",
                  borderRadius: 10,
                  fontSize: 13,
                  display: "flex",
                  flexDirection: "column",
                  flex: 1,
                  minHeight: 0,
                  background: "var(--bg-surface)",
                  color: "var(--text-primary)"
                }}
              >
                {/* Header */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "3fr 1fr 1fr 1.5fr auto",
                    padding: "12px 14px",
                    background: "var(--bg-muted)",
                    fontSize: 12,
                    opacity: 0.8,
                    fontWeight: 500
                  }}
                >
                  <div>Tag</div>
                  <div style={{ textAlign: "center" }}>Size</div>
                  <div style={{ textAlign: "center" }}>Context</div>
                  <div style={{ textAlign: "center" }}>Input</div>
                  <div></div>
                </div>

                {/* Scrollable rows */}
                <div
                  style={{
                    overflowY: "auto",
                    maxHeight: "50vh"
                  }}
                >
                  {tags.map((t, i) => (
                    <div
                      key={t.tag || i}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "3fr 1fr 1fr 1.5fr auto",
                        padding: "12px 14px",
                        borderTop: "1px solid var(--border-soft)",
                        alignItems: "center",
                        background: "var(--bg-surface)"
                      }}
                    >
                      <div style={{ fontFamily: "var(--font-mono)" }}>{t.tag}</div>
                      <div style={{ textAlign: "center" }}>{t.size}</div>
                      <div style={{ textAlign: "center" }}>{t.context}</div>
                      <div style={{ textAlign: "center" }}>{t.input}</div>

                      <div style={{ display: "flex", justifyContent: "flex-end" }}>
                        <button
                          className="btn btn-primary btn-sm"
                          disabled={pulling === t.tag}
                          onClick={() => pullModel(t.tag)}
                        >
                          {pulling === t.tag ? "Pulling..." : "⬇ Pull"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ModelCard({
  model,
  onClick
}:{
  model: PopularModel;
  onClick: () => void;
}) {
  return (
    <div
      className="card"
      onClick={onClick}
      style={{
        cursor:"pointer",
        display:"flex",
        flexDirection:"column",
        borderColor: model.recommended ? "var(--border-accent)" : "var(--border-soft)",
        transition:"all 0.15s ease"
      }}
    >
      <div style={{ padding:"14px 16px", display:"flex", flexDirection:"column", gap:8 }}>

        {model.recommended && (
          <span className="badge badge-accent">★ Recommended</span>
        )}

        <div style={{ fontFamily:"var(--font-mono)", fontSize:13, fontWeight:600 }}>
          {model.id}
        </div>

        <div style={{ fontSize:12, color:"var(--text-secondary)", lineHeight:1.6 }}>
          {model.description}
        </div>

        <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
          <span className="badge badge-muted">{model.params}</span>

          {(model.tags || []).map(t => (
            <span key={t} className="badge badge-cyan">{t}</span>
          ))}
        </div>

      </div>
    </div>
  );
}