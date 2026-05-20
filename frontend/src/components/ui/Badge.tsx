import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type BadgeTone =
  | 'neutral'
  | 'positive'
  | 'negative'
  | 'warning'
  | 'info'
  | 'primary'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
  size?: 'sm' | 'md'
  icon?: ReactNode
  children: ReactNode
}

const SIZE = {
  sm: 'text-xs px-2 py-0.5 gap-1',
  md: 'text-sm px-2.5 py-1 gap-1.5',
}

const TONE: Record<BadgeTone, string> = {
  neutral: 'bg-sentiment-neutral-soft text-text-muted',
  positive: 'bg-sentiment-positive-soft text-sentiment-positive',
  negative: 'bg-sentiment-negative-soft text-sentiment-negative',
  warning: 'bg-accent-soft text-accent',
  info: 'bg-primary-soft text-primary',
  primary: 'bg-primary text-white',
}

export default function Badge({
  tone = 'neutral',
  size = 'md',
  icon,
  className,
  children,
  ...rest
}: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium whitespace-nowrap',
        SIZE[size],
        TONE[tone],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </span>
  )
}
