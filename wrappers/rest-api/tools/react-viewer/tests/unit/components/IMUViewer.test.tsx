import { describe, it, expect } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { IMUViewer } from '@/components/IMUViewer'
import { useAppStore } from '@/store'
import { render, createMockDevice, createMockDeviceState } from '../../utils/test-utils'

// `render` resets the store, so state has to arrive via initialStoreState.
function streamingWithIMUHistory() {
  const device = createMockDevice()
  const now = 1_700_000_000_000
  return {
    deviceStates: {
      [device.device_id]: createMockDeviceState(device, { isActive: true, isStreaming: true }),
    },
    imuHistory: {
      accel: Array.from({ length: 5 }, (_, i) => ({
        timestamp: now + i * 50,
        x: 0.1,
        y: -9.8,
        z: 0.2,
      })),
      gyro: Array.from({ length: 5 }, (_, i) => ({
        timestamp: now + i * 50,
        x: 0.001,
        y: -0.002,
        z: 0.003,
      })),
    },
    isIMUViewerExpanded: true,
  }
}

describe('IMUViewer', () => {
  it('prompts to start streaming when nothing is streaming', () => {
    render(<IMUViewer />, { initialStoreState: { isIMUViewerExpanded: true } })
    expect(screen.getByText(/Start streaming with IMU sensors enabled/)).toBeInTheDocument()
  })

  // Regression: the panel used to gate on a store getter that zustand's
  // Object.assign froze at false after the first set(), so it showed the
  // "start streaming" prompt forever and its graphs were unreachable.
  it('shows the history graphs while a device is streaming', () => {
    render(<IMUViewer />, { initialStoreState: streamingWithIMUHistory() })

    expect(screen.queryByText(/Start streaming with IMU sensors enabled/)).not.toBeInTheDocument()
    expect(screen.queryByText(/No IMU data received/)).not.toBeInTheDocument()
    expect(screen.getByText('Accelerometer History')).toBeInTheDocument()
    expect(screen.getByText('Gyroscope History')).toBeInTheDocument()
  })

  it('stays reachable after an unrelated store update', () => {
    render(<IMUViewer />, { initialStoreState: streamingWithIMUHistory() })
    // Any set() used to be enough to freeze the streaming flag.
    useAppStore.setState({ error: 'unrelated' })
    expect(screen.getByText('Accelerometer History')).toBeInTheDocument()
  })

  it('reports the retained sample counts', () => {
    render(<IMUViewer />, { initialStoreState: streamingWithIMUHistory() })
    expect(screen.getByText(/5 accel, 5 gyro samples/)).toBeInTheDocument()
  })

  it('offers per-series toggles that flip pressed state', () => {
    render(<IMUViewer />, { initialStoreState: streamingWithIMUHistory() })

    // One X toggle per chart (accel and gyro).
    const xToggles = screen.getAllByTitle('Hide X')
    expect(xToggles).toHaveLength(2)
    expect(xToggles[0]).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(xToggles[0])
    expect(screen.getAllByTitle('Show X')[0]).toHaveAttribute('aria-pressed', 'false')
    // The other chart is unaffected.
    expect(screen.getAllByTitle('Hide X')[0]).toHaveAttribute('aria-pressed', 'true')
  })

  it('keeps the Clear History and Export CSV actions', () => {
    render(<IMUViewer />, { initialStoreState: streamingWithIMUHistory() })
    expect(screen.getByRole('button', { name: 'Clear History' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Export CSV' })).toBeInTheDocument()
  })
})
