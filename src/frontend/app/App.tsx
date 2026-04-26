import React from "react";
import { Navigate, Route, Routes, useLocation, NavLink } from "react-router-dom";
import { ToastProvider } from "../hooks/useToast";
import { useTheme } from "../theme/ThemeProvider";
import { ModelsPage }        from "../pages/ModelsPage";
import { ChatPage }          from "../pages/ChatPage";
import { ConversationsPage } from "../pages/ConversationsPage";
import { TerminalPage }      from "../pages/TerminalPage";
import { AnalyticsPage }     from "../pages/AnalyticsPage";
import { DiscoverPage }      from "../pages/DiscoverPage";
import { SettingsBar }       from "./SettingsBar";

const NAV = [
  { to: "/models",        icon: "⬡", label: "Models",        section: "main" },
  { to: "/discover",      icon: "◎", label: "Discover",       section: "main" },
  { to: "/chat",          icon: "⌁", label: "Chat",           section: "main" },
  { to: "/conversations", icon: "≡", label: "Conversations",  section: "main" },
  { to: "/terminal",      icon: "$", label: "Terminal",       section: "tools" },
  { to: "/analytics",     icon: "◈", label: "Analytics",      section: "tools" },
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
              <NavLink key={n.to} to={n.to} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{n.icon}</span>
                {n.label}
              </NavLink>
            ))}

            <span className="nav-section-label">Tools</span>
            {NAV.filter(n => n.section === "tools").map(n => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>{n.icon}</span>
                {n.label}
              </NavLink>
            ))}
          </div>

          <div className="nav-footer">
            <button className="nav-link" onClick={toggle} style={{ cursor: "pointer" }}>
              <span>{theme === "dark" ? "☀" : "☾"}</span>
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
          </div>
        </nav>

        {/* Main */}
        <div className="main-content">
          <SettingsBar />
          <Routes>
            <Route path="/" element={<Navigate to="/models" replace />} />
            <Route path="/models"        element={<ModelsPage />} />
            <Route path="/discover"      element={<DiscoverPage />} />
            <Route path="/chat"          element={<ChatPage />} />
            <Route path="/chat/:convId"  element={<ChatPage />} />
            <Route path="/conversations" element={<ConversationsPage />} />
            <Route path="/terminal"      element={<TerminalPage />} />
            <Route path="/analytics"     element={<AnalyticsPage />} />
          </Routes>
        </div>
      </div>
    </ToastProvider>
  );
}
