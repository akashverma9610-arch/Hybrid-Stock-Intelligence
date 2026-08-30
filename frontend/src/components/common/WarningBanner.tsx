import React from 'react';
import { AlertCircle, AlertTriangle, Info } from 'lucide-react';

interface WarningBannerProps {
  id?: string;
  type?: 'warning' | 'critical' | 'info' | 'unavailable';
  title?: string;
  message: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const WarningBanner: React.FC<WarningBannerProps> = ({
  id,
  type = 'warning',
  title,
  message,
  action,
  className = '',
}) => {
  const styles = {
    warning: {
      bg: 'bg-amber-500/10 border-amber-500/30 text-amber-200',
      icon: <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />,
    },
    critical: {
      bg: 'bg-rose-500/10 border-rose-500/30 text-rose-200',
      icon: <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />,
    },
    info: {
      bg: 'bg-sky-500/10 border-sky-500/30 text-sky-200',
      icon: <Info className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />,
    },
    unavailable: {
      bg: 'bg-[#161616] border-[#333] text-gray-300',
      icon: <Info className="w-4 h-4 text-gray-400 shrink-0 mt-0.5" />,
    },
  }[type];

  return (
    <div
      id={id || `banner-${type}`}
      className={`border rounded-lg p-3.5 flex items-start gap-3 text-xs leading-relaxed ${styles.bg} ${className}`}
    >
      {styles.icon}
      <div className="flex-1">
        {title && <div className="font-bold mb-0.5 text-slate-900 dark:text-slate-100">{title}</div>}
        <div className="text-slate-700 dark:text-slate-300">{message}</div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
};
