import { describe, it, expect } from 'vitest';
import path from 'node:path';
import { loadCatalog, buildCatalog, CatalogError } from '../src/catalog/load.js';

const CATALOG = path.resolve('config/catalog.yaml');

describe('catalog', () => {
  it('the real catalog loads and is valid', () => {
    const catalog = loadCatalog(CATALOG);
    expect(catalog.programs.length).toBeGreaterThan(30);
    expect(catalog.index.programs['medical-emergency'].cannot_run_with).toContain('clean-energy');
    // cannot_run_with is applied both ways
    expect(catalog.index.programs['clean-energy'].cannot_run_with).toContain('medical-emergency');
    expect(catalog.index.programs['creative-techstyles'].only_runs_with).toEqual([
      'medical-emergency',
      'clean-energy',
    ]);
  });

  function rawCatalog() {
    return {
      settings: {
        class_size: 25,
        slots: [{ id: 'full', label: 'Full day', start: '09:15', end: '14:45' }],
        staff_pool: { name: 'Staff', size: 4 },
        semesters: { S1: { from: '2027-01-28', to: '2027-06-25' } },
        blackouts: [],
      },
      resources: [{ id: 'pink-room', name: 'Pink Room', type: 'room' }],
      categories: ['tech-samplers'],
      programs: [
        {
          id: 'a',
          name: 'A',
          category: 'tech-samplers',
          semesters: ['S1'],
          max_classes: 1,
          staff_required: 2,
          requires: [['pink-room']],
        },
      ],
    };
  }

  it('accepts a minimal catalog and fills in defaults', () => {
    const catalog = buildCatalog(rawCatalog());
    expect(catalog.programs[0].cannot_run_with).toEqual([]);
    expect(catalog.programs[0].only_runs_with).toBeNull();
    expect(catalog.settings.semesters.S1).toHaveLength(1);
  });

  it('rejects an unknown room with a clear message', () => {
    const raw = rawCatalog();
    raw.programs[0].requires = [['pink-room', 'purple-room']];
    expect(() => buildCatalog(raw)).toThrow(CatalogError);
    expect(() => buildCatalog(raw)).toThrow(/Program "a" → requires line 1: unknown room\/equipment "purple-room"/);
  });

  it('rejects unknown programs in combination rules', () => {
    const raw = rawCatalog();
    raw.programs[0].cannot_run_with = ['ghost'];
    expect(() => buildCatalog(raw)).toThrow(/cannot_run_with: unknown program "ghost"/);
  });

  it('rejects misspelt fields', () => {
    const raw = rawCatalog();
    raw.programs[0].cannot_run_wth = [];
    expect(() => buildCatalog(raw)).toThrow(/programs\[0\] \(a\).*cannot_run_wth/);
  });

  it('rejects programs needing more staff than the pool', () => {
    const raw = rawCatalog();
    raw.programs[0].staff_required = 9;
    expect(() => buildCatalog(raw)).toThrow(/could never be booked/);
  });
});
