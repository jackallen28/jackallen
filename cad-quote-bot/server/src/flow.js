// The conversation state machine. Every reply the widget renders is produced
// here, so the front-end stays a dumb renderer and the flow can never be
// skipped or reordered from the browser.
import { config } from './config.js';
import * as llm from './llm.js';
import { renderScad, analyzeStl } from './openscad.js';
import { putFile } from './storage.js';
import { createSession, saveSession, newId, appendLead } from './store.js';
import { notifyQuote } from './notify.js';

const GREETING = `Hi! Tell me in one sentence what you'd like made and I'll turn it into a 3D model you can look at — then a quote.`;
const EXAMPLE = `For example: "a wall bracket to hold a 90 mm diameter torch" or "a replacement knob for my oven dial".`;

function bot(session, text, card = null) {
  session.messages.push({ id: newId('m'), role: 'bot', text, card, ts: Date.now() });
}
function user(session, text) {
  session.messages.push({ id: newId('m'), role: 'user', text, card: null, ts: Date.now() });
}

/** What the widget should show as input affordances for the current state. */
export function uiFor(session) {
  switch (session.state) {
    case 'brief':
      return { mode: 'text', placeholder: 'e.g. a bracket to hold a 90 mm torch on a wall', chips: [] };
    case 'questions': {
      const q = session.questions[session.qIndex];
      return { mode: 'text', placeholder: 'Type your answer…', chips: q?.options || [] };
    }
    case 'summary':
      return {
        mode: 'confirm',
        actions: [
          { id: 'spec_ok', label: 'Looks right — build it', style: 'primary' },
          { id: 'spec_change', label: 'Change something', style: 'ghost' },
        ],
      };
    case 'change':
      return { mode: 'text', placeholder: 'What should be different?', chips: [] };
    case 'generating':
      return { mode: 'busy', label: 'Modelling and rendering — this takes up to a minute' };
    case 'review':
      return {
        mode: 'confirm',
        actions: [
          { id: 'design_ok', label: 'Approve this design', style: 'primary' },
          { id: 'design_reject', label: 'Not quite — change it', style: 'ghost' },
        ],
      };
    case 'reject':
      return { mode: 'text', placeholder: 'What needs to change?', chips: [] };
    case 'details':
      return { mode: 'form', fields: LEAD_FIELDS };
    case 'done':
      return { mode: 'done' };
    default:
      return { mode: 'text', placeholder: 'Type a message…', chips: [] };
  }
}

export const LEAD_FIELDS = [
  { name: 'name', label: 'Full name', type: 'text', autocomplete: 'name', required: true },
  { name: 'email', label: 'Email', type: 'email', autocomplete: 'email', required: true },
  { name: 'phone', label: 'Mobile', type: 'tel', autocomplete: 'tel', required: true },
  { name: 'postcode', label: 'Post code', type: 'text', autocomplete: 'postal-code', required: true },
  { name: 'quantity', label: 'Quantity', type: 'number', min: 1, max: 100000, required: true },
  {
    name: 'leadtime',
    label: 'Required by',
    type: 'select',
    required: true,
    options: ['As soon as possible', 'Within 1 week', 'Within 2 weeks', 'Within 1 month', 'Flexible / no rush'],
  },
  { name: 'notes', label: 'Anything else? (optional)', type: 'textarea', required: false },
];

export async function start(meta) {
  const session = await createSession(meta);
  bot(session, GREETING);
  bot(session, EXAMPLE);
  await saveSession(session);
  return session;
}

export async function handleMessage(session, text) {
  const message = String(text || '').trim().slice(0, config.limits.maxMessageChars);
  if (!message) return session;

  switch (session.state) {
    case 'brief':
      return handleBrief(session, message);
    case 'questions':
      return handleAnswer(session, message);
    case 'change':
      return applySpecChange(session, message);
    case 'reject':
      return applyDesignChange(session, message);
    case 'summary':
    case 'review':
      // A typed message while buttons are showing is treated as a change request.
      user(session, message);
      return session.state === 'summary'
        ? applySpecChange(session, message, false)
        : applyDesignChange(session, message, false);
    default:
      user(session, message);
      bot(session, 'Use the options above to continue.');
      return saveSession(session);
  }
}

export async function handleAction(session, actionId) {
  switch (`${session.state}:${actionId}`) {
    case 'summary:spec_ok':
      user(session, 'Looks right — build it');
      return startGeneration(session);
    case 'summary:spec_change':
      user(session, 'Change something');
      session.state = 'change';
      bot(session, 'No problem — what should be different? Be as specific as you like.');
      return saveSession(session);
    case 'review:design_ok':
      user(session, 'Approve this design');
      session.state = 'details';
      bot(session, 'Great — that design is approved. Last step: a few details so we can price it and get back to you.');
      return saveSession(session);
    case 'review:design_reject':
      user(session, 'Not quite — change it');
      session.state = 'reject';
      bot(session, 'Tell me what to change and I\'ll remodel it.');
      return saveSession(session);
    default:
      return session;
  }
}

