import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);

// --- PWA: register service worker & capture install prompt ---
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .catch((err) => console.warn("[PWA] SW registration failed:", err));
  });
}

// Cache the install-prompt event so a UI button can trigger it later.
window.deferredPWAInstallPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  window.deferredPWAInstallPrompt = e;
  window.dispatchEvent(new Event("pwa-installable"));
});
window.addEventListener("appinstalled", () => {
  window.deferredPWAInstallPrompt = null;
  window.dispatchEvent(new Event("pwa-installed"));
});
