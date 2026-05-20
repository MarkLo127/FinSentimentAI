import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

export default function Skeleton({
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-surface-2', className)}
      {...rest}
    />
  )
}
