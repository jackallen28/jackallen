// All Claude calls live here. Every call returns structured JSON via
// output_config.format so the flow engine never has to parse prose.
import Anthropic from '@anthropic-ai/sdk';
import { config } from './config.js';

const MODEL = config.anthropic.model;

// Built on first use so the process still boots (and /healthz still answers)
// when the key is missing or rotated in later.
let _client = null;
function client() {
  if (!_client) _client = new Anthropic({ apiKey: config.anthropic.apiKey });
  return _client;
}

// Server-side refusal fallbacks are a beta; if the deployed SDK/account does not
// have it, fall back to the plain endpoint once and remember that for the process.
let useFallbacks = true;

async function createMessage(params) {
  if (useFallbacks) {
    try {
      return await client().beta.messages.create({
        ...params,
        betas: ['server-side-fallback-2026-07-01'],
        fallbacks: 'default',
      });
    } catch (err) {
      const status = err?.status ?? err?.statusCode;
      const message = String(err?.error?.error?.message || err?.message || '');
      // Only blame the beta when the API actually complains about it — a 400
      // about anything else (a schema, say) must not silently disable it.
      if (status !== 400 && status !== 404) throw err;
      // Retry without the beta either way, but only stop trying it for good
      // when the API actually complained about it — a 400 about anything else
      // (a schema, say) must not silently disable it for the whole process.
      if (/fallback|beta/i.test(message)) {
        useFallbacks = false;
        console.warn('[llm] server-side fallbacks unavailable, continuing without them:', message);
      }
    }
  }
  return client().messages.create(params);
}

// Structured outputs accept a subset of JSON Schema: no maxItems, minimum,
// maximum, minLength, maxLength or pattern, and minItems only as 0 or 1. Sending
// one of those is a 400 from the API, so scrub them here rather than relying on
// every schema author remembering. Objects must also declare
// additionalProperties:false and list every property in required.
const UNSUPPORTED_KEYWORDS = ['maxItems', 'minimum', 'maximum', 'minLength', 'maxLength', 'pattern', 'multipleOf', 'uniqueItems', 'format'];

export function strictSchema(node) {
  if (Array.isArray(node)) return node.map(strictSchema);
  if (!node || typeof node !== 'object') return node;

  const out = {};
  for (const [key, value] of Object.entries(node)) {
    if (UNSUPPORTED_KEYWORDS.includes(key)) continue;
    if (key === 'minItems') {
      // Only 0 and 1 are accepted; a larger floor belongs in the prompt.
      out.minItems = Math.min(Number(value) || 0, 1);
      continue;
    }
    out[key] = strictSchema(value);
  }

  if (out.type === 'object' && out.properties) {
    out.additionalProperties = false;
    out.required = Object.keys(out.properties);
  }
  return out;
}

function textOf(message) {
  return message.content.filter((b) => b.type === 'text').map((b) => b.text).join('');
}

async function askJson({ system, messages, schema, effort = 'high', maxTokens = 16000 }) {
  const request = {
    model: MODEL,
    max_tokens: maxTokens,
    system,
    messages,
    thinking: { type: 'adaptive' },
    output_config: { effort, format: { type: 'json_schema', schema: strictSchema(schema) } },
  };

  let response;
  try {
    response = await createMessage(request);
  } catch (err) {
    if ((err?.status ?? err?.statusCode) !== 400) throw err;
    // The API rejected the request shape — most often the schema. Rather than
    // fail the customer's conversation, ask for the same JSON in prose and
    // parse it ourselves.
    console.warn('[llm] structured output rejected, falling back to prose JSON:', err.message);
    response = await createMessage({
      model: MODEL,
      max_tokens: maxTokens,
      system: `${system}\n\nReply with a single JSON object matching this schema and nothing else — no prose, no code fences:\n${JSON.stringify(schema)}`,
      messages,
      thinking: { type: 'adaptive' },
    });
  }

  if (response.stop_reason === 'refusal') {
    const err = new Error('The assistant declined this request.');
    err.code = 'refusal';
    throw err;
  }
  const raw = textOf(response);
  try {
    return JSON.parse(raw);
  } catch { /* fall through to the lenient parse below */ }
  try {
    // The prose fallback can wrap the object in stray text or a code fence.
    return JSON.parse(raw.slice(raw.indexOf('{'), raw.lastIndexOf('}') + 1));
  } catch {
    // Extremely rare with structured outputs, but a truncated response is possible.
    const err = new Error(`Model returned unparseable JSON (stop_reason=${response.stop_reason})`);
    err.code = 'bad_json';
    throw err;
  }
}

