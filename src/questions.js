/**
 * Question bank for "Mind Feud".
 *
 * Every board question has exactly 6 answers, ranked like a Family Feud survey
 * so the point values total 100. Higher-ranked answers are the "obvious" ones,
 * which rewards students who push past the first thing that comes to mind.
 *
 * Each answer carries:
 *   text    - what appears on the board when revealed
 *   points  - the survey value (before the round multiplier)
 *   accept  - alias phrases the local matcher will accept. A guess matches an
 *             alias when every significant word of that alias appears in the
 *             guess (fuzzily, so typos and plurals are fine). Keep aliases
 *             specific: a one-word alias like "brain" would swallow half the
 *             board.
 *
 * `nearMiss` entries are answers that are genuinely correct but did not make
 * the board. They still cost the team their turn (that is the rule), but the
 * host screen calls them out — this is the moment the real show lives for, and
 * it is where the actual teaching happens.
 */

export const ROUNDS = [
  {
    id: 'r1',
    name: 'Round 1 — Sensation, Perception & Illusion',
    weeks: 'Weeks 2–3',
    multiplier: 1,
    questions: [
      {
        id: 'r1q1',
        prompt: 'We surveyed 100 students of the mind: name a way your brain proves that PERCEPTION is not the same thing as SENSATION.',
        answers: [
          { text: 'Visual illusions — Müller-Lyer, Ponzo, the Ames Room', points: 28,
            accept: ['visual illusion', 'optical illusion', 'muller lyer', 'ponzo', 'ames room', 'ebbinghaus', 'zollner', 'jastrow'] },
          { text: 'The Dress / Yanny vs Laurel — same signal, different experience', points: 22,
            accept: ['the dress', 'blue black white gold', 'yanny', 'laurel', 'yanny laurel', 'same input different perception', 'people see it differently'] },
          { text: 'Top-down processing — expectation fills in what is not there', points: 17,
            accept: ['top down processing', 'top down', 'expectations fill gaps', 'scrambled text', 'garden path sentence', 'priming', 'context changes what you see'] },
          { text: 'Change blindness & selective attention — the gorilla you missed', points: 14,
            accept: ['change blindness', 'selective attention', 'inattentional blindness', 'attention spotlight', 'the gorilla', 'invisible gorilla', 'missing the gorilla'] },
          { text: 'The McGurk effect — what you SEE overrides what you HEAR', points: 11,
            accept: ['mcgurk effect', 'mcgurk', 'lips override sound', 'seeing changes hearing'] },
          { text: 'Perceptual constancy — size, colour and shape stay put anyway', points: 8,
            accept: ['perceptual constancy', 'constancy', 'size constancy', 'colour constancy', 'color constancy', 'shape constancy'] },
        ],
        nearMiss: [
          { text: 'Synaesthesia — #7, just off the board', accept: ['synaesthesia', 'synesthesia', 'hearing colours', 'hearing colors', 'tasting sounds'] },
          { text: 'The rubber hand illusion — that is Round 1, Question 3!', accept: ['rubber hand', 'rubber hand illusion'] },
        ],
      },
      {
        id: 'r1q2',
        prompt: 'Gestalt means "shape" or "form". Name a Gestalt principle — a rule your brain uses to group what it sees into something sensible.',
        answers: [
          { text: 'Closure — the brain fills in the missing gaps', points: 26,
            accept: ['closure', 'filling in gaps', 'fills in the gaps', 'completing the shape'] },
          { text: 'Proximity — things that are close together group together', points: 23,
            accept: ['proximity', 'closeness', 'close together grouped'] },
          { text: 'Similarity — things that look alike group together', points: 20,
            accept: ['similarity', 'similar things grouped', 'look alike grouped'] },
          { text: 'Figure–Ground — picking the figure out of the background', points: 16,
            accept: ['figure ground', 'figure and ground', 'rubins vase', 'rubin vase', 'vase or faces', 'foreground background'] },
          { text: 'The Law of Prägnanz — the brain always chooses the simplest order', points: 9,
            accept: ['pragnanz', 'law of pragnanz', 'pragnanz law', 'simplicity', 'simplest interpretation', 'good figure', 'law of simplicity'] },
          { text: 'Continuity — the eye follows the smoothest path', points: 6,
            accept: ['continuity', 'continuation', 'good continuation', 'smooth path', 'follows the line'] },
        ],
        nearMiss: [
          { text: 'Common fate — a real Gestalt principle, but not on our board', accept: ['common fate', 'moving together'] },
        ],
      },
      {
        id: 'r1q3',
        prompt: 'Name an experiment or demonstration from this unit where one sense HIJACKS another — or hijacks your body altogether.',
        answers: [
          { text: 'The Rubber Hand Illusion — the brain adopts a fake limb', points: 27,
            accept: ['rubber hand illusion', 'rubber hand', 'fake hand', 'the brush and the fake hand'] },
          { text: 'The McGurk Effect — lip movements rewrite the sound', points: 21,
            accept: ['mcgurk effect', 'mcgurk', 'lips change the sound', 'ba ga da'] },
          { text: 'Apple vs potato — nose pinched, eyes shut, smell writes the taste', points: 18,
            accept: ['apple and potato', 'apple potato', 'nose pinched', 'holding your nose', 'smell affects taste', 'olfactory taste', 'taste test'] },
          { text: 'The Stroop Test — reading fights colour naming', points: 15,
            accept: ['stroop test', 'stroop', 'colour word interference', 'color word test'] },
          { text: 'Yanny vs Laurel — one sound file, two realities', points: 12,
            accept: ['yanny', 'laurel', 'yanny or laurel'] },
          { text: 'Synaesthesia — one sense automatically triggers another', points: 7,
            accept: ['synaesthesia', 'synesthesia', 'hearing colours', 'hearing colors', 'seeing sounds', 'tasting words'] },
        ],
        nearMiss: [
          { text: 'Phantom limb pain / prosthetic embodiment — the clinical payoff of the rubber hand', accept: ['phantom limb', 'prosthetic', 'amputee', 'mirror box'] },
        ],
      },
    ],
  },

  {
    id: 'r2',
    name: 'Round 2 — Souls, Selves & Substances',
    weeks: 'Weeks 4–5',
    multiplier: 2,
    questions: [
      {
        id: 'r2q1',
        prompt: 'Descartes set out to doubt absolutely everything. Name something he found he COULD doubt — or the one thing he found he could not.',
        answers: [
          { text: 'His senses — they deceive him with illusions', points: 25,
            accept: ['his senses', 'the senses', 'sensory information', 'senses deceive', 'illusions trick him', 'what he sees'] },
          { text: 'The physical world and his own body — he might be dreaming', points: 21,
            accept: ['the physical world', 'his body', 'the external world', 'dreaming', 'the dream argument', 'whether he is dreaming', 'physical objects'] },
          { text: 'Mathematics — a malevolent demon could be deceiving him', points: 18,
            accept: ['mathematics', 'maths', 'math', 'two plus two', 'evil demon', 'malevolent demon', 'evil genius', 'the demon'] },
          { text: 'That he exists as a thinking thing — the ONE thing he could not doubt', points: 16,
            accept: ['cogito ergo sum', 'i think therefore i am', 'that he thinks', 'that he exists', 'his own existence', 'the cogito', 'his mind exists', 'he is a thinking thing'] },
          { text: 'Whether other people have minds at all', points: 12,
            accept: ['other minds', 'other people have minds', 'whether others think', 'other peoples minds'] },
          { text: 'Whether he is awake right now', points: 8,
            accept: ['whether he is awake', 'being awake', 'awake or asleep', 'if he is asleep'] },
        ],
        nearMiss: [
          { text: 'God — Descartes argued God would not deceive him. Off the board!', accept: ['god', 'the existence of god'] },
        ],
      },
      {
        id: 'r2q2',
        prompt: 'Substance dualism has taken a beating for 380 years. Name an OBJECTION to Descartes\' dualism.',
        answers: [
          { text: 'Elisabeth of Bohemia\'s Interaction Problem — how does a non-physical mind push matter?', points: 30,
            accept: ['interaction problem', 'elisabeth of bohemia', 'princess elisabeth', 'how does the mind move the body', 'mind cant touch the body', 'no physical contact'] },
          { text: 'Conservation of energy — the mind would inject energy from nowhere', points: 22,
            accept: ['conservation of energy', 'law of conservation of energy', 'energy from nowhere', 'breaks physics', 'closed system'] },
          { text: 'Ockham\'s Razor — one substance is simpler than two', points: 18,
            accept: ['ockhams razor', 'occams razor', 'razor', 'simplest explanation', 'fewest assumptions', 'one substance is simpler'] },
          { text: 'The Pool Hall Analogy — no contact, no push', points: 14,
            accept: ['pool hall', 'pool ball', 'billiard', 'pool table analogy', 'cant move a ball with your mind'] },
          { text: 'The pineal gland answer does not actually solve anything', points: 10,
            accept: ['pineal gland', 'the pineal gland fails', 'his answer was the pineal gland'] },
          { text: 'Neuroscience — damage the brain and you damage the person', points: 6,
            accept: ['neuroscience', 'brain damage', 'phineas gage', 'gage', 'brain injury changes personality', 'evidence from the brain'] },
        ],
        nearMiss: [
          { text: 'Drugs and anaesthetic change the mind physically — that is Round 4!', accept: ['drugs', 'anaesthetic', 'anesthetic', 'medication'] },
        ],
      },
      {
        id: 'r2q3',
        prompt: 'Every tradition we studied has an answer to "what is the self?". Name a tradition\'s answer — the thinker, the term, or the idea.',
        answers: [
          { text: 'Buddhist Anattā — there is NO permanent self, only the Five Aggregates', points: 25,
            accept: ['anatta', 'no self', 'non self', 'buddhism', 'buddhist', 'five aggregates', 'skandhas', 'the chariot analogy', 'bundle of processes'] },
          { text: 'Hindu Ātman — the eternal true Self, one with Brahman', points: 21,
            accept: ['atman', 'hindu', 'hinduism', 'brahman', 'eternal self'] },
          { text: 'The Christian soul — immortal, imago Dei, judged after death', points: 18,
            accept: ['christian soul', 'christianity', 'imago dei', 'image of god', 'immortal soul', 'made by god', 'judged after death'] },
          { text: 'Islamic Rūh — the divine spirit breathed into us, surviving death', points: 15,
            accept: ['ruh', 'islam', 'islamic', 'muslim', 'divine spirit', 'breathed into us'] },
          { text: 'Plato\'s Tripartite Soul — Reason, Spirit and Appetite', points: 13,
            accept: ['plato', 'tripartite soul', 'three parts of the soul', 'charioteer', 'reason spirit appetite', 'the chariot and horses', 'black horse white horse', 'nous'] },
          { text: 'Avicenna\'s Floating Man — the self known with no senses at all', points: 8,
            accept: ['avicenna', 'floating man', 'flying man', 'ibn sina', 'the man in the air'] },
        ],
        nearMiss: [
          { text: 'Descartes\' thinking thing — correct philosophy, wrong question. Off the board!', accept: ['descartes', 'cogito', 'thinking thing'] },
        ],
      },
    ],
  },

  {
    id: 'r3',
    name: 'Round 3 — Source Analysis & Significance',
    weeks: 'Assessment skills — PCASTLE & the 5 criteria',
    multiplier: 2,
    questions: [
      {
        id: 'r3q1',
        prompt: 'PCASTLE has SEVEN letters. Our board only has SIX. Name a PCASTLE question — and hope yours made the cut.',
        answers: [
          { text: 'P — Purpose: why was it made? What did the creator want?', points: 24,
            accept: ['purpose', 'why was it made', 'why was it created', 'the creators goal', 'p for purpose'] },
          { text: 'A — Author: who made it, and what do they know?', points: 21,
            accept: ['author', 'who made it', 'who wrote it', 'the creator', 'their expertise', 'a for author'] },
          { text: 'C — Context: when and where, and what was happening?', points: 19,
            accept: ['context', 'when and where', 'historical context', 'what was happening at the time', 'c for context'] },
          { text: 'S — Source type: primary or secondary? Speech, text, news?', points: 15,
            accept: ['source type', 'primary or secondary', 'what kind of source', 'type of source', 's for source'] },
          { text: 'T — Tone / Bias: what is the creator\'s attitude?', points: 13,
            accept: ['tone', 'bias', 'tone and bias', 'attitude', 'is it biased', 't for tone'] },
          { text: 'L — Language / Audience: who was it written FOR?', points: 8,
            accept: ['language', 'audience', 'language and audience', 'who is it for', 'word choice', 'l for language'] },
        ],
        nearMiss: [
          { text: 'E — EVIDENCE. It is the 7th letter of PCASTLE and it is NOT on the board. Ohhh!',
            accept: ['evidence', 'e for evidence', 'the facts provided', 'reliability of the facts'] },
        ],
      },
      {
        id: 'r3q2',
        prompt: 'A student argues Phineas Gage was historically significant. Name a SIGNIFICANCE CRITERION they could use — or the evidence they would cite for it.',
        answers: [
          { text: 'DEPTH — it fundamentally changed how people thought about brain and personality', points: 25,
            accept: ['depth', 'how deeply it changed thinking', 'changed ideas fundamentally', 'profoundly changed thinking'] },
          { text: 'DURABILITY — 175 years later it is still in every textbook', points: 21,
            accept: ['durability', 'how long it lasted', 'still matters today', 'lasting effect', 'still in textbooks'] },
          { text: 'RELEVANCE — it connects straight to modern neuroscience and brain injury', points: 18,
            accept: ['relevance', 'why it matters to us', 'connects to today', 'modern concerns', 'relevant now'] },
          { text: 'IMPORTANCE — doctors and scientists at the time cared enormously', points: 15,
            accept: ['importance', 'how much it mattered at the time', 'who cared at the time', 'mattered to people then'] },
          { text: 'QUANTITY — how many people the resulting neuroscience reached', points: 12,
            accept: ['quantity', 'how many people affected', 'number of people', 'breadth'] },
          { text: 'THE EVIDENCE ITSELF — Harlow\'s reports and the tamping iron', points: 9,
            accept: ['harlows report', 'john harlow', 'the tamping iron', 'the iron bar', 'medical reports', 'the physical evidence', 'his skull'] },
        ],
        nearMiss: [
          { text: 'Macmillan\'s challenge — that Gage recovered. Great critique, not a criterion!',
            accept: ['macmillan', 'malcolm macmillan', 'he recovered', 'stagecoach driver', 'chile'] },
        ],
      },
      {
        id: 'r3q3',
        prompt: 'I hand you Descartes\' "Meditations", published 1641. Run PCASTLE on it — name a question you would ask AND what you would find.',
        answers: [
          { text: 'PURPOSE — to rebuild all knowledge on something absolutely certain', points: 24,
            accept: ['purpose', 'why he wrote it', 'to find certainty', 'to rebuild knowledge', 'to prove the soul'] },
          { text: 'AUTHOR — Descartes: mathematician, scientist and a devout Catholic', points: 20,
            accept: ['author', 'who wrote it', 'descartes himself', 'a mathematician', 'he was catholic', 'his background'] },
          { text: 'CONTEXT — 1640s, the Scientific Revolution, with Galileo just condemned', points: 19,
            accept: ['context', 'the scientific revolution', 'galileo', 'the church at the time', 'seventeenth century', '1600s', 'the inquisition'] },
          { text: 'SOURCE TYPE — a primary source, a philosophical text, not a report', points: 15,
            accept: ['source type', 'primary source', 'philosophical text', 'its primary', 'a book he wrote'] },
          { text: 'TONE / BIAS — he is arguing a case, not reporting neutrally', points: 13,
            accept: ['tone', 'bias', 'hes arguing a case', 'persuasive', 'not neutral', 'trying to convince you'] },
          { text: 'AUDIENCE — dedicated to the theologians of the Sorbonne', points: 9,
            accept: ['audience', 'who it was for', 'the sorbonne', 'theologians', 'the church', 'educated scholars', 'language and audience'] },
        ],
        nearMiss: [
          { text: 'EVIDENCE — what does he actually prove? The 7th letter strikes again!',
            accept: ['evidence', 'what evidence does he give', 'his proof', 'reliability'] },
        ],
      },
    ],
  },

  {
    id: 'r4',
    name: 'Round 4 — Brains, Machines & Minds (TRIPLE POINTS)',
    weeks: 'Weeks 6–8',
    multiplier: 3,
    questions: [
      {
        id: 'r4q1',
        prompt: 'A 1.1 metre iron bar goes through Phineas Gage\'s frontal lobe and he WALKS AWAY. Name what changed — or a reason a dualist says it proves nothing.',
        answers: [
          { text: 'His personality — "no longer Gage": fitful, irreverent, profane', points: 26,
            accept: ['his personality', 'personality changed', 'no longer gage', 'he became rude', 'profane', 'irreverent', 'he changed as a person', 'his character'] },
          { text: 'Almost nothing else — speech, memory, movement and intelligence survived', points: 20,
            accept: ['nothing else changed', 'his memory was fine', 'his speech was fine', 'intelligence was intact', 'he could still walk and talk', 'movement was fine'] },
          { text: 'The Damaged Radio Analogy — you broke the receiver, not the music', points: 18,
            accept: ['damaged radio', 'broken radio', 'radio analogy', 'the music comes from elsewhere', 'the signal not the source', 'the receiver is damaged'] },
          { text: 'Correlation is not identity — changing together is not being the same thing', points: 15,
            accept: ['correlation is not identity', 'correlation not causation', 'correlation doesnt prove identity', 'just because they change together'] },
          { text: 'The evidence is shaky — Harlow wrote his famous report 20 years later', points: 12,
            accept: ['harlow wrote it later', 'twenty years later', 'the report was late', 'unreliable evidence', 'written from memory', 'weak evidence'] },
          { text: 'He adapted — Macmillan showed Gage worked as a stagecoach driver in Chile', points: 9,
            accept: ['he recovered', 'he adapted', 'macmillan', 'stagecoach driver', 'chile', 'he got better', 'he held down a job'] },
        ],
        nearMiss: [
          { text: 'He survived for 12 more years — true, but not on the board!', accept: ['he survived', 'he lived for years', 'twelve more years', 'he didnt die'] },
        ],
      },
      {
        id: 'r4q2',
        prompt: 'Turing said a machine that talks like us, thinks. Name an OBJECTION — a reason people say a machine cannot really think.',
        answers: [
          { text: 'Searle\'s Chinese Room — syntax is not semantics', points: 27,
            accept: ['chinese room', 'searle', 'john searle', 'syntax is not semantics', 'rulebook', 'symbol manipulation', 'the man in the room'] },
          { text: 'The Lady Lovelace Objection — it only does what it is programmed to do', points: 22,
            accept: ['lady lovelace', 'ada lovelace', 'lovelace objection', 'only does what its programmed', 'it cant originate anything', 'no creativity'] },
          { text: 'The Consciousness Objection — it can act emotional without feeling anything', points: 18,
            accept: ['consciousness objection', 'it doesnt feel anything', 'no inner experience', 'acting emotional without feeling', 'theres nobody home', 'no qualia'] },
          { text: 'The Disabilities Objection — it will never fall in love or enjoy strawberries', points: 15,
            accept: ['disabilities objection', 'it cant fall in love', 'cant enjoy strawberries', 'strawberries and cream', 'it cant feel love'] },
          { text: 'It is imitation, not understanding — Eugene Goostman gamed the test', points: 11,
            accept: ['eugene goostman', 'goostman', 'its just imitation', 'it tricks you', 'pretending to be a boy', 'gaming the test', 'a cheap trick'] },
          { text: 'It is made of the wrong stuff — silicon is not a brain', points: 7,
            accept: ['made of the wrong stuff', 'silicon not carbon', 'its not biological', 'it has no brain', 'wrong material'] },
        ],
        nearMiss: [
          { text: 'Functionalism says the material does not matter — that is Turing\'s REPLY, not the objection!',
            accept: ['functionalism', 'what it does not what its made of'] },
        ],
      },
      {
        id: 'r4q3',
        prompt: 'Final board question. Name something a MATERIALIST points to as evidence that the mind simply IS the brain.',
        answers: [
          { text: 'Brain damage changes the person — Gage, and every case since', points: 25,
            accept: ['brain damage', 'brain injury', 'phineas gage', 'gage', 'damage changes personality', 'head injury'] },
          { text: 'Drugs change consciousness — caffeine, painkillers, alcohol', points: 21,
            accept: ['drugs', 'caffeine', 'painkillers', 'pain relief', 'alcohol', 'medication changes your mind', 'chemicals change how you think'] },
          { text: 'General anaesthetic switches consciousness OFF entirely', points: 17,
            accept: ['anaesthetic', 'anesthetic', 'general anaesthetic', 'going under', 'surgery knocks you out', 'switches consciousness off'] },
          { text: 'Deep Brain Stimulation — run electricity through it and mood changes', points: 14,
            accept: ['deep brain stimulation', 'dbs', 'electricity', 'electrical stimulation', 'stimulating the brain changes mood'] },
          { text: 'Lobotomies changed people permanently and physically', points: 12,
            accept: ['lobotomy', 'lobotomies', 'brain surgery', 'cutting the frontal lobe'] },
          { text: 'The PATTERN — millions of cases, repeatable and predictable', points: 11,
            accept: ['the pattern', 'millions of cases', 'its repeatable', 'predictable', 'happens every time', 'not just one case'] },
        ],
        nearMiss: [
          { text: 'Ockham\'s Razor — a materialist argument, but not evidence. Round 2 territory!',
            accept: ['ockhams razor', 'occams razor', 'simplest explanation'] },
        ],
      },
    ],
  },
];

