import { LucideIcon } from "lucide-react";
import { ReactNode } from "react";

interface CardProps {
  icon?: LucideIcon;
  title?: string;
  children: ReactNode;
  className?: string;
}

export default function Card({ icon: Icon, title, children, className = "" }: CardProps) {
  return (
    <div
      className={`bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm dark:shadow-none p-6 space-y-4 animate-slide-up ${className}`}
    >
      {title && (
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />}
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">{title}</h3>
        </div>
      )}
      {children}
    </div>
  );
}
