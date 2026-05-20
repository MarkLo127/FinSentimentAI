import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: 'sm' | 'md' | 'lg'
}

const PAD = {
  sm: 'p-3 sm:p-4 md:p-5',
  md: 'p-4 sm:p-5 md:p-6',
  lg: 'p-5 sm:p-6 md:p-8',
}

export function Card({
  padding = 'md',
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <section
      className={cn(
        'rounded-xl border border-border bg-surface shadow-soft',
        'dark:shadow-none',
        PAD[padding],
        className,
      )}
      {...rest}
    >
      {children}
    </section>
  )
}

interface CardHeaderProps {
  title: ReactNode
  meta?: ReactNode
  action?: ReactNode
  className?: string
}

export function CardHeader({ title, meta, action, className }: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 mb-4',
        className,
      )}
    >
      <div className="flex items-center gap-3 min-w-0">
        <h2 className="text-base md:text-lg font-semibold text-text">{title}</h2>
        {meta && <span className="text-xs text-text-subtle">{meta}</span>}
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  )
}

export default Card
