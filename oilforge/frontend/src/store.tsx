/** Global state: auth session, theme, fiscal reporting period. */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from "react";
import { api, getToken, setToken } from "./api";

type UserInfo = { name: string; email: string } | null;
type Period = { start: string; end: string; label: string };

function fiscalYear(year: number): Period {
  return { start: `${year}-01-01`, end: `${year}-12-31`, label: `Fiscal ${year}` };
}

type Store = {
  user: UserInfo;
  login: (u: NonNullable<UserInfo>, token: string) => void;
  logout: () => void;
  dark: boolean;
  toggleDark: () => void;
  period: Period;
  setPeriod: (p: Period) => void;
  year: number;
};

const Ctx = createContext<Store>(null!);
export const useStore = () => useContext(Ctx);
export { fiscalYear };
export type { Period };

export function StoreProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo>(null);
  const [booted, setBooted] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("oilforge_theme") === "dark" ||
      (localStorage.getItem("oilforge_theme") === null &&
        window.matchMedia("(prefers-color-scheme: dark)").matches),
  );
  const [period, setPeriod] = useState<Period>(() => fiscalYear(new Date().getFullYear()));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("oilforge_theme", dark ? "dark" : "light");
  }, [dark]);

  useEffect(() => {
    if (!getToken()) { setBooted(true); return; }
    api.get("/api/auth/me")
      .then((me) => setUser({ name: me.name, email: me.email }))
      .catch(() => setToken(null))
      .finally(() => setBooted(true));
  }, []);

  const login = useCallback((u: NonNullable<UserInfo>, token: string) => {
    setToken(token);
    setUser(u);
  }, []);
  const logout = useCallback(() => { setToken(null); setUser(null); }, []);
  const toggleDark = useCallback(() => setDark((d) => !d), []);

  const value = useMemo(
    () => ({
      user, login, logout, dark, toggleDark, period, setPeriod,
      year: new Date(period.end + "T00:00:00").getFullYear(),
    }),
    [user, login, logout, dark, toggleDark, period],
  );

  if (!booted) return null;
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
