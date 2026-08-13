import type { OptionInfo } from '../api/types'

/**
 * Filter camera options by a case-insensitive substring of their name, or of the
 * post-processing filter they belong to, so a result always contains the typed
 * text. Descriptions are not searched - they mention unrelated terms (the
 * sync-mode description contains "laser") and produced false hits.
 *
 * An empty query returns the input unchanged, in the original order.
 */
export function filterOptions(options: OptionInfo[], query: string): OptionInfo[] {
  const q = query.trim().toLowerCase()
  if (!q) return options

  return options.filter(option =>
    option.name.toLowerCase().includes(q)
    || (option.filter_name || '').toLowerCase().includes(q)
  )
}
