"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Activity, BookOpen, FileCog, Stethoscope, Workflow } from "lucide-react";
import { StoreProvider } from "@/store";
import { cn } from "@/lib/utils";

const TABS = [
  { href: "/", label: "Assessment", icon: Activity },
  { href: "/flow", label: "Decision flow", icon: Workflow },
  { href: "/evidence", label: "Evidence", icon: BookOpen },
  { href: "/authoring", label: "Authoring", icon: FileCog },
];

function NavTabs() {
  const pathname = usePathname();
  return (
    <nav className="ml-auto flex items-center gap-1">
      {TABS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "relative inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              active ? "text-white" : "text-white/75 hover:bg-white/10 hover:text-white"
            )}
          >
            {active && (
              <motion.span
                layoutId="nav-pill"
                className="absolute inset-0 rounded-md bg-white/20"
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
              />
            )}
            <Icon className="relative z-10 h-4 w-4" />
            <span className="relative z-10">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <StoreProvider>
      <div className="min-h-screen">
        <header className="brand-gradient text-white shadow-md">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-5 py-3">
            <Link href="/" className="flex items-center gap-2.5">
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
            </Link>
            <NavTabs />
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-5 py-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>

        <footer className="mx-auto max-w-7xl px-5 pb-8 pt-2 text-xs text-muted-foreground">
          Decision support, not a diagnosis. Thresholds are unverified and awaiting
          expert sign-off.
        </footer>
      </div>
    </StoreProvider>
  );
}