/* ---------------------------- intake ---------------------------- */

async function handleBrief(session, message) {
  user(session, message);
  if (message.length < 8) {
    bot(session, 'Could you give me a little more detail? One sentence describing the part is plenty.');
    return saveSession(session);
  }
  session.brief = message;
  const plan = await llm.planQuestions(message);
  session.product = plan.product;
  session.questions = plan.questions;
  session.qIndex = 0;
  session.state = 'questions';
  bot(session, plan.acknowledgement);
  bot(session, `I've got ${plan.questions.length} quick questions, then I'll model it.`);
  askCurrentQuestion(session);
  return saveSession(session);
}

function askCurrentQuestion(session) {
  const q = session.questions[session.qIndex];
  if (!q) return;
  const n = `${session.qIndex + 1}/${session.questions.length}`;
  bot(session, `${n} · ${q.question}${q.why ? `\n_${q.why}_` : ''}`);
}

async function handleAnswer(session, message) {
  user(session, message);
  const q = session.questions[session.qIndex];
  if (!q) return saveSession(session);

  let answer = message;
  // Chip taps and short concrete answers don't need a model round-trip.
  const isChip = (q.options || []).some((o) => o.toLowerCase() === message.toLowerCase());
  if (!isChip) {
    try {
      const triage = await llm.triageAnswer({ brief: session.brief, question: q.question, message });
      answer = triage.normalised_answer || message;
      if (triage.kind !== 'answer' && triage.reply) bot(session, triage.reply);
    } catch (err) {
      console.warn('[flow] triage failed, taking the answer verbatim:', err.message);
    }
  }
  session.answers[q.id] = answer;
  session.qIndex += 1;

  if (session.qIndex < session.questions.length) {
    askCurrentQuestion(session);
    return saveSession(session);
  }
  return buildSummary(session);
}

async function buildSummary(session, change = null) {
  bot(session, 'Thanks — here\'s what I\'ll build:');
  session.spec = await llm.buildSpec({
    brief: session.brief,
    questions: session.questions,
    answers: session.answers,
    previousSpec: change ? session.spec : null,
    change,
  });
  session.state = 'summary';
  bot(session, formatSpec(session.spec), { type: 'spec', spec: session.spec });
  return saveSession(session);
}

function formatSpec(spec) {
  const lines = [
    `**${spec.title}**`,
    spec.one_liner,
    '',
    ...spec.details.map((d) => `• **${d.label}:** ${d.value}`),
    `• **Overall size:** ${spec.dimensions}`,
    `• **Process:** ${spec.process}`,
    `• **Material:** ${spec.material}`,
  ];
  if (spec.assumptions?.length) {
    lines.push('', '_Assumptions I made — tell me if any are wrong:_', ...spec.assumptions.map((a) => `– ${a}`));
  }
  return lines.join('\n');
}

async function applySpecChange(session, message, echo = true) {
  if (echo) user(session, message);
  bot(session, 'Updating the spec…');
  return buildSummary(session, message);
}

async function applyDesignChange(session, message, echo = true) {
  if (echo) user(session, message);
  bot(session, 'Understood — updating the design.');
  session.spec = await llm.buildSpec({
    brief: session.brief,
    questions: session.questions,
    answers: session.answers,
    previousSpec: session.spec,
    change: message,
  });
  bot(session, formatSpec(session.spec), { type: 'spec', spec: session.spec });
  return startGeneration(session);
}

/* ------------------------- model generation ------------------------- */

async function startGeneration(session) {
  if (session.generations >= config.limits.maxGenerationsPerSession) {
    session.state = 'details';
    bot(session, `We've hit the limit of ${config.limits.maxGenerationsPerSession} model builds for one chat. Leave your details and a person will take it from here with everything you've told me.`);
    return saveSession(session);
  }
  session.generations += 1;
  session.state = 'generating';
  session.job = { id: newId('j'), status: 'running', startedAt: Date.now() };
  bot(session, 'Writing the CAD model and rendering it now — about 30 to 60 seconds.');
  await saveSession(session);

  // Detached on purpose: the widget polls /api/session/:id for the result.
  runGeneration(session).catch(async (err) => {
    console.error('[flow] generation crashed:', err);
    session.job = { ...session.job, status: 'error', error: err.message };
    session.state = 'review';
    bot(session, 'I couldn\'t finish that model. You can adjust the description and I\'ll try again, or approve the spec and a person will pick it up manually.');
    await saveSession(session);
  });
  return session;
}

