import React, { useEffect, useState } from "react";
import { Download, Share, Smartphone, X } from "lucide-react";

/**
 * PWA install helper.
 * - Android/Chrome/Edge/desktop: uses the deferred `beforeinstallprompt` event.
 * - iOS Safari: no programmatic API, show textual instructions.
 * - Hides itself entirely when the app is already installed (standalone mode).
 */
export default function InstallPWAButton({ compact = false }) {
  const [installable, setInstallable] = useState(!!window.deferredPWAInstallPrompt);
  const [installed, setInstalled] = useState(false);
  const [showIosGuide, setShowIosGuide] = useState(false);

  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent) && !/crios|fxios/i.test(navigator.userAgent);
  const isStandalone =
    window.matchMedia?.("(display-mode: standalone)").matches ||
    window.navigator.standalone === true;

  useEffect(() => {
    const onInstallable = () => setInstallable(true);
    const onInstalled = () => {
      setInstallable(false);
      setInstalled(true);
    };
    window.addEventListener("pwa-installable", onInstallable);
    window.addEventListener("pwa-installed", onInstalled);
    return () => {
      window.removeEventListener("pwa-installable", onInstallable);
      window.removeEventListener("pwa-installed", onInstalled);
    };
  }, []);

  if (isStandalone || installed) return null;

  const handleClick = async () => {
    if (isIos) {
      setShowIosGuide(true);
      return;
    }
    const evt = window.deferredPWAInstallPrompt;
    if (!evt) {
      // Fallback: on some browsers we can't trigger install; show iOS-style guide.
      setShowIosGuide(true);
      return;
    }
    try {
      evt.prompt();
      const choice = await evt.userChoice;
      if (choice.outcome === "accepted") {
        setInstallable(false);
      }
      window.deferredPWAInstallPrompt = null;
    } catch (e) {
      console.warn("[PWA] install prompt failed:", e);
    }
  };

  // On non-iOS browsers that never fired beforeinstallprompt (e.g. Firefox desktop),
  // still keep a subtle entry point so the user can see the iOS-style instructions.
  const label = isIos ? "Installa su iPhone" : "Installa App";

  return (
    <>
      <button
        onClick={handleClick}
        data-testid="pwa-install-btn"
        className={`w-full flex items-center justify-center gap-2 rounded-md
                    border border-[#34C759]/40 text-[#34C759]
                    hover:bg-[#34C759]/10 transition-colors
                    ${compact ? "px-2 py-1.5 text-xs" : "px-3 py-2 text-sm mb-2"}`}
      >
        {isIos ? <Smartphone size={16} /> : <Download size={16} />}
        <span>{label}</span>
      </button>

      {showIosGuide && (
        <div
          className="fixed inset-0 z-[80] bg-black/80 flex items-center justify-center p-4"
          onClick={() => setShowIosGuide(false)}
          data-testid="pwa-ios-guide"
        >
          <div
            className="bg-[#0A0A0F] border border-white/10 rounded-lg max-w-md w-full p-5 text-sm"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="font-display font-black text-base">Installa Wolf's Mind</div>
              <button
                onClick={() => setShowIosGuide(false)}
                className="text-white/60 hover:text-white"
                data-testid="pwa-ios-guide-close"
              >
                <X size={18} />
              </button>
            </div>
            {isIos ? (
              <ol className="space-y-3 text-white/80">
                <li className="flex gap-2">
                  <span className="text-[#34C759] font-bold">1.</span>
                  <span>
                    Apri questa pagina in <b>Safari</b> (non Chrome).
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-[#34C759] font-bold">2.</span>
                  <span>
                    Tocca l'icona <Share size={14} className="inline mx-1" /> <b>Condividi</b> in basso.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-[#34C759] font-bold">3.</span>
                  <span>
                    Scorri e scegli <b>"Aggiungi a Home"</b>, poi tocca <b>Aggiungi</b>.
                  </span>
                </li>
              </ol>
            ) : (
              <ol className="space-y-3 text-white/80">
                <li className="flex gap-2">
                  <span className="text-[#34C759] font-bold">1.</span>
                  <span>
                    Apri il menu del browser (i tre puntini <b>⋮</b>).
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-[#34C759] font-bold">2.</span>
                  <span>
                    Scegli <b>"Installa app"</b> o <b>"Aggiungi a schermata Home"</b>.
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="text-[#34C759] font-bold">3.</span>
                  <span>Conferma per aggiungere l'icona alla home del dispositivo.</span>
                </li>
              </ol>
            )}
            <div className="mt-4 text-xs text-white/50">
              Una volta installata, l'app si aprirà a schermo intero come un'app nativa.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
