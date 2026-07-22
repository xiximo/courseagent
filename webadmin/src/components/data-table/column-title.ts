import { type Column } from '@tanstack/react-table'

export function getColumnTitle<TData, TValue>(
  column: Column<TData, TValue>,
  titleOverride?: string
): string {
  if (titleOverride) return titleOverride
  const metaTitle = column.columnDef.meta?.title
  if (metaTitle) return metaTitle
  return column.id
}
