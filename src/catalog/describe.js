// Small helpers that turn catalog entries into plain-English text.
// Used by `npm run catalog:check`, the admin catalog page and the public program pages.

export function resourceName(catalog, id) {
  return catalog.index.resources[id]?.name || id;
}

export function programName(catalog, id) {
  return catalog.index.programs[id]?.name || id;
}

/** ["pink-room", "blue-room"] → "Pink Room or Blue Room" */
export function describeRequirement(catalog, alternatives) {
  return alternatives.map((id) => resourceName(catalog, id)).join(' or ');
}

/** Lists only the rooms (not equipment) a program uses, e.g. ["Drone Room", "Pink Room"]. */
export function programRooms(catalog, program) {
  return program.requires
    .filter((alts) => alts.every((id) => catalog.index.resources[id]?.type === 'room'))
    .map((alts) => describeRequirement(catalog, alts));
}

/** Lists the tracked shared equipment a program uses. */
export function programTrackedEquipment(catalog, program) {
  return program.requires
    .filter((alts) => alts.some((id) => catalog.index.resources[id]?.type === 'equipment'))
    .map((alts) => describeRequirement(catalog, alts));
}

export function describeCombinationRules(catalog, program) {
  const rules = [];
  if (program.cannot_run_with.length) {
    rules.push(`Can't run with: ${program.cannot_run_with.map((id) => programName(catalog, id)).join(', ')}`);
  }
  if (program.only_runs_with) {
    rules.push(
      program.only_runs_with.length
        ? `Only runs with: ${program.only_runs_with.map((id) => programName(catalog, id)).join(', ')}`
        : 'Runs on its own (nothing else that slot)',
    );
  }
  return rules;
}

export function semesterLabel(semesters) {
  const nice = semesters.map((s) => s.replace(/^S(\d)$/, 'Semester $1'));
  return semesters.length > 1 && semesters.every((s) => /^S\d$/.test(s)) ? 'All year' : nice.join(', ');
}
