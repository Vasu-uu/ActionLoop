import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Kind = "success" | "error" | "info";
interface Toast { id: number; kind: Kind; text: string }
interface Ctx { toast: (text: string, kind?: Kind) => void }

const ToastCtx = createContext<Ctx>({ toast: () => {} });
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const toast = useCallback((text: string, kind: Kind = "info") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, kind, text }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), kind === "error" ? 6000 : 3000);
  }, []);
  const value = useMemo(() => ({ toast }), [toast]);
  const color: Record<Kind, string> = {
    success: "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
    error: "border-red-500 bg-red-50 text-red-900 dark:bg-red-950 dark:text-red-100",
    info: "border-brand-500 bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100",
  };
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`pointer-events-auto rounded-lg border-l-4 px-3 py-2 text-sm shadow-lg ${color[t.kind]}`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
