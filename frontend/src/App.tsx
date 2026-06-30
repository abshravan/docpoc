import type { ReactNode } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { Activity, Stethoscope, Workflow } from "lucide-react";
import { StoreProvider } from "@/store";
import { AssessmentPage } from "@/pages/AssessmentPage";
import { FlowPage } from "@/pages/FlowPage";
import { cn } from "@/lib/utils";

function NavTab({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        cn(
          "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          isActive
            ? "bg-white/20 text-white"
            : "text-white/75 hover:bg-white/10 hover:text-white"
        )
      }
    >
      {icon}
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <StoreProvider>
        <div className="min-h-screen">
          {/* Branded top bar */}
          <header className="brand-gradient text-white shadow-md">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-5 py-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15 ring-1 ring-white/30">
                  <Stethoscope className="h-5 w-5" />
                </div>
                <div className="leading-tight">
                  <div className="flex items-center gap-2 font-semibold tracking-tight">
                    EPL-CDS
                    <span className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ring-white/25">
                      research build
                    </span>
                  </div>
                  <div className="text-[11px] text-white/70">
                    Early pregnancy loss · decision support
                  </div>
                </div>
              </div>
              <nav className="ml-auto flex items-center gap-1">
                <NavTab to="/" icon={<Activity className="h-4 w-4" />}>
                  Assessment
                </NavTab>
                <NavTab to="/flow" icon={<Workflow className="h-4 w-4" />}>
                  Decision flow
                </NavTab>
              </nav>
            </div>
          </header>

          <main className="mx-auto max-w-7xl px-5 py-6">
            <Routes>
              <Route path="/" element={<AssessmentPage />} />
              <Route path="/flow" element={<FlowPage />} />
            </Routes>
          </main>

          <footer className="mx-auto max-w-7xl px-5 pb-8 pt-2 text-xs text-muted-foreground">
            Decision support, not a diagnosis. Thresholds are unverified and awaiting
            expert sign-off.
          </footer>
        </div>
      </StoreProvider>
    </BrowserRouter>
  );
}
