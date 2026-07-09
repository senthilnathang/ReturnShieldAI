import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  Brain,
  CaseSensitive,
  Layers3,
  LineChart,
  Menu,
  PanelRightOpen,
  Shield,
  Sparkles,
  SlidersHorizontal,
} from 'lucide-react';

import { LeftSidebar } from './LeftSidebar';

const navSections = [
  {
    label: 'Workspace',
    items: [
      { to: '/', label: 'Overview', icon: LineChart },
      { to: '/cases', label: 'Cases', icon: Layers3 },
      { to: '/investigations', label: 'Investigations', icon: Shield },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { to: '/decision-engine', label: 'Decision Engine', icon: Brain },
      { to: '/enhancements', label: 'Fraud Signals', icon: Sparkles },
    ],
  },
  {
    label: 'Control',
    items: [
      { to: '/rules', label: 'Rules', icon: SlidersHorizontal },
      { to: '/feedback', label: 'Feedback', icon: Sparkles },
    ],
  },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [sidebarPinned, setSidebarPinned] = useState(false);
  const location = useLocation();
  useEffect(() => setMobileOpen(false), [location.pathname]);

  const effectiveExpanded = sidebarVisible && (sidebarExpanded || sidebarPinned);
  const sidebarWidth = effectiveExpanded ? 234 : 56;

  useEffect(() => {
    const root = document.documentElement;
    if (sidebarVisible) {
      root.style.setProperty('--sidebar-w', String(sidebarWidth) + 'px');
    } else {
      root.style.setProperty('--sidebar-w', '0px');
    }
  }, [sidebarVisible, sidebarWidth]);

  const handleMouseEnter = useCallback(() => {
    if (sidebarVisible) setSidebarExpanded(true);
  }, [sidebarVisible]);

  const handleMouseLeave = useCallback(() => {
    if (!sidebarPinned) setSidebarExpanded(false);
  }, [sidebarPinned]);

  const togglePin = useCallback(() => {
    setSidebarPinned((prev) => !prev);
    setSidebarExpanded(true);
  }, []);

  return (
    <div className="min-h-[100dvh]">
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-30 bg-grey-background/60 backdrop-blur-sm xl:hidden"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 w-[234px] overflow-y-auto border-r border-grey-border bg-surface-sidebar transition-transform duration-200 xl:hidden ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className="flex h-full flex-col p-md">
          <div className="flex items-center gap-3 pb-md">
            <div className="flex size-11 items-center justify-center rounded-xl bg-grey-background text-grey-primary">
              <Shield className="size-5" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-s font-semibold text-grey-primary">ReturnShield AI</div>
              <div className="text-xs text-grey-secondary">return fraud decisioning</div>
            </div>
          </div>

          <div className="mb-md rounded-lg border border-grey-border bg-grey-background-light p-md">
            <div className="text-xs uppercase tracking-[0.24em] text-grey-secondary">Operations mode</div>
            <div className="mt-1 text-s font-medium text-grey-primary">Analyst workspace</div>
            <div className="mt-1 text-xs leading-5 text-grey-secondary">
              Score, inspect, decide, and feed labels back into the fraud engine.
            </div>
          </div>

          <nav className="flex-1 overflow-y-auto px-xs scrollbar-gutter-stable">
            <div className="space-y-5">
              {navSections.map((section) => (
                <div key={section.label}>
                  <div className="px-sm pb-1 text-xs uppercase tracking-[0.28em] text-grey-secondary">
                    {section.label}
                  </div>
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    return (
                      <NavLink
                        key={item.to}
                        to={item.to}
                        className={({ isActive }) =>
                          `text-s flex flex-row items-center gap-sm rounded-xs p-sm font-medium w-full transition-colors ${
                            isActive
                              ? 'bg-purple-background text-purple-primary'
                              : 'text-grey-primary hover:bg-purple-background hover:text-purple-primary'
                          }`
                        }
                      >
                        <Icon className="size-6 shrink-0" />
                        <span className="line-clamp-1 text-start">{item.label}</span>
                      </NavLink>
                    );
                  })}
                </div>
              ))}
            </div>
          </nav>

          <div className="mt-md rounded-lg border border-grey-border bg-grey-background-light p-md">
            <div className="text-xs uppercase tracking-[0.24em] text-grey-secondary">Decision chain</div>
            <div className="mt-1 text-xs leading-5 text-grey-primary">
              Return → rules (35%) → supervised ML (65%) → explainability → analyst feedback
            </div>
            <div className="mt-1 text-[11px] leading-4 text-grey-secondary">
              If the promoted model is unavailable, the scorer falls back to a heuristic path and keeps the API response flowing.
            </div>
            <Link
              to="/investigations"
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-purple-primary hover:text-purple-hover"
            >
              Open investigations <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </aside>

      {sidebarVisible && (
        <div
          className="hidden xl:block"
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <LeftSidebar expanded={effectiveExpanded} pinned={sidebarPinned} onTogglePin={togglePin} />
        </div>
      )}

      <main
        className="flex min-h-[100dvh] flex-col px-3 pb-5 pt-3 sm:px-4 xl:pr-6 xl:pt-4 transition-all duration-300 ease-in-out"
        style={{ marginLeft: 'var(--sidebar-w)' }}
      >
        <header className="glass sticky top-3 z-10 mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[24px] px-4 py-3">
          <button
            onClick={() => setMobileOpen((v) => !v)}
            className="inline-flex items-center gap-2 rounded-lg border border-grey-border bg-grey-background px-3 py-2 text-sm text-grey-primary xl:hidden"
          >
            <Menu className="size-4" />
            Menu
          </button>
          <div className="hidden items-center gap-3 xl:flex">
            <div className="flex size-10 items-center justify-center rounded-lg bg-grey-background ring-1 ring-grey-border">
              <CaseSensitive className="size-4 text-grey-secondary" />
            </div>
            <div>
              <div className="text-sm font-medium text-grey-primary">Fraud decision operations console</div>
              <div className="text-xs text-grey-secondary">API scoring, case review, analyst feedback</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSidebarVisible((v) => !v)}
              className="hidden rounded-lg border border-grey-border bg-grey-background px-2 py-2 text-xs text-grey-secondary transition-colors hover:text-grey-primary xl:inline-flex"
              title={sidebarVisible ? 'Hide sidebar' : 'Show sidebar'}
            >
              <PanelRightOpen className="size-4" />
            </button>
            <div className="flex items-center gap-2 rounded-lg border border-grey-border bg-grey-background px-3 py-2 text-xs text-grey-primary">
              <BadgeCheck className="size-4 text-green-primary" />
              Connected
            </div>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
