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

function pick(body) {
  const system = String(body.system || '');
  if (system.includes('plan the SHORTEST set of questions')) return responses.questions;
  if (system.includes('build specification')) return responses.spec;
  if (system.includes('Decide whether their message answers it')) return responses.triage;
  return responses.scad;
}

http.createServer((req, res) => {
  let raw = '';
  req.on('data', (c) => { raw += c; });
  req.on('end', () => {
    const body = JSON.parse(raw || '{}');
    const payload = pick(body);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      id: 'msg_test', type: 'message', role: 'assistant', model: body.model,
      content: [{ type: 'text', text: JSON.stringify(payload) }],
      stop_reason: 'end_turn', stop_sequence: null,
      usage: { input_tokens: 10, output_tokens: 10 },
    }));
  });
}).listen(9333, () => console.log('fake anthropic on :9333'));
