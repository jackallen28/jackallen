/**
 * Pairing logic for a round.
 *
 * Students are shuffled, then a slice of them is assigned to AI partners and the
 * rest are paired off with each other. Because human-human pairs consume two
 * students at a time, the AI count is nudged by one where needed so the human
 * remainder is always even.
 *
 * The AI slice is then split across whichever models the teacher chose for the
 * round, so one class can run several models side by side.
 */

/** Fisher-Yates shuffle on a copy of the input. */
export function shuffle(items) {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * Decide how many students get an AI partner.
 * Keeps the human remainder even, preferring to *drop* an AI slot so that
 * classes get as many human-human conversations as the ratio allows.
 */
export function aiCountFor(n, aiRatio) {
  if (n <= 0) return 0;
  let aiCount = Math.round(n * aiRatio);
  aiCount = Math.min(n, Math.max(0, aiCount));
  if ((n - aiCount) % 2 !== 0) {
    if (aiCount > 0) aiCount -= 1;
    else aiCount = 1;
  }
  return aiCount;
}

/**
 * Spread `count` slots across weighted models.
 *
 * Uses largest-remainder so the split matches the requested weights as closely
 * as whole students allow — with 5 AI students over two equal models you get
 * 3/2, never 2/2 with one student silently unassigned.
 *
 * @param {number} count           how many AI-paired students there are
 * @param {Record<string, number>} mix  modelId -> relative weight
 * @returns {string[]} one model id per slot, shuffled
 */
export function allocateModels(count, mix) {
  const entries = Object.entries(mix || {}).filter(([, w]) => Number(w) > 0);
  if (count <= 0 || entries.length === 0) return [];

  const total = entries.reduce((sum, [, w]) => sum + Number(w), 0);
  const shares = entries.map(([id, weight]) => {
    const ideal = (count * Number(weight)) / total;
    const base = Math.floor(ideal);
    return { id, base, remainder: ideal - base };
  });

  let assigned = shares.reduce((sum, share) => sum + share.base, 0);
  shares.sort((a, b) => b.remainder - a.remainder);
  for (let i = 0; assigned < count; i++, assigned++) {
    shares[i % shares.length].base += 1;
  }

  const slots = [];
  for (const share of shares) {
    for (let i = 0; i < share.base; i++) slots.push(share.id);
  }
  return shuffle(slots);
}

/**
 * Build the conversations for a round.
 *
 * @param {string[]} codes  student codes taking part
 * @param {number} aiRatio  target proportion paired with the AI (0..1)
 * @param {Record<string, number>} mix  which models to use, and in what shares
 * @returns {Array<{id: string, type: 'ai'|'human', members: string[], model?: string}>}
 */
export function buildConversations(codes, aiRatio, mix) {
  const shuffled = shuffle(codes);
  const aiCount = aiCountFor(shuffled.length, aiRatio);

  const aiStudents = shuffled.slice(0, aiCount);
  const humanStudents = shuffled.slice(aiCount);
  const models = allocateModels(aiStudents.length, mix);

  const conversations = [];
  let seq = 0;

  for (const [index, code] of aiStudents.entries()) {
    conversations.push({
      id: `c${++seq}`,
      type: 'ai',
      members: [code],
      model: models[index],
    });
  }
  for (let i = 0; i + 1 < humanStudents.length; i += 2) {
    conversations.push({
      id: `c${++seq}`,
      type: 'human',
      members: [humanStudents[i], humanStudents[i + 1]],
    });
  }

  return conversations;
}
