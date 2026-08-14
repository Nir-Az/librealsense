// License: Apache 2.0. See LICENSE file in root directory.
// Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

export interface IMUSample {
  timestamp: number
  x: number
  y: number
  z: number
}

export interface IMUChartPoint {
  t: number
  x: number
  y: number
  z: number
}

// Default visible span, matching the C++ viewer's 300 samples at one per 50 ms.
export const IMU_CHART_WINDOW_MS = 15_000

// Plot against the sample timestamp rather than its array position: the history is
// a sliding window, so an index-based x re-labels every point on each redraw and
// the whole trace appears to jitter. On a time axis a sample keeps its x, so old
// data stays put and only the right edge advances.
export function toIMUChartSeries(samples: IMUSample[]): IMUChartPoint[] {
  return samples.map((s) => ({ t: s.timestamp, x: s.x, y: s.y, z: s.z }))
}

// Axis bounds snap to these so the scale settles on round numbers instead of
// tracking the peak exactly.
const AXIS_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

// Beyond the ladder, fall back to the value itself rather than the largest step:
// a bad frame or wrong-unit stream should still be shown in full, not clipped.
const snapUp = (value: number) => AXIS_STEPS.find((step) => step >= value) ?? value

// Symmetric Y bound that grows the moment the signal needs room but shrinks only
// once it fits well inside the current scale — without that hysteresis the axis
// rescales on nearly every redraw and the chart looks like it is jumping.
export function nextIMUAxisBound(points: IMUChartPoint[], current: number, floor: number): number {
  let peak = floor
  for (const p of points) {
    peak = Math.max(peak, Math.abs(p.x), Math.abs(p.y), Math.abs(p.z))
  }
  const needed = peak * 1.15
  if (needed > current) return snapUp(needed)
  if (needed < current / 2.5) return snapUp(Math.max(needed, floor))
  return current
}
