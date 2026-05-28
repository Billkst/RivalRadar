import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge classnames using clsx (handles arrays/objects/booleans) and twMerge
 * (resolves Tailwind conflicts e.g. `p-2 p-4` → `p-4`).
 * Standard shadcn/ui helper.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
