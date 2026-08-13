import { describe, it, expect } from 'vitest'
import { filterOptions } from '@/utils/optionSearch'
import { createMockOption } from '../../utils/test-utils'

const exposure = createMockOption({ option_id: 'Exposure', name: 'Exposure', category: 'Basic Controls' })
const gain = createMockOption({ option_id: 'Gain', name: 'Gain', category: 'Basic Controls' })
const laser = createMockOption({ option_id: 'Laser_Power', name: 'Laser Power', category: 'Basic Controls' })
const ppSpatial = createMockOption({
  option_id: 'PP_Spatial_Filter_Magnitude',
  name: 'Filter Magnitude',
  category: 'Post-Processing',
  filter_name: 'Spatial Filter',
})

// Real-world trap: this control's description contains the word "laser" but it
// is NOT a laser control. Searching "laser" must not surface it.
const syncMode = createMockOption({
  option_id: 'inter_cam_sync_mode',
  name: 'Inter Cam Sync Mode',
  category: 'Basic Controls',
  description:
    'Inter-camera synchronization mode: ... 259 and 260 for two frames per trigger with laser ON-OFF and OFF-ON.',
})

const all = [exposure, gain, laser, ppSpatial]

describe('filterOptions', () => {
  it('returns all options unchanged for an empty query', () => {
    expect(filterOptions(all, '')).toEqual(all)
    expect(filterOptions(all, '   ')).toEqual(all)
  })

  it('matches by substring of the name, case-insensitively', () => {
    const r = filterOptions(all, 'GAI')
    expect(r).toContain(gain)
    expect(r).not.toContain(exposure)
  })

  it('does not match a control merely because its description mentions the term', () => {
    const r = filterOptions([laser, syncMode], 'laser')
    expect(r).toContain(laser)
    expect(r).not.toContain(syncMode)
  })

  it('never returns a control without the typed term in its labels', () => {
    // "option" appears in option ids but in no name/category/filter name, so it
    // must return nothing rather than loose fuzzy hits.
    expect(filterOptions(all, 'option')).toHaveLength(0)
    expect(filterOptions(all, 'zzzqqq')).toHaveLength(0)
  })

  it('does not tolerate typos (only what the user can see matches)', () => {
    expect(filterOptions(all, 'expsure')).toHaveLength(0)
  })

  it('surfaces post-processing params via their filter name (spatial)', () => {
    const r = filterOptions(all, 'spatial')
    expect(r).toContain(ppSpatial)
    expect(r).not.toContain(gain)
  })

  it('preserves original array order among matches', () => {
    const r = filterOptions(all, 'a') // Gain, Laser Power, Filter Magnitude
    const idx = r.map(o => all.indexOf(o))
    expect(idx).toEqual([...idx].sort((a, b) => a - b))
  })
})
