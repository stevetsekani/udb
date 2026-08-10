import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressBar, StatusPill, formatBytes, formatDate } from './ui'

describe('ui components', () => {
  it('renders ProgressBar with clamped value', () => {
    const { container } = render(<ProgressBar value={150} />)
    const fill = container.querySelector('.progress-fill') as HTMLElement
    expect(fill.style.width).toBe('100%')
  })

  it('renders ProgressBar with 0 value', () => {
    const { container } = render(<ProgressBar value={-10} />)
    const fill = container.querySelector('.progress-fill') as HTMLElement
    expect(fill.style.width).toBe('0%')
  })

  it('renders StatusPill label', () => {
    render(<StatusPill status="downloading" />)
    expect(screen.getByText('Downloading')).toBeInTheDocument()
  })

  it('formats bytes', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(formatBytes(2 * 1024 ** 3)).toBe('2.0 GB')
  })

  it('formats dates', () => {
    expect(formatDate('')).toBe('—')
    expect(formatDate('not-a-date')).toBe('not-a-date')
    expect(formatDate('2026-08-10T12:00:00')).toContain('2026')
  })
})

