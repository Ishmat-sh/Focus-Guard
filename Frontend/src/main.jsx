import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center px-6">
      <section className="w-full max-w-xl rounded-3xl border border-slate-700 bg-slate-900/80 p-8 shadow-2xl shadow-sky-950/30">
        <p className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-300">
          Focus Guard
        </p>

        <h1 className="mt-4 text-4xl font-bold text-white">Ready to focus</h1>
        <p className="mt-3 text-slate-300">
          Keep your work sessions structured and distraction-free.
        </p>

        <div className="mt-8 flex items-center justify-between gap-4 rounded-2xl border border-slate-700 bg-slate-800/80 p-5">
          <div>
            <p className="text-sm text-slate-400">Current status</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">Idle</p>
          </div>

          <div className="rounded-full border border-sky-400/60 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-200">
            25 min session
          </div>
        </div>

        <div className="mt-8 flex gap-3">
          <button className="flex-1 rounded-xl bg-sky-500 px-4 py-3 font-semibold text-slate-950 transition hover:bg-sky-400">
            Start session
          </button>
          <button className="flex-1 rounded-xl border border-slate-600 bg-slate-800 px-4 py-3 font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-700">
            Take break
          </button>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);