/**
 * Final round bank — short, fast, one accepted concept each.
 * The leading team races the clock; anything they miss or pass falls into the
 * spoiler pile for the trailing team.
 */
export const RAPID_FIRE = [
  { prompt: 'Two Latin words: Descartes\' proof that he exists.',
    accept: ['cogito ergo sum', 'i think therefore i am', 'cogito'] },
  { prompt: 'The raw data your eyes and ears collect — one word.',
    accept: ['sensation', 'sensory input', 'raw data'] },
  { prompt: 'The brain\'s interpretation of that data — one word.',
    accept: ['perception', 'interpreting it', 'interpretation'] },
  { prompt: 'Who asked Descartes how a non-physical mind can push a physical body?',
    accept: ['elisabeth of bohemia', 'princess elisabeth', 'elisabeth'] },
  { prompt: 'The rulebook thought experiment that says syntax is not semantics.',
    accept: ['the chinese room', 'chinese room', 'searles chinese room'] },
  { prompt: 'The 1848 railroad foreman with an iron bar through his frontal lobe.',
    accept: ['phineas gage', 'gage'] },
  { prompt: 'Turing\'s original name for the Turing Test.',
    accept: ['the imitation game', 'imitation game'] },
  { prompt: 'The Buddhist doctrine that there is no permanent self.',
    accept: ['anatta', 'no self', 'non self', 'anatman'] },
  { prompt: 'The view that mind and body are two entirely different substances.',
    accept: ['dualism', 'substance dualism', 'cartesian dualism'] },
  { prompt: 'The view that everything mental is physical brain activity.',
    accept: ['materialism', 'physicalism', 'monism'] },
  { prompt: 'The gland Descartes claimed was where mind meets body.',
    accept: ['the pineal gland', 'pineal gland', 'pineal'] },
  { prompt: 'Avicenna\'s thought experiment: a person suspended in mid-air, senses shrouded.',
    accept: ['the floating man', 'floating man', 'flying man'] },
  { prompt: 'The principle that says prefer the explanation with fewest assumptions.',
    accept: ['ockhams razor', 'occams razor', 'the razor', 'parsimony'] },
  { prompt: 'The Gestalt principle where your brain completes an unfinished shape.',
    accept: ['closure'] },
  { prompt: 'The illusion where a brush and a fake hand convince your brain it is yours.',
    accept: ['the rubber hand illusion', 'rubber hand illusion', 'rubber hand'] },
  { prompt: 'The idea that a mind is defined by what it DOES, not what it is made of.',
    accept: ['functionalism', 'functionalist'] },
  { prompt: 'Plato\'s soul has three parts. Name the one that steers — the charioteer.',
    accept: ['reason', 'the charioteer', 'nous', 'rationality'] },
  { prompt: 'The "E" in PCASTLE.',
    accept: ['evidence'] },
  { prompt: 'The significance criterion asking "how long did the effects last?"',
    accept: ['durability'] },
  { prompt: 'The philosopher who defined consciousness as awareness of your own mind.',
    accept: ['david armstrong', 'armstrong'] },
  { prompt: 'The 2014 chatbot that posed as a 13-year-old Ukrainian boy.',
    accept: ['eugene goostman', 'goostman', 'eugene'] },
  { prompt: 'The test where naming ink colours fights with reading the words.',
    accept: ['the stroop test', 'stroop test', 'stroop'] },
];

export function findRound(roundId) {
  return ROUNDS.find((r) => r.id === roundId) || null;
}

export function findQuestion(questionId) {
  for (const round of ROUNDS) {
    const q = round.questions.find((x) => x.id === questionId);
    if (q) return { round, question: q };
  }
  return null;
}
