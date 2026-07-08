import { cva } from 'class-variance-authority';
import { NavLink } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import * as React from 'react';

export const sidebarLink = cva(
  'text-s flex flex-row items-center gap-sm rounded-xs p-sm font-medium w-full transition-colors',
  {
    variants: {
      isActive: {
        true: 'bg-purple-background text-purple-primary dark:bg-grey-background-light dark:text-purple-hover',
        false:
          'text-grey-primary hover:bg-purple-background hover:text-purple-primary dark:text-grey-primary dark:hover:bg-grey-background-light dark:hover:text-purple-hover',
      },
    },
    defaultVariants: {
      isActive: false,
    },
  },
);

export interface SidebarLinkProps {
  Icon: LucideIcon;
  label: string;
  to: string;
  children?: React.ReactNode;
  className?: string;
}

export function SidebarLink({ Icon, label, to, children, className }: SidebarLinkProps) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        sidebarLink({ isActive, className })
      }
    >
      <Icon className="size-6 shrink-0" />
      <span className="line-clamp-1 text-start opacity-0 transition-opacity group-hover/sidebar:opacity-100 delay-300 group-hover/sidebar:delay-0">
        {label}
      </span>
      {children}
    </NavLink>
  );
}

export interface SidebarButtonProps
  extends Omit<React.ComponentPropsWithoutRef<'button'>, 'children'> {
  Icon: LucideIcon;
  label: string;
}

export const SidebarButton = React.forwardRef<HTMLButtonElement, SidebarButtonProps>(
  function SidebarButton({ Icon, label, className, ...props }, ref) {
    return (
      <button ref={ref} className={sidebarLink({ className })} {...props}>
        <Icon className="size-6 shrink-0" />
        <span className="line-clamp-1 text-start opacity-0 transition-opacity group-hover/sidebar:opacity-100 delay-300 group-hover/sidebar:delay-0">
          {label}
        </span>
      </button>
    );
  },
);
