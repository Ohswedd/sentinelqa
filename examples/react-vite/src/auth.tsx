import { ReactNode, createContext, useCallback, useContext, useMemo, useState } from "react";

interface AuthState {
  user: string | null;
  token: string | null;
  signIn: (username: string, token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const signIn = useCallback((username: string, nextToken: string) => {
    setUser(username);
    setToken(nextToken);
  }, []);

  const signOut = useCallback(() => {
    setUser(null);
    setToken(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, token, signIn, signOut }),
    [user, token, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth used outside <AuthProvider>");
  return ctx;
}
