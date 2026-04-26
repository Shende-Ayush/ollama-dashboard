import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
type Theme = "dark" | "light";
interface Ctx { theme: Theme; toggle: () => void; }
const ThemeCtx = createContext<Ctx>({ theme: "dark", toggle: () => {} });
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("theme") as Theme) || "dark");
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); localStorage.setItem("theme", theme); }, [theme]);
  const value = useMemo(() => ({ theme, toggle: () => setTheme(t => t === "dark" ? "light" : "dark") }), [theme]);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}
export const useTheme = () => useContext(ThemeCtx);
