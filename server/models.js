/**
 * The models a teacher can put in front of the class.
 *
 * The catalog is server-owned on purpose: the teacher console sends model *ids*
 * and anything not listed here is rejected, so a stray value from the browser
 * can never pick the model or the spend.
 *
 * Prices are US dollars per million tokens, used to estimate the cost of a
 * round in the teacher's report. Add a row to offer another model.
 */
export const MODEL_CATALOG = [
  {
    id: 'claude-opus-5',
    label: 'Opus 5',
    blurb: 'Most capable. Best at holding the persona under pressure.',
    inputPerMTok: 5,
    outputPerMTok: 25,
  },
  {
    id: 'claude-sonnet-5',
    label: 'Sonnet 5',
    blurb: 'Middle ground on cost and capability.',
    inputPerMTok: 2,
    outputPerMTok: 10,
  },
  {
    id: 'claude-haiku-4-5',
    label: 'Haiku 4.5',
    blurb: 'Cheapest and fastest. Easier for students to catch out.',
    inputPerMTok: 1,
    outputPerMTok: 5,
  },
];

const BY_ID = new Map(MODEL_CATALOG.map((model) => [model.id, model]));

export function isKnownModel(id) {
  return BY_ID.has(id);
}

export function modelById(id) {
  return BY_ID.get(id) || null;
}

/** Human-readable name for reports and the dashboard. */
export function modelLabel(id) {
  return BY_ID.get(id)?.label || id || 'unknown';
}

/**
 * Two request params are model-gated. `effort` is rejected by Haiku 4.5 and
 * Sonnet 4.5, and the server-side refusal fallback only applies to models that
 * can return stop_reason "refusal". Sending either to a model that does not take
 * it returns a 400 on *every* turn, which would quietly drop a whole class onto
 * the scripted fallback — so only send them where they are accepted.
 */
export function modelCapabilities(id) {
  return {
    effort: /^claude-(fable-5|mythos-5|opus-5|opus-4-[5678]|sonnet-5|sonnet-4-6)/.test(id),
    refusalFallback: /^claude-(fable-5|mythos-5|opus-5|opus-4-[78])/.test(id),
  };
}

/** Dollar cost of a token count on a given model. */
export function estimateCost(id, inputTokens, outputTokens) {
  const model = BY_ID.get(id);
  if (!model) return 0;
  return (
    (inputTokens / 1_000_000) * model.inputPerMTok +
    (outputTokens / 1_000_000) * model.outputPerMTok
  );
}

/**
 * Validate a teacher's requested model mix.
 * Accepts `{modelId: weight}` and returns only known models with weight > 0,
 * falling back to the env default (or Opus 5) when nothing usable is supplied.
 */
export function normaliseMix(mix) {
  const cleaned = {};
  for (const [id, weight] of Object.entries(mix || {})) {
    const value = Number(weight);
    if (isKnownModel(id) && Number.isFinite(value) && value > 0) cleaned[id] = value;
  }
  if (Object.keys(cleaned).length > 0) return cleaned;

  const fallback = isKnownModel(process.env.BOT_MODEL) ? process.env.BOT_MODEL : 'claude-opus-5';
  return { [fallback]: 1 };
}
