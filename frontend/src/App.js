import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Tesserati from "./pages/Tesserati";
import Ricevute from "./pages/Ricevute";
import Abbonamenti from "./pages/Abbonamenti";
import Movimenti from "./pages/Movimenti";
import Compensi from "./pages/Compensi";
import Report from "./pages/Report";
import Admin from "./pages/Admin";
import Calendario from "./pages/Calendario";
import LibroSoci from "./pages/LibroSoci";

const Loader = () => (
  <div className="min-h-screen flex items-center justify-center bg-[#050505] text-white/60">
    Caricamento…
  </div>
);

function Protected({ children, adminOnly = false }) {
  const { user } = useAuth();
  if (user === null) return <Loader />;
  if (user === false) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

function LoginRoute() {
  const { user } = useAuth();
  if (user === null) return <Loader />;
  if (user) return <Navigate to="/" replace />;
  return <Login />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginRoute />} />
          <Route path="/" element={<Protected><Dashboard /></Protected>} />
          <Route path="/tesserati" element={<Protected><Tesserati /></Protected>} />
          <Route path="/libro-soci" element={<Protected><LibroSoci /></Protected>} />
          <Route path="/ricevute" element={<Protected><Ricevute /></Protected>} />
          <Route path="/abbonamenti" element={<Protected><Abbonamenti /></Protected>} />
          <Route path="/calendario" element={<Protected><Calendario /></Protected>} />
          <Route path="/movimenti" element={<Protected><Movimenti /></Protected>} />
          <Route path="/compensi" element={<Protected><Compensi /></Protected>} />
          <Route path="/report" element={<Protected><Report /></Protected>} />
          <Route path="/admin" element={<Protected adminOnly><Admin /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
