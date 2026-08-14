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

// Plot against the sample timestamp rather than its array position: the history is
// a sliding window, so an index-based x re-labels every point on each redraw and
// the whole trace appears to jitter. On a time axis a sample keeps the same x, so
// old data stays put and only the right edge advances.
export function toIMUChartSeries(samples: IMUSample[]): IMUChartPoint[] {
  return samples.map((s) => ({ t: s.timestamp, x: s.x, y: s.y, z: s.z }))
}