/** Smallest possible call, to prove the key and model work. Used by /diag. */
export async function checkModel() {
  if (!config.anthropic.apiKey) return { ok: false, error: 'ANTHROPIC_API_KEY is not set' };
  try {
    const response = await createMessage({
      model: MODEL,
      max_tokens: 16,
      messages: [{ role: 'user', content: 'Reply with the single word: ready' }],
    });
    return { ok: true, model: MODEL, reply: textOf(response).trim().slice(0, 40) };
  } catch (err) {
    return {
      ok: false,
      model: MODEL,
      status: err?.status ?? err?.statusCode ?? null,
      error: String(err?.message || err).slice(0, 300),
    };
  }
}

/**
 * Runs the first real structured-output call — the one a conversation makes —
 * and reports the API's own error if it fails. This is what /diag?full=1 uses:
 * a plain message proves the key works, only this proves the request shape does.
 */
export async function checkStructuredOutput() {
  try {
    const plan = await planQuestions('a wall bracket to hold a 90 mm diameter torch');
    return { ok: true, questions: plan.questions.length, sample: plan.questions[0]?.question };
  } catch (err) {
    return {
      ok: false,
      status: err?.status ?? err?.statusCode ?? null,
      type: err?.error?.error?.type || err?.code || null,
      error: String(err?.error?.error?.message || err?.message || err).slice(0, 500),
    };
  }
}

const SHARED_CONTEXT = `You are the intake engineer for a workshop that 3D prints (FDM/SLA) and CNC machines
one-off and small-batch parts. You turn a customer's plain-language description into a
manufacturable parametric design, and you are pragmatic: customers are usually not engineers,
so you ask few, high-value questions and fill the rest with sensible defaults you state openly.
All dimensions are millimetres unless the customer says otherwise.`;

/* ------------------------------------------------------------------ */
/* 1. Question plan                                                    */
/* ------------------------------------------------------------------ */

const QUESTION_PLAN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['product', 'acknowledgement', 'questions'],
  properties: {
    product: { type: 'string', description: 'Short noun phrase naming what the customer wants, e.g. "wall-mounted headphone hook"' },
    acknowledgement: { type: 'string', description: 'One friendly sentence confirming what you understood. No questions in it.' },
    questions: {
      type: 'array',
      description: 'Between 3 and 6 questions. Never more.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'question', 'type', 'options', 'why'],
        properties: {
          id: { type: 'string', description: 'snake_case key, e.g. "overall_height"' },
          question: { type: 'string', description: 'The question as asked in chat. One question only.' },
          type: { type: 'string', enum: ['text', 'choice', 'number'] },
          options: {
            type: 'array',
            items: { type: 'string' },
            description: 'At most 5 tappable suggested answers. Required for type=choice, otherwise up to 4 common values, or an empty array.',
          },
          why: { type: 'string', description: 'Half-sentence explaining why it matters, shown as helper text.' },
        },
      },
    },
  },
};

export function planQuestions(brief) {
  return askJson({
    effort: 'medium',
    system: `${SHARED_CONTEXT}

Given a one-line brief, plan the SHORTEST set of questions that would let you model the part
in OpenSCAD without guessing anything important. Rules:
- 3 to 6 questions. Never more. Fewer is better.
- Always cover overall size/fit constraints and the intended use or load if they are unclear.
- Ask about mounting/fixing method, material or process (3D print vs CNC), and any mating
  dimensions ONLY when they genuinely change the geometry.
- Never ask about quantity, lead time, budget, delivery or contact details — those are collected later.
- Never ask two things in one question.
- Offer tappable options with realistic values (include units) wherever a customer could reasonably pick from a shortlist.
- Plain language. No CAD jargon.`,
    messages: [{ role: 'user', content: `Customer brief: """${brief}"""` }],
    schema: QUESTION_PLAN_SCHEMA,
  });
}

/* ------------------------------------------------------------------ */
/* 2. Specification                                                    */
/* ------------------------------------------------------------------ */

const SPEC_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['title', 'one_liner', 'details', 'dimensions', 'process', 'material', 'assumptions'],
  properties: {
    title: { type: 'string' },
    one_liner: { type: 'string', description: 'One sentence describing the part.' },
    details: {
      type: 'array',
      description: 'Between 3 and 10 key/value spec lines.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['label', 'value'],
        properties: { label: { type: 'string' }, value: { type: 'string' } },
      },
      description: 'Key/value spec lines, e.g. {"label":"Hook depth","value":"45 mm"}.',
    },
    dimensions: { type: 'string', description: 'Overall envelope, e.g. "80 x 40 x 25 mm".' },
    process: { type: 'string', enum: ['3D printing (FDM)', '3D printing (SLA)', 'CNC machining', 'Either — to be confirmed'] },
    material: { type: 'string', description: 'Suggested material, e.g. "PETG" or "6061 aluminium".' },
    assumptions: {
      type: 'array',
      items: { type: 'string' },
      description: 'At most 6 items: anything you filled in yourself so the customer can correct it.',
    },
  },
};

