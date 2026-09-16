import { describe, expect, it } from 'vitest'
import { formatFileSize } from './ExpenseDetailPage'

describe('formatFileSize', () => {
  it('renders bytes under 1024 as-is', () => {
    expect(formatFileSize(512)).toBe('512 B')
  })

  it('renders kilobytes with one decimal place', () => {
    expect(formatFileSize(2048)).toBe('2.0 KB')
    expect(formatFileSize(1536)).toBe('1.5 KB')
  })

  it('renders megabytes once the kilobyte threshold is exceeded', () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB')
  })
})
