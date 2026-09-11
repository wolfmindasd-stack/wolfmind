import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null=checking, false=anon, obj=user

  // 1️⃣ Controlla se esiste un token salvato
  useEffect(() => {
    (async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          setUser(false);
          return;
        }

        // 2️⃣ Chiama /auth/me con il token
        const { data } = await api.get("/auth/me");
        setUser(data);
      } catch {
        setUser(false);
      }
    })();
  }, []);

  // 3️⃣ LOGIN — salva token + imposta utente
  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });

    // Salva il token JWT
    localStorage.setItem("token", data.access_token);

    // Imposta l’utente
    setUser(data.user);

    return data.user;
  };

  // 4️⃣ LOGOUT — rimuove token
  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {}

    localStorage.removeItem("token");
    setUser(false);
  };

  return (
    <AuthCtx.Provider value={{ user, setUser, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
