type ClassValue = string | number | boolean | null | undefined

export function cn(...parts: ClassValue[]): string {
  const out: string[] = []
  for (const p of parts) {
    if (typeof p === 'string' && p) out.push(p)
  }
  return out.join(' ')
}
