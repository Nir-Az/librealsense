import { describe, it, expect } from 'vitest'
import {
  nextIMUAxisBound,
  toIMUChartSeries,
  zoomIMUAxisRange,
  imuPlotHeight,
  IMU_CHART_LAYOUT,
  type IMUChartPoint,
} from '@/utils/imuChart'

const point = (t: number, x: number, y = 0, z = 0): IMUChartPoint => ({ t, x, y, z })

describe('toIMUChartSeries', () => {
  it('keys points on the sample timestamp, not the array index', () => {
    const series = toIMUChartSeries([
      { timestamp: 1_000, x: 1, y: 2, z: 3 },
      { timestamp: 1_050, x: 4, y: 5, z: 6 },
    ])
    expect(series).toEqual([
      { t: 1_000, x: 1, y: 2, z: 3 },
      { t: 1_050, x: 4, y: 5, z: 6 },
    ])
  })

  it('keeps a sample at the same x after the window slides', () => {
    const samples = [
      { timestamp: 1_000, x: 1, y: 0, z: 0 },
      { timestamp: 1_050, x: 2, y: 0, z: 0 },
    ]
    const before = toIMUChartSeries(samples)
    // Oldest sample drops off, as the ring buffer does.
    const after = toIMUChartSeries(samples.slice(1))
    expect(after[0].t).toBe(before[1].t)
  })
})

describe('nextIMUAxisBound', () => {
  it('never goes below the dead zone, so at-rest noise is not magnified', () => {
    const noise = [point(0, 0.004), point(1, -0.003)]
    expect(nextIMUAxisBound(noise, 0.5, 0.5)).toBe(0.5)
  })

  it('grows to fit a signal that needs more room', () => {
    expect(nextIMUAxisBound([point(0, 9.8)], 0.5, 0.5)).toBeGreaterThanOrEqual(9.8)
  })

  it('holds the current scale instead of rescaling on every redraw', () => {
    // Comfortably inside 20 but not below the shrink threshold (20 / 2.5 = 8).
    expect(nextIMUAxisBound([point(0, 9)], 20, 0.5)).toBe(20)
  })

  it('shrinks only once the signal fits well inside the current scale', () => {
    expect(nextIMUAxisBound([point(0, 0.01)], 20, 0.5)).toBeLessThan(20)
  })

  it('fits values beyond the snap ladder rather than clipping them', () => {
    // A wrong-unit or bad frame must still be fully visible.
    const bound = nextIMUAxisBound([point(0, 5_000)], 0.5, 0.5)
    expect(bound).toBeGreaterThanOrEqual(5_000)
  })
})

describe('zoomIMUAxisRange', () => {
  it('keeps the value under the pointer fixed while zooming in', () => {
    // Pointer a quarter down the plot of the automatic range [-12, 12] sits at 6.
    const ratio = 0.25
    const range = zoomIMUAxisRange(null, 12, ratio, 1 / 1.25)
    expect(range).not.toBeNull()
    const [min, max] = range!
    expect(max - ratio * (max - min)).toBeCloseTo(6, 6)
  })

  it('produces an asymmetric range when the pointer is off centre', () => {
    const [min, max] = zoomIMUAxisRange(null, 12, 0.9, 1 / 1.25)!
    expect(Math.abs(min)).not.toBeCloseTo(Math.abs(max), 3)
  })

  it('narrows the visible span when zooming in', () => {
    const [min, max] = zoomIMUAxisRange(null, 12, 0.5, 1 / 1.25)!
    expect(max - min).toBeLessThan(24)
  })

  it('hands the axis back to auto once zoomed out past the automatic scale', () => {
    expect(zoomIMUAxisRange([-11, 11], 12, 0.5, 1.25)).toBeNull()
  })

  it('refuses to zoom past a degenerate span', () => {
    const tiny: [number, number] = [-0.00002, 0.00002]
    expect(zoomIMUAxisRange(tiny, 12, 0.5, 1 / 1.25)).toBe(tiny)
  })
})

describe('imuPlotHeight', () => {
  it('subtracts every chart inset that shrinks the plot area', () => {
    const { marginTop, marginBottom, axisHeight } = IMU_CHART_LAYOUT
    expect(imuPlotHeight(200)).toBe(200 - marginTop - marginBottom - axisHeight)
  })
})
