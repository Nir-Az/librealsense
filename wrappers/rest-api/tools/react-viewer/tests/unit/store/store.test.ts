import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { useAppStore } from '@/store'
import { firmwareStatus } from '@/api/types'
import { resetStore, createMockDevice, createMockDeviceState, createMockSensor, createMockOption } from '../../utils/test-utils'

describe('AppStore', () => {
  beforeEach(() => {
    resetStore()
  })

  describe('Firmware recommendation across enumeration', () => {
    // The device-list endpoint never consults the online versions DB, so it reports
    // neither a recommendation nor a status for any device.
    function enumerateWith(firmwareVersion: string) {
      const device = createMockDevice({
        device_id: 'fw-1',
        serial_number: 'fw-1',
        firmware_version: firmwareVersion,
      })
      server.use(http.get('/api/v1/devices/', () => HttpResponse.json([device])))
      return device
    }

    it('keeps a learned recommendation when the device list re-enumerates', async () => {
      const device = enumerateWith('5.17.0.10')
      useAppStore.setState({
        devices: [device],
        deviceStates: {
          'fw-1': createMockDeviceState(device, { firmware: { recommended: '5.17.3.10' } }),
        },
      })

      await useAppStore.getState().fetchDevices()

      expect(useAppStore.getState().deviceStates['fw-1'].firmware?.recommended).toBe('5.17.3.10')
    })

    it('the verdict follows the installed version without being recomputed', async () => {
      expect(firmwareStatus('5.17.0.10', '5.17.3.10')).toBe('outdated')
      expect(firmwareStatus('5.17.3.10', '5.17.3.10')).toBe('up_to_date')
      expect(firmwareStatus('5.17.3.25', '5.17.3.10')).toBe('up_to_date')
      expect(firmwareStatus(undefined, '5.17.3.10')).toBe('unknown')
      expect(firmwareStatus('5.17.3.10', undefined)).toBe('unknown')
    })
  })

  describe('Initial State', () => {
    it('starts with default values', () => {
      const state = useAppStore.getState()
      
      expect(state.isConnected).toBe(false)
      expect(state.devices).toEqual([])
      expect(state.deviceStates).toEqual({})
      expect(state.isLoadingDevices).toBe(false)
      expect(state.error).toBeNull()
    })

    it('starts in 2d view mode', () => {
      const state = useAppStore.getState()

      expect(state.viewMode).toBe('2d')
    })

    it('starts with chat closed', () => {
      const state = useAppStore.getState()
      
      expect(state.isChatOpen).toBe(false)
      expect(state.isChatAvailable).toBe(false)
      expect(state.chatMessages).toEqual([])
    })

    it('starts with empty IMU history', () => {
      const state = useAppStore.getState()
      
      expect(state.imuHistory).toEqual({})
    })
  })

  describe('Connection State', () => {
    it('sets connection state', () => {
      useAppStore.getState().setConnected(true)
      
      expect(useAppStore.getState().isConnected).toBe(true)
      
      useAppStore.getState().setConnected(false)
      
      expect(useAppStore.getState().isConnected).toBe(false)
    })
  })

  describe('View Mode', () => {
    it('switches to 3d', async () => {
      await useAppStore.getState().setViewMode('3d')

      expect(useAppStore.getState().viewMode).toBe('3d')
    })

    it('switches back to 2d', async () => {
      await useAppStore.getState().setViewMode('3d')
      await useAppStore.getState().setViewMode('2d')

      expect(useAppStore.getState().viewMode).toBe('2d')
    })
  })

  describe('Error Handling', () => {
    it('sets error message', () => {
      useAppStore.getState().setError('Something went wrong')
      
      expect(useAppStore.getState().error).toBe('Something went wrong')
    })

    it('clears error message', () => {
      useAppStore.getState().setError('Error')
      useAppStore.getState().clearError()
      
      expect(useAppStore.getState().error).toBeNull()
    })
  })

  describe('Chat State', () => {
    it('toggles chat open/closed', () => {
      expect(useAppStore.getState().isChatOpen).toBe(false)
      
      useAppStore.getState().toggleChat()
      expect(useAppStore.getState().isChatOpen).toBe(true)
      
      useAppStore.getState().toggleChat()
      expect(useAppStore.getState().isChatOpen).toBe(false)
    })

    it('clears chat messages', () => {
      useAppStore.setState({
        chatMessages: [
          { id: '1', role: 'user', content: 'Hello' },
          { id: '2', role: 'assistant', content: 'Hi' },
        ],
      })
      
      useAppStore.getState().clearChat()
      
      expect(useAppStore.getState().chatMessages).toEqual([])
    })
  })

  describe('IMU History', () => {
    // The store keeps one sample per 50 ms, so tests drive the clock rather than
    // calling addIMUData in a tight loop, where every call after the first is
    // dropped and the assertions pass without ever exercising the buffer.
    beforeEach(() => {
      vi.useFakeTimers()
      vi.setSystemTime(1_700_000_000_000)
      useAppStore.getState().clearIMUHistory()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    const push = (deviceId: string, type: 'accel' | 'gyro', sample: { x: number; y: number; z: number }) =>
      useAppStore.getState().addIMUData(deviceId, type, { timestamp: Date.now(), ...sample })

    it('adds accelerometer data under its device', () => {
      push('device-1', 'accel', { x: 0.1, y: 0.2, z: 9.8 })

      const history = useAppStore.getState().imuHistory['device-1']
      expect(history.accel).toHaveLength(1)
      expect(history.accel[0]).toMatchObject({ x: 0.1, y: 0.2, z: 9.8 })
      expect(history.gyro).toEqual([])
    })

    it('adds gyroscope data under its device', () => {
      push('device-1', 'gyro', { x: 0.01, y: 0.02, z: 0.03 })

      const history = useAppStore.getState().imuHistory['device-1']
      expect(history.gyro).toHaveLength(1)
      expect(history.gyro[0]).toMatchObject({ x: 0.01, y: 0.02, z: 0.03 })
    })

    it('keeps devices apart', () => {
      push('device-1', 'accel', { x: 1, y: 1, z: 1 })
      push('device-2', 'accel', { x: 2, y: 2, z: 2 })

      const { imuHistory } = useAppStore.getState()
      expect(imuHistory['device-1'].accel).toHaveLength(1)
      expect(imuHistory['device-1'].accel[0]).toMatchObject({ x: 1 })
      expect(imuHistory['device-2'].accel[0]).toMatchObject({ x: 2 })
    })

    it('drops samples that arrive inside the cadence interval', () => {
      push('device-1', 'accel', { x: 1, y: 1, z: 1 })
      vi.advanceTimersByTime(10)
      push('device-1', 'accel', { x: 2, y: 2, z: 2 })

      expect(useAppStore.getState().imuHistory['device-1'].accel).toHaveLength(1)

      vi.advanceTimersByTime(50)
      push('device-1', 'accel', { x: 3, y: 3, z: 3 })

      expect(useAppStore.getState().imuHistory['device-1'].accel).toHaveLength(2)
    })

    it('starts a fresh window after a streaming gap', () => {
      push('device-1', 'accel', { x: 1, y: 1, z: 1 })
      vi.advanceTimersByTime(50)
      push('device-1', 'accel', { x: 2, y: 2, z: 2 })
      expect(useAppStore.getState().imuHistory['device-1'].accel).toHaveLength(2)

      // Longer than IMU_STALE_GAP_MS: the stream stopped and restarted.
      vi.advanceTimersByTime(5_000)
      push('device-1', 'accel', { x: 3, y: 3, z: 3 })

      const accel = useAppStore.getState().imuHistory['device-1'].accel
      expect(accel).toHaveLength(1)
      expect(accel[0]).toMatchObject({ x: 3 })
    })

    it('clears one device without touching the other', () => {
      push('device-1', 'accel', { x: 1, y: 1, z: 1 })
      push('device-2', 'accel', { x: 2, y: 2, z: 2 })

      useAppStore.getState().clearIMUHistory('device-1')

      const { imuHistory } = useAppStore.getState()
      expect(imuHistory['device-1'].accel).toEqual([])
      expect(imuHistory['device-2'].accel).toHaveLength(1)
    })

    it('limits IMU history length', () => {
      const maxLength = useAppStore.getState().maxIMUHistoryLength

      for (let i = 0; i < maxLength + 10; i++) {
        push('device-1', 'accel', { x: i, y: i, z: i })
        vi.advanceTimersByTime(50)
      }

      const accel = useAppStore.getState().imuHistory['device-1'].accel
      expect(accel).toHaveLength(maxLength)
      // The window slid: the oldest samples were dropped, not the newest.
      expect(accel[accel.length - 1]).toMatchObject({ x: maxLength + 9 })
    })
  })

  describe('Device States', () => {
    it('stores device state by device_id', () => {
      const device = createMockDevice()
      const deviceState = createMockDeviceState(device, { isActive: true })
      
      useAppStore.setState({
        devices: [device],
        deviceStates: { [device.device_id]: deviceState },
      })
      
      const state = useAppStore.getState()
      expect(state.deviceStates[device.device_id]).toEqual(deviceState)
    })

    it('getActiveDevices returns only active devices', () => {
      const device1 = createMockDevice({ device_id: 'device-1' })
      const device2 = createMockDevice({ device_id: 'device-2' })
      
      const state1 = createMockDeviceState(device1, { isActive: true })
      const state2 = createMockDeviceState(device2, { isActive: false })
      
      useAppStore.setState({
        devices: [device1, device2],
        deviceStates: {
          [device1.device_id]: state1,
          [device2.device_id]: state2,
        },
      })
      
      const activeDevices = useAppStore.getState().getActiveDevices()
      expect(activeDevices).toHaveLength(1)
      expect(activeDevices[0].device.device_id).toBe('device-1')
    })

    it('isAnyDeviceStreaming returns true when a device is streaming', () => {
      const device = createMockDevice()
      const deviceState = createMockDeviceState(device, { isActive: true, isStreaming: true })
      
      useAppStore.setState({
        devices: [device],
        deviceStates: { [device.device_id]: deviceState },
      })
      
      expect(useAppStore.getState().isAnyDeviceStreaming()).toBe(true)
    })

    it('isAnyDeviceStreaming returns false when no devices are streaming', () => {
      const device = createMockDevice()
      const deviceState = createMockDeviceState(device, { isActive: true, isStreaming: false })
      
      useAppStore.setState({
        devices: [device],
        deviceStates: { [device.device_id]: deviceState },
      })
      
      expect(useAppStore.getState().isAnyDeviceStreaming()).toBe(false)
    })

    // Regression: derived streaming state used to be a `get isStreaming()`
    // accessor. Zustand merges with Object.assign, which copies an accessor's
    // evaluated value, so it froze at false after the first set() and every
    // consumer silently believed nothing was ever streaming.
    it('keeps derived streaming state correct across later store updates', () => {
      const device = createMockDevice()

      useAppStore.setState({
        devices: [device],
        deviceStates: {
          [device.device_id]: createMockDeviceState(device, { isActive: true, isStreaming: true }),
        },
      })
      expect(useAppStore.getState().isAnyDeviceStreaming()).toBe(true)

      // An unrelated write must not stale the derived value.
      useAppStore.setState({ error: 'unrelated' })
      expect(useAppStore.getState().isAnyDeviceStreaming()).toBe(true)
    })

    it('does not expose a snapshot-prone isStreaming value on the store', () => {
      // A plain boolean here would be frozen at creation time; consumers must
      // call isAnyDeviceStreaming() instead.
      expect('isStreaming' in useAppStore.getState()).toBe(false)
    })
  })

  describe('fetchDevices', () => {
    const presentDevice = createMockDevice({ device_id: 'present-1', serial_number: 'present-1' })
    const goneDevice = createMockDevice({ device_id: 'gone-1', serial_number: 'gone-1' })

    function mockDevicesEndpoint(list: ReturnType<typeof createMockDevice>[]) {
      server.use(
        http.get('/api/v1/devices/', () => HttpResponse.json(list))
      )
    }

    it('never drops a caller: every fetch reaches the backend', async () => {
      const seen: (string | null)[] = []
      server.use(
        http.get('/api/v1/devices/', async ({ request }) => {
          seen.push(new URL(request.url).searchParams.get('force_refresh'))
          await new Promise((resolve) => setTimeout(resolve, 20))
          return HttpResponse.json([presentDevice])
        })
      )

      const cached = useAppStore.getState().fetchDevices(false)
      await useAppStore.getState().fetchDevices(true)
      await cached

      expect(seen).toEqual([null, 'true'])
      expect(useAppStore.getState().devices.map((d) => d.device_id)).toEqual(['present-1'])
    })

    it('ignores a response older than one already applied', async () => {
      let call = 0
      server.use(
        http.get('/api/v1/devices/', async () => {
          call += 1
          if (call === 1) {
            // First request is slow and returns a list the second one supersedes.
            await new Promise((resolve) => setTimeout(resolve, 40))
            return HttpResponse.json([goneDevice])
          }
          return HttpResponse.json([presentDevice])
        })
      )

      const stale = useAppStore.getState().fetchDevices()
      await useAppStore.getState().fetchDevices()
      await stale

      expect(useAppStore.getState().devices.map((d) => d.device_id)).toEqual(['present-1'])
    })
  })

  describe('Stream Configuration', () => {
    it('can set stream configs directly via setState', () => {
      const device = createMockDevice()
      const config = {
        stream_type: 'depth' as const,
        format: 'Z16',
        enabled: true,
        enable: true,
        resolution: { width: 1280, height: 720 },
        framerate: 30,
      }
      const deviceState = createMockDeviceState(device, {
        isActive: true,
        streamConfigs: [config],
      })
      
      useAppStore.setState({
        devices: [device],
        deviceStates: { [device.device_id]: deviceState },
      })
      
      const state = useAppStore.getState()
      const configs = state.deviceStates[device.device_id].streamConfigs
      expect(configs).toContainEqual(config)
    })
  })

  describe('Aggregate Getters', () => {
    it('isStreaming reflects device streaming state', () => {
      const device = createMockDevice()
      const deviceState = createMockDeviceState(device, {
        isActive: true,
        isStreaming: true,
      })
      
      useAppStore.setState({
        devices: [device],
        deviceStates: { [device.device_id]: deviceState },
      })
      
      // Check isStreaming through the getter
      const state = useAppStore.getState()
      const isAnyStreaming = Object.values(state.deviceStates).some(ds => ds.isStreaming)
      expect(isAnyStreaming).toBe(true)
    })

    it('isStreaming getter returns false when no devices are streaming', () => {
      const device = createMockDevice()
      const deviceState = createMockDeviceState(device, {
        isActive: true,
        isStreaming: false,
      })
      
      useAppStore.setState({
        devices: [device],
        deviceStates: { [device.device_id]: deviceState },
      })
      
      const state = useAppStore.getState()
      const isAnyStreaming = Object.values(state.deviceStates).some(ds => ds.isStreaming)
      expect(isAnyStreaming).toBe(false)
    })

    it('isAnyDeviceStreaming tracks deviceStates after a state update', () => {
      const device = createMockDevice()

      expect(useAppStore.getState().isAnyDeviceStreaming()).toBe(false)

      useAppStore.setState({
        devices: [device],
        deviceStates: {
          [device.device_id]: createMockDeviceState(device, { isActive: true, isStreaming: true }),
        },
      })

      expect(useAppStore.getState().isAnyDeviceStreaming()).toBe(true)
    })
  })
})
