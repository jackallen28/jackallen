/**
 * Pairing logic for a round.
 *
 * Students are shuffled, then a slice of them is assigned to AI partners and the
 * rest are paired off with each other. Because human-human pairs consume two
 * students at a time, the AI count is nudged by one where needed so the human
 * remainder is always even.
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
 * Build the conversations for a round.
 *
 * @param {string[]} codes  student codes taking part
 * @param {number} aiRatio  target proportion paired with the AI (0..1)
 * @returns {Array<{id: string, type: 'ai'|'human', members: string[]}>}
 */
export function buildConversations(codes, aiRatio) {
  const shuffled = shuffle(codes);
  const aiCount = aiCountFor(shuffled.length, aiRatio);

  const aiStudents = shuffled.slice(0, aiCount);
  const humanStudents = shuffled.slice(aiCount);

  const conversations = [];
  let seq = 0;

  for (const code of aiStudents) {
    conversations.push({ id: `c${++seq}`, type: 'ai', members: [code] });
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
