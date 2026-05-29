import React from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { ToastProvider } from "../hooks/useToast";
import { useTheme } from "../theme/ThemeProvider";
import { ErrorBoundary } from "../common/ErrorBoundary";
import { ModelsPage }        from "../pages/ModelsPage";
import { ChatPage }          from "../pages/ChatPage";
import { ConversationsPage } from "../pages/ConversationsPage";
import { TerminalPage }      from "../pages/TerminalPage";
import { AnalyticsPage }     from "../pages/AnalyticsPage";
import { DiscoverPage }      from "../pages/DiscoverPage";
import { SmartCommandsPage } from "../pages/SmartCommandsPage";
import { PromptStudioPage }  from "../pages/PromptStudioPage";
import { AgentsPage }        from "../pages/AgentsPage";
import { HealthPage }        from "../pages/HealthPage";

const NAV = [
  { to: "/models",        icon: "⬡", label: "Models",        section: "main" },
  { to: "/discover",      icon: "◎", label: "Discover",       section: "main" },
  { to: "/chat",          icon: "⌁", label: "Chat",           section: "main" },
  { to: "/conversations", icon: "≡", label: "Conversations",  section: "main" },
  { to: "/terminal",      icon: "$", label: "Terminal",       section: "tools" },
  { to: "/analytics",     icon: "◈", label: "Analytics",      section: "tools" },
  { to: "/smart-commands", icon: "~", label: "Smart Cmds",    section: "ai" },
  { to: "/prompt-studio",  icon: "✎", label: "Prompts",       section: "ai" },
  { to: "/agents",         icon: "@", label: "Agents",        section: "ai" },
  { to: "/health",         icon: "+", label: "Health",        section: "ai" },
];

export function App() {
  const { theme, toggle } = useTheme();

  return (
    <ToastProvider>
      <div className="app-shell">
        {/* Sidebar */}
        <nav className="nav-sidebar">
          <div className="nav-brand">
            <div className="nav-logo">⬡</div>
            <span className="nav-title">Ollama</span>
          </div>

          <div className="nav-links">
            <span className="nav-section-label">Main</span>
            {NAV.filter(n => n.section === "main").map(n => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, width: 16, textAlign: "center" }}>{n.icon}</span>
                {n.label}
              </NavLink>
            ))}

            <span className="nav-section-label">Tools</span>
            {NAV.filter(n => n.section === "tools").map(n => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, width: 16, textAlign: "center" }}>{n.icon}</span>
                {n.label}
              </NavLink>
            ))}

            <span className="nav-section-label">AI</span>
            {NAV.filter(n => n.section === "ai").map(n => (
              <NavLink
                key={n.to}
                to={n.to}
                className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              >
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, width: 16, textAlign: "center" }}>{n.icon}</span>
                {n.label}
              </NavLink>
            ))}
          </div>

          <div className="nav-footer">
            <button className="nav-link" onClick={toggle}>
              <span style={{ width: 16, textAlign: "center" }}>{theme === "dark" ? "☀" : "☾"}</span>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
            <div style={{ padding: "6px 10px", fontSize: 10, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              v2.0 · no-auth mode
            </div>
          </div>
        </nav>

        {/* Main content area */}
        <div className="main-content">
          <Routes>
            <Route path="/"              element={<Navigate to="/models" replace />} />
            <Route path="/models"        element={<ErrorBoundary><ModelsPage /></ErrorBoundary>} />
            <Route path="/discover"      element={<ErrorBoundary><DiscoverPage /></ErrorBoundary>} />
            <Route path="/chat"          element={<ErrorBoundary><ChatPage /></ErrorBoundary>} />
            <Route path="/chat/:convId"  element={<ErrorBoundary><ChatPage /></ErrorBoundary>} />
            <Route path="/conversations" element={<ErrorBoundary><ConversationsPage /></ErrorBoundary>} />
            <Route path="/terminal"      element={<ErrorBoundary><TerminalPage /></ErrorBoundary>} />
            <Route path="/analytics"     element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
            <Route path="/smart-commands" element={<ErrorBoundary><SmartCommandsPage /></ErrorBoundary>} />
            <Route path="/prompt-studio"  element={<ErrorBoundary><PromptStudioPage /></ErrorBoundary>} />
            <Route path="/agents"         element={<ErrorBoundary><AgentsPage /></ErrorBoundary>} />
            <Route path="/health"         element={<ErrorBoundary><HealthPage /></ErrorBoundary>} />
          </Routes>
        </div>
      </div>
    </ToastProvider>
  );
}
