import { useState } from 'react'

const DEFAULT_PAGE_SIZE = 20

/**
 * Client-side pagination over an already-filtered array. List pages in this
 * app fetch their full result set up front and filter it in memory (see
 * AccountsPage's search box) rather than passing limit/offset to the API,
 * so pagination here just slices what's already loaded. Clamping `page` to
 * `totalPages` (rather than resetting it elsewhere) means a filter that
 * shrinks the result set automatically pulls a too-high page back in range.
 */
export function usePagedList<T>(items: T[] | undefined, pageSize = DEFAULT_PAGE_SIZE) {
  const [page, setPage] = useState(1)
  const totalPages = Math.max(1, Math.ceil((items?.length ?? 0) / pageSize))
  const currentPage = Math.min(page, totalPages)
  const paged = items?.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  return { page: currentPage, totalPages, setPage, paged }
}