async function runGeneration(session) {
  const job = session.job;
  let { scad, notes } = await llm.generateScad(session.spec);
  let result = await renderScad(scad);

  for (let attempt = 0; attempt < 2 && !result.ok; attempt += 1) {
    console.warn(`[flow] render failed (attempt ${attempt + 1}): ${result.error}`);
    const repaired = await llm.repairScad({ spec: session.spec, scad, error: result.error });
    scad = repaired.scad;
    notes = repaired.notes || notes;
    result = await renderScad(scad);
  }

  if (!result.ok) {
    job.status = 'error';
    job.error = result.error;
    session.state = 'review';
    bot(session, 'That one defeated me — the geometry wouldn\'t render cleanly. Tell me what to simplify, or approve the spec as it stands and one of our engineers will model it by hand.');
    await saveSession(session);
    return;
  }

  const base = `${session.id}/${job.id}`;
  const stats = analyzeStl(result.stl);
  const [stlUrl, pngUrl, scadUrl] = await Promise.all([
    putFile(`${base}/model.stl`, result.stl, { download: `${slug(session.spec.title)}.stl` }),
    result.png ? putFile(`${base}/preview.png`, result.png) : Promise.resolve(null),
    putFile(`${base}/model.scad`, scad),
  ]);

  Object.assign(job, {
    status: 'done',
    finishedAt: Date.now(),
    scad,
    notes,
    stats,
    stlUrl,
    pngUrl,
    scadUrl,
    viewerUrl: `${config.publicUrl}/viewer/${session.id}/${job.id}`,
  });
  session.state = 'review';
  bot(session, notes ? `Done. ${notes}` : 'Done — here\'s your model.', {
    type: 'preview',
    imageUrl: pngUrl,
    viewerUrl: job.viewerUrl,
    stlUrl,
    stats,
    title: session.spec.title,
  });
  bot(session, 'Open the 3D viewer to spin it around, then approve it or tell me what to change.');
  await saveSession(session);
}

function slug(s) {
  return String(s || 'model').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'model';
}

/* ----------------------------- the lead ----------------------------- */

export async function submitLead(session, payload) {
  const errors = validateLead(payload);
  if (Object.keys(errors).length) return { ok: false, errors };

  const lead = {
    id: newId('q'),
    sessionId: session.id,
    receivedAt: new Date().toISOString(),
    name: payload.name.trim(),
    email: payload.email.trim(),
    phone: payload.phone.trim(),
    postcode: payload.postcode.trim().toUpperCase(),
    quantity: Number(payload.quantity),
    leadtime: payload.leadtime,
    notes: (payload.notes || '').trim().slice(0, 2000),
    product: session.product,
    brief: session.brief,
    spec: session.spec,
    files: session.job?.status === 'done'
      ? { stl: session.job.stlUrl, png: session.job.pngUrl, scad: session.job.scadUrl, viewer: session.job.viewerUrl }
      : null,
    stats: session.job?.stats || null,
    meta: session.meta,
  };

  session.lead = lead;
  session.state = 'done';
  bot(session, `Thanks ${lead.name.split(' ')[0]} — that's with us.`);
  bot(session, `We'll review your design and get back to you at **${lead.email}** with a price and lead time, usually within one business day. Your reference is **${lead.id.slice(2, 10).toUpperCase()}**.`);
  await saveSession(session);

  await appendLead(lead);

  // Notification failures must not lose the lead: it is already on disk.
  try {
    const sent = await notifyQuote(lead);
    if (sent.mode === 'preview') {
      bot(session, 'Preview mode is on, so nothing was emailed. Here is the request exactly as it would arrive:', {
        type: 'link',
        label: 'Preview the quote request',
        url: sent.previewUrl,
      });
      await saveSession(session);
    }
  } catch (err) {
    console.error('[flow] quote notification failed:', err);
  }

  return { ok: true, lead };
}

function validateLead(p = {}) {
  const errors = {};
  const str = (v) => String(v ?? '').trim();
  if (str(p.name).length < 2) errors.name = 'Please enter your name';
  if (!/^[^@\s]+@[^@\s.]+\.[^@\s]{2,}$/.test(str(p.email))) errors.email = 'Please enter a valid email';
  const digits = str(p.phone).replace(/[^\d]/g, '');
  if (digits.length < 8 || digits.length > 15) errors.phone = 'Please enter a valid mobile number';
  if (str(p.postcode).length < 3) errors.postcode = 'Please enter your post code';
  const qty = Number(p.quantity);
  if (!Number.isInteger(qty) || qty < 1 || qty > 100000) errors.quantity = 'Enter a quantity between 1 and 100,000';
  if (!LEAD_FIELDS.find((f) => f.name === 'leadtime').options.includes(str(p.leadtime))) errors.leadtime = 'Choose a lead time';
  return errors;
}