export function buildSpec({ brief, questions, answers, previousSpec = null, change = null }) {
  const qa = questions.map((q) => `- ${q.question}\n  answer: ${answers[q.id] ?? '(skipped)'}`).join('\n');
  const revision = previousSpec
    ? `\n\nThe customer previously approved this spec:\n${JSON.stringify(previousSpec, null, 2)}\n\nThey now want this changed: """${change}"""\nApply the change, keep everything else identical.`
    : '';
  return askJson({
    effort: 'medium',
    system: `${SHARED_CONTEXT}

Write a tight build specification the customer can check at a glance. Rules:
- Every dimension is a concrete number in mm. Never write "TBC" or "as required" — choose a sensible value and list it under assumptions.
- "details" must be specific enough that two different engineers would model the same part.
- Keep it to the part itself: no pricing, no lead time, no delivery.
- Plain language a non-engineer can verify.`,
    messages: [{
      role: 'user',
      content: `Customer brief: """${brief}"""\n\nIntake answers:\n${qa}${revision}`,
    }],
    schema: SPEC_SCHEMA,
  });
}

/* ------------------------------------------------------------------ */
/* 3. OpenSCAD source                                                  */
/* ------------------------------------------------------------------ */

const SCAD_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['scad', 'notes'],
  properties: {
    scad: { type: 'string', description: 'Complete, self-contained OpenSCAD source.' },
    notes: { type: 'string', description: 'One or two sentences for the customer about how the model was built.' },
  },
};

const SCAD_RULES = `Write complete, self-contained OpenSCAD source for the specified part. Hard rules:
- No include<>, use<>, import(), surface() or any file/network access. The file must stand alone.
- Units are millimetres. Model the real part at 1:1.
- Put every dimension in a named parameter block at the top of the file, with comments.
- Set $fn between 48 and 120 (a single global $fn, never above 200).
- Produce ONE manifold solid: union everything, avoid coincident faces (overlap joined solids by
  at least 0.01 mm, and overshoot every cut by 0.1 mm on each open end).
- Design it to actually manufacture: no unsupported overhangs beyond ~45 degrees on printed parts,
  minimum wall 1.6 mm for FDM / 1 mm for SLA / 1.5 mm for machined aluminium, fillet or chamfer
  stress corners, and add clearance (0.3 mm FDM, 0.1 mm CNC) on any mating feature.
- Centre the part sensibly and stand it on the Z=0 plane so it previews and slices correctly.
- The whole model must render in well under 60 seconds.
- Do not emit echo() debug spam, animation, or anything that needs command-line -D arguments.`;

export function generateScad(spec) {
  return askJson({
    effort: 'high',
    system: `${SHARED_CONTEXT}\n\n${SCAD_RULES}`,
    messages: [{ role: 'user', content: `Build this part.\n\n${JSON.stringify(spec, null, 2)}` }],
    schema: SCAD_SCHEMA,
  });
}

export function repairScad({ spec, scad, error }) {
  return askJson({
    effort: 'high',
    system: `${SHARED_CONTEXT}\n\n${SCAD_RULES}`,
    messages: [{
      role: 'user',
      content: `This OpenSCAD source failed to render.\n\nSpec:\n${JSON.stringify(spec, null, 2)}\n\nSource:\n\`\`\`\n${scad}\n\`\`\`\n\nOpenSCAD reported:\n\`\`\`\n${error}\n\`\`\`\n\nReturn corrected source that renders to a single manifold solid. Fix the cause, do not simplify the part away.`,
    }],
    schema: SCAD_SCHEMA,
  });
}

/* ------------------------------------------------------------------ */
/* 4. Answer triage — did the customer answer, or ask us something?     */
/* ------------------------------------------------------------------ */

const TRIAGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['kind', 'normalised_answer', 'reply'],
  properties: {
    kind: {
      type: 'string',
      enum: ['answer', 'question', 'unsure'],
      description: 'answer = they answered it; question = they asked us something instead; unsure = they explicitly do not know.',
    },
    normalised_answer: { type: 'string', description: 'Their answer tidied up with units, or your recommended default when kind is question/unsure.' },
    reply: { type: 'string', description: 'Max 2 sentences. For question/unsure: answer them and state the value you will use. For answer: empty string.' },
  },
};

export function triageAnswer({ brief, question, message }) {
  return askJson({
    effort: 'low',
    maxTokens: 2000,
    system: `${SHARED_CONTEXT}

You asked the customer one intake question. Decide whether their message answers it.
If they asked you something or said they do not know, answer briefly and pick a sensible
default value yourself so the intake can move on. Never ask a follow-up question.`,
    messages: [{
      role: 'user',
      content: `Product brief: """${brief}"""\nQuestion asked: """${question}"""\nCustomer said: """${message}"""`,
    }],
    schema: TRIAGE_SCHEMA,
  });
}
