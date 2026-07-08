import { Link, NavLink } from 'react-router-dom';
import { ArrowRight, Brain, GitBranch, Layers3, LineChart, Monitor, Pin, PinOff, Search, Shield, Sparkles, SlidersHorizontal, Timer } from 'lucide-react';

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
      { to: '/enhancements', label: 'AI / ML', icon: Sparkles },
      { to: '/fraud-ring', label: 'Fraud Ring', icon: GitBranch },
      { to: '/patterns', label: 'Patterns', icon: Search },
      { to: '/evidence', label: 'Evidence', icon: Shield },
    ],
  },
  {
    label: 'Analytics',
    items: [
      { to: '/graph-analytics', label: 'Graph Analytics', icon: GitBranch },
      { to: '/feedback', label: 'Feedback', icon: Sparkles },
    ],
  },
  {
    label: 'Control',
    items: [
      { to: '/rules', label: 'Rules', icon: SlidersHorizontal },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/modules', label: 'Modules', icon: Monitor },
    ],
  },
] as const;

export function LeftSidebar({
  expanded,
  pinned,
  onTogglePin,
}: {
  expanded: boolean;
  pinned: boolean;
  onTogglePin: () => void;
}) {
  return (
    <div
      className="fixed top-0 left-0 z-20 h-screen border-r border-grey-border bg-surface-sidebar transition-all duration-300 ease-in-out"
      style={{ width: expanded ? 234 : 56 }}
    >
      <div className="flex h-full w-[234px] flex-col overflow-hidden">
        <div className="flex items-center gap-3 p-3">
          <Shield className="size-6 shrink-0 text-grey-primary transition-all duration-300" />
          <div
            className="min-w-0 transition-opacity duration-300"
            style={{ opacity: expanded ? 1 : 0 }}
          >
            <div className="truncate text-s font-semibold text-grey-primary">ReturnShield AI</div>
            <div className="text-xs text-grey-secondary">return fraud decisioning</div>
          </div>
          <button
            onClick={onTogglePin}
            className="ml-auto flex size-6 shrink-0 items-center justify-center rounded text-grey-secondary hover:bg-grey-background hover:text-grey-primary transition-opacity duration-300"
            style={{ opacity: expanded ? 1 : 0 }}
            title={pinned ? 'Unpin sidebar' : 'Pin sidebar'}
          >
            {pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
          </button>
        </div>

        <div
          className="mx-3 mb-3 rounded-lg border border-grey-border bg-grey-background-light p-3 transition-opacity duration-300"
          style={{ opacity: expanded ? 1 : 0 }}
        >
          <div className="text-xs uppercase tracking-[0.24em] text-grey-secondary">Operations mode</div>
          <div className="mt-1 text-s font-medium text-grey-primary">Analyst workspace</div>
          <div className="mt-1 text-xs leading-4 text-grey-secondary">
            Score, inspect, decide, and feed labels back into the fraud engine.
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-1 scrollbar-gutter-stable">
          <div className="space-y-5">
            {navSections.map((section) => (
              <div key={section.label}>
                <div
                  className="px-2 pb-1 text-xs uppercase tracking-[0.28em] text-grey-secondary transition-opacity duration-300"
                  style={{ opacity: expanded ? 1 : 0 }}
                >
                  {section.label}
                </div>
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `text-s flex flex-row items-center gap-2 rounded p-2 font-medium w-full transition-colors ${
                        isActive
                          ? 'bg-purple-background text-purple-primary'
                          : 'text-grey-primary hover:bg-purple-background hover:text-purple-primary'
                      }`
                    }
                  >
                    <item.icon className="size-6 shrink-0" />
                    <span
                      className="line-clamp-1 text-start transition-opacity duration-300"
                      style={{ opacity: expanded ? 1 : 0 }}
                    >
                      {item.label}
                    </span>
                  </NavLink>
                ))}
              </div>
            ))}
          </div>
        </nav>

        <div
          className="mx-3 mb-3 rounded-lg border border-grey-border bg-grey-background-light p-3 transition-opacity duration-300"
          style={{ opacity: expanded ? 1 : 0 }}
        >
          <div className="text-xs uppercase tracking-[0.24em] text-grey-secondary">Decision chain</div>
          <div className="mt-1 text-xs leading-4 text-grey-primary">
            Return request → rules → ML → explainability → analyst feedback
          </div>
          <Link
            to="/investigations"
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-purple-primary hover:text-purple-hover"
          >
            Open investigations <ArrowRight className="size-3" />
          </Link>
        </div>
      </div>
    </div>
  );
}
