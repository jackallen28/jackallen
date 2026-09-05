// Stand-in for api.anthropic.com used by the smoke test: it replies with
// schema-shaped JSON so the whole flow can run without spending tokens.
import http from 'node:http';

const CUBE_SPEC = {
  title: 'Wall bracket for 90 mm torch',
  one_liner: 'A wall-mounted cradle that holds a 90 mm diameter torch horizontally.',
  details: [
    { label: 'Cradle bore', value: '91 mm' },
    { label: 'Back plate', value: '110 x 60 x 5 mm' },
    { label: 'Fixings', value: '2 x M5 countersunk' },
  ],
  dimensions: '110 x 95 x 60 mm',
  process: '3D printing (FDM)',
  material: 'PETG',
  assumptions: ['Torch body is a plain cylinder', 'Mounted to a timber stud'],
};

const responses = {
  questions: {
    product: 'wall bracket for a torch',
    acknowledgement: 'Got it — a wall bracket to hold a 90 mm diameter torch.',
    questions: [
      { id: 'torch_length', question: 'How long is the torch body?', type: 'choice', options: ['200 mm', '250 mm', '300 mm'], why: 'Sets how wide the cradle needs to be.' },
      { id: 'mounting', question: 'What are you fixing it to?', type: 'choice', options: ['Timber stud', 'Plasterboard', 'Brick'], why: 'Changes the fixing holes.' },
      { id: 'orientation', question: 'Horizontal or vertical?', type: 'choice', options: ['Horizontal', 'Vertical'], why: 'Changes the cradle geometry.' },
    ],
  },
  spec: CUBE_SPEC,
  scad: { scad: 'cube_size = 40;\n$fn = 64;\ncube([cube_size, cube_size, cube_size], center = false);\n', notes: 'Built as a single extruded body with filleted corners.' },
  triage: { kind: 'answer', normalised_answer: '250 mm', reply: '' },
};

// The real API accepts only a subset of JSON Schema in output_config.format.
// Enforcing it here is the point: a schema the API would reject must fail the
// test suite, not production.
const UNSUPPORTED = ['maxItems', 'minimum', 'maximum', 'minLength', 'maxLength', 'pattern', 'multipleOf', 'uniqueItems', 'format'];

function schemaProblems(node, path = 'schema') {
  if (Array.isArray(node)) return node.flatMap((n, i) => schemaProblems(n, `${path}[${i}]`));
  if (!node || typeof node !== 'object') return [];

  const problems = [];
  for (const key of Object.keys(node)) {
    if (UNSUPPORTED.includes(key)) problems.push(`${path}.${key} is not supported`);
  }
  if ('minItems' in node && Number(node.minItems) > 1) problems.push(`${path}.minItems must be 0 or 1`);
  if (node.type === 'object' && node.properties) {
    if (node.additionalProperties !== false) problems.push(`${path} must set additionalProperties: false`);
    const missing = Object.keys(node.properties).filter((k) => !(node.required || []).includes(k));
    if (missing.length) problems.push(`${path}.required is missing ${missing.join(', ')}`);
  }
  for (const [key, value] of Object.entries(node)) {
    if (key !== 'required' && value && typeof value === 'object') problems.push(...schemaProblems(value, `${path}.${key}`));
  }
  return problems;
}

function pick(body) {
  const system = String(body.system || '');
  if (system.includes('plan the SHORTEST set of questions')) return responses.questions;
  if (system.includes('build specification')) return responses.spec;
  if (system.includes('Decide whether their message answers it')) return responses.triage;
  return responses.scad;
}

// REJECT_STRUCTURED=1 makes every structured-output request fail the way a
// stricter API would, so the prose-JSON fallback can be tested.
const rejectStructured = process.env.REJECT_STRUCTURED === '1';

function apiError(message) {
  return { type: 'error', error: { type: 'invalid_request_error', message } };
}

http.createServer((req, res) => {
  let raw = '';
  req.on('data', (c) => { raw += c; });
  req.on('end', () => {
    const body = JSON.parse(raw || '{}');

    const schema = body.output_config?.format?.schema;
    if (schema) {
      if (rejectStructured) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(apiError('structured outputs are not available')));
        return;
      }
      const problems = schemaProblems(schema);
      if (problems.length) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(apiError(`Invalid output_config.format.schema: ${problems.join('; ')}`)));
        return;
      }
    }

    const payload = pick(body);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      id: 'msg_test', type: 'message', role: 'assistant', model: body.model,
      content: [{ type: 'text', text: JSON.stringify(payload) }],
      stop_reason: 'end_turn', stop_sequence: null,
      usage: { input_tokens: 10, output_tokens: 10 },
    }));
  });
}).listen(Number(process.env.PORT) || 9333, function listening() {
  console.log(`fake anthropic on :${this.address().port}${rejectStructured ? ' (rejecting structured outputs)' : ''}`);
});
