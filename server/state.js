import { EventEmitter } from 'node:events';
import { buildConversations } from './pairing.js';
import { botReply, typingDelayMs } from './bot.js';
import { estimateCost, modelLabel, normaliseMix } from './models.js';
import { isKnownPersona, personaCatalog, personaLabel } from './classroom.js';

export const PHASES = {
  LOBBY: 'lobby',     // students joining, waiting for the teacher
  ACTIVE: 'active',   // the chat window is open and the clock is running
  GUESS: 'guess',     // time is up, students are voting human vs AI
  RESULTS: 'results', // everyone has voted (or the teacher moved on)
};

const MAX_MESSAGE_LENGTH = 300;
const MIN_MESSAGE_INTERVAL_MS = 400;
const MAX_MESSAGES_PER_STUDENT = 120;
const BOT_OPENERS = ['hey', 'hi', 'yo', 'hey hey', 'sup'];

/** A single classroom run. One instance per server process. */
export class Session extends EventEmitter {
  constructor() {
    super();
    this.phase = PHASES.LOBBY;
    this.students = new Map();      // code -> student record
    this.conversations = new Map(); // convId -> conversation record
    this.roundNumber = 0;
    this.durationSec = 120;
    this.aiRatio = 0.5;
    this.modelMix = normaliseMix(null);
    this.personaMix = defaultPersonaMix();
    this.startedAt = null;
    this.endedAt = null;
    this.endsAt = null;
    this.roundTimer = null;
    this.usedLiveBot = false;
  }

  // ---------------------------------------------------------------- students

  /** Join or reconnect. Returns {ok, error?}. */
  join(code, socketId) {
    if (!/^\d{6}$/.test(code)) {
      return { ok: false, error: 'Enter a 6-digit number.' };
    }

    const existing = this.students.get(code);
    if (existing) {
      // Treat a repeat join as a reconnect (refresh, dropped wifi, new tab).
      existing.socketId = socketId;
      existing.connected = true;
      this.emit('roster');
      return { ok: true, reconnected: true };
    }

    this.students.set(code, {
      code,
      socketId,
      connected: true,
      joinedAt: Date.now(),
      convId: null,
      guess: null,
      guessedAt: null,
      sent: 0,
      lastSentAt: 0,
    });
    this.emit('roster');
    return { ok: true, reconnected: false };
  }

  /** Mark a student offline without dropping their round data. */
  disconnect(socketId) {
    for (const student of this.students.values()) {
      if (student.socketId === socketId) {
        student.connected = false;
        student.socketId = null;
        this.emit('roster');
        return student.code;
      }
    }
    return null;
  }

  /** Remove a student entirely (teacher action). */
  remove(code) {
    const student = this.students.get(code);
    if (!student) return false;
    if (student.convId) {
      const conv = this.conversations.get(student.convId);
      if (conv) conv.members = conv.members.filter((m) => m !== code);
    }
    this.students.delete(code);
    this.emit('roster');
    return true;
  }

  getByCode(code) {
    return this.students.get(code) || null;
  }

  codeForSocket(socketId) {
    for (const student of this.students.values()) {
      if (student.socketId === socketId) return student.code;
    }
    return null;
  }

  // ------------------------------------------------------------------- round

  /** Pair everyone currently in the lobby and start the clock. */
  start({ durationSec = 120, aiRatio = 0.5, modelMix = null, personaMix = null } = {}) {
    if (this.phase === PHASES.ACTIVE) {
      return { ok: false, error: 'A round is already running.' };
    }
    const codes = [...this.students.keys()];
    if (codes.length === 0) {
      return { ok: false, error: 'No students have joined yet.' };
    }

    this.clearTimers();
    this.durationSec = Math.max(15, Math.min(900, Math.round(durationSec)));
    this.aiRatio = Math.max(0, Math.min(1, aiRatio));
    // Unknown model ids are dropped here, so the browser can never choose the spend.
    this.modelMix = normaliseMix(modelMix);
    this.personaMix = normalisePersonaMix(personaMix);
    this.roundNumber += 1;
    this.usedLiveBot = false;
    this.conversations.clear();

    for (const student of this.students.values()) {
      student.convId = null;
      student.guess = null;
      student.guessedAt = null;
      student.sent = 0;
      student.lastSentAt = 0;
    }

    for (const spec of buildConversations(codes, this.aiRatio, this.modelMix, this.personaMix)) {
      const conv = {
        ...spec,
        messages: [],
        botTurns: 0,
        liveTurns: 0,
        tokensIn: 0,
        tokensOut: 0,
        botBusy: false,
        botAgain: false,
        botTimer: null,
        replyTimer: null,
        openerTimer: null,
      };
      this.conversations.set(conv.id, conv);
      for (const code of conv.members) {
        const student = this.students.get(code);
        if (student) student.convId = conv.id;
      }
    }

    this.phase = PHASES.ACTIVE;
    this.startedAt = Date.now();
    this.endedAt = null;
    this.endsAt = Date.now() + this.durationSec * 1000;
    this.roundTimer = setTimeout(() => this.endRound(), this.durationSec * 1000);

    // Bots open the conversation if the student hasn't said anything yet, so
    // nobody sits in front of a silent window.
    for (const conv of this.conversations.values()) {
      if (conv.type !== 'ai') continue;
      conv.openerTimer = setTimeout(() => {
        if (this.phase !== PHASES.ACTIVE || conv.messages.length > 0) return;
        const opener = BOT_OPENERS[Math.floor(Math.random() * BOT_OPENERS.length)];
        this.deliverBotMessage(conv, opener);
      }, 2500 + Math.random() * 5000);
    }

    this.emit('phase');
    this.emit('roster');
    return { ok: true };
  }

  /** Time is up: freeze the chats and move students to the guess screen. */
  endRound() {
    if (this.phase !== PHASES.ACTIVE) return { ok: false, error: 'No round running.' };
    this.clearTimers();
    this.phase = PHASES.GUESS;
    this.endedAt = Date.now();
    this.endsAt = null;
    this.emit('phase');
    return { ok: true };
  }

  /** Close voting and show the reveal. */
  showResults() {
    if (this.phase === PHASES.LOBBY) return { ok: false, error: 'No round to reveal.' };
    this.clearTimers();
    this.phase = PHASES.RESULTS;
    this.endsAt = null;
    this.emit('phase');
    return { ok: true };
  }

  /**
   * Back to the lobby.
   * @param {boolean} keepStudents  keep the roster for another round
   */
  reset({ keepStudents = true } = {}) {
    this.clearTimers();
    this.conversations.clear();
    this.phase = PHASES.LOBBY;
    this.endsAt = null;

    if (keepStudents) {
      for (const student of this.students.values()) {
        student.convId = null;
        student.guess = null;
        student.guessedAt = null;
        student.sent = 0;
        student.lastSentAt = 0;
      }
    } else {
      this.students.clear();
    }

    this.emit('phase');
    this.emit('roster');
    return { ok: true };
  }

  clearTimers() {
    if (this.roundTimer) clearTimeout(this.roundTimer);
    this.roundTimer = null;
    for (const conv of this.conversations.values()) {
      for (const key of ['botTimer', 'replyTimer', 'openerTimer']) {
        if (conv[key]) clearTimeout(conv[key]);
        conv[key] = null;
      }
      conv.botBusy = false;
      conv.botAgain = false;
    }
  }

  // ----------------------------------------------------------------- chatting

  /** Handle an inbound student message. Returns {ok, error?}. */
  sendMessage(code, rawText) {
    if (this.phase !== PHASES.ACTIVE) return { ok: false, error: 'The chat is closed.' };

    const student = this.students.get(code);
    if (!student || !student.convId) return { ok: false, error: 'You are not in this round.' };

    const text = String(rawText || '').replace(/\s+/g, ' ').trim().slice(0, MAX_MESSAGE_LENGTH);
    if (!text) return { ok: false, error: 'Empty message.' };

    const now = Date.now();
    if (now - student.lastSentAt < MIN_MESSAGE_INTERVAL_MS) {
      return { ok: false, error: 'Slow down a little.' };
    }
    if (student.sent >= MAX_MESSAGES_PER_STUDENT) {
      return { ok: false, error: 'Message limit reached.' };
    }
    student.lastSentAt = now;
    student.sent += 1;

    const conv = this.conversations.get(student.convId);
    if (!conv) return { ok: false, error: 'Conversation not found.' };

    const message = { sender: code, text, ts: now };
    conv.messages.push(message);
    this.fanOut(conv, message);

    if (conv.type === 'ai') this.scheduleBotTurn(conv);
    this.emit('roster');
    return { ok: true };
  }

  /** Relay a typing indicator to the human partner only. */
  setTyping(code, isTyping) {
    if (this.phase !== PHASES.ACTIVE) return;
    const student = this.students.get(code);
    if (!student || !student.convId) return;
    const conv = this.conversations.get(student.convId);
    if (!conv || conv.type !== 'human') return;
    for (const member of conv.members) {
      if (member !== code) this.emit('typing', member, Boolean(isTyping));
    }
  }

  /** Push a message to everyone in a conversation, from each one's point of view. */
  fanOut(conv, message) {
    for (const member of conv.members) {
      this.emit('message', member, {
        mine: message.sender === member,
        text: message.text,
        ts: message.ts,
      });
    }
  }

  // --------------------------------------------------------------------- bot

  scheduleBotTurn(conv) {
    if (conv.openerTimer) {
      clearTimeout(conv.openerTimer);
      conv.openerTimer = null;
    }
    if (conv.botBusy) {
      conv.botAgain = true;
      return;
    }
    if (conv.botTimer) clearTimeout(conv.botTimer);
    // Short settle window so a burst of quick messages gets one reply, not three.
    conv.botTimer = setTimeout(() => this.runBotTurn(conv), 900 + Math.random() * 800);
  }

  /** Convert stored messages into alternating API turns. */
  historyFor(conv) {
    const history = [];
    for (const message of conv.messages) {
      const role = message.sender === 'bot' ? 'assistant' : 'user';
      const last = history[history.length - 1];
      if (last && last.role === role) last.content += `\n${message.text}`;
      else history.push({ role, content: message.text });
    }
    // The API needs the exchange to open on a user turn.
    while (history.length && history[0].role === 'assistant') history.shift();
    return history;
  }

  async runBotTurn(conv) {
    if (this.phase !== PHASES.ACTIVE) return;
    conv.botTimer = null;
    conv.botBusy = true;
    conv.botAgain = false;

    try {
      const history = this.historyFor(conv);
      if (history.length === 0) return;

      this.emitTypingToMembers(conv, true);
      const { text, live, usage } = await botReply(history, conv.model, conv.persona);
      if (this.phase !== PHASES.ACTIVE) return;
      conv.botTurns += 1;
      conv.tokensIn += usage?.inputTokens || 0;
      conv.tokensOut += usage?.outputTokens || 0;
      if (live) {
        conv.liveTurns += 1;
        this.usedLiveBot = true;
      }

      await new Promise((resolve) => {
        conv.replyTimer = setTimeout(resolve, typingDelayMs(text));
      });
      if (this.phase !== PHASES.ACTIVE) return;

      this.deliverBotMessage(conv, text);
    } catch (err) {
      console.warn('[state] bot turn failed:', err.message);
    } finally {
      this.emitTypingToMembers(conv, false);
      conv.botBusy = false;
      conv.replyTimer = null;
      const last = conv.messages[conv.messages.length - 1];
      if (conv.botAgain && last && last.sender !== 'bot' && this.phase === PHASES.ACTIVE) {
        this.scheduleBotTurn(conv);
      }
    }
  }

  deliverBotMessage(conv, text) {
    const message = { sender: 'bot', text, ts: Date.now() };
    conv.messages.push(message);
    this.fanOut(conv, message);
  }

  emitTypingToMembers(conv, isTyping) {
    for (const member of conv.members) this.emit('typing', member, isTyping);
  }

  // ------------------------------------------------------------------ guesses

  submitGuess(code, guess) {
    if (this.phase !== PHASES.GUESS && this.phase !== PHASES.RESULTS) {
      return { ok: false, error: 'Not time to guess yet.' };
    }
    if (guess !== 'human' && guess !== 'ai') {
      return { ok: false, error: 'Pick human or AI.' };
    }
    const student = this.students.get(code);
    if (!student || !student.convId) return { ok: false, error: 'You were not in this round.' };
    if (student.guess) return { ok: false, error: 'You have already answered.' };

    student.guess = guess;
    student.guessedAt = Date.now();
    this.emit('roster');
    return { ok: true };
  }

  // -------------------------------------------------------------------- views

  /** What one student's screen needs. */
  studentView(code) {
    const student = this.students.get(code);
    if (!student) return { phase: 'signin' };

    const conv = student.convId ? this.conversations.get(student.convId) : null;
    const inRound = Boolean(conv);

    const view = {
      phase: this.phase,
      code,
      inRound,
      roundNumber: this.roundNumber,
      endsAt: this.endsAt,
      durationSec: this.durationSec,
      waitingCount: this.students.size,
      guess: student.guess,
      transcript: conv
        ? conv.messages.map((m) => ({ mine: m.sender === code, text: m.text, ts: m.ts }))
        : [],
    };

    // The answer is only ever sent once the student has locked in a guess.
    if (conv && student.guess && (this.phase === PHASES.GUESS || this.phase === PHASES.RESULTS)) {
      view.reveal = {
        partnerType: conv.type,
        correct: student.guess === conv.type,
      };
    }
    return view;
  }

  /** What the teacher dashboard needs. */
  teacherView() {
    const students = [...this.students.values()]
      .sort((a, b) => a.code.localeCompare(b.code))
      .map((student) => {
        const conv = student.convId ? this.conversations.get(student.convId) : null;
        const partner = conv
          ? conv.type === 'ai'
            ? modelLabel(conv.model)
            : conv.members.find((m) => m !== student.code) || 'unpaired'
          : null;
        return {
          code: student.code,
          connected: student.connected,
          joinedAt: student.joinedAt,
          inRound: Boolean(conv),
          partnerType: conv ? conv.type : null,
          model: conv && conv.type === 'ai' ? conv.model : null,
          modelLabel: conv && conv.type === 'ai' ? modelLabel(conv.model) : null,
          persona: conv && conv.type === 'ai' ? conv.persona : null,
          personaLabel: conv && conv.type === 'ai' && conv.persona
            ? `${conv.persona} — ${personaLabel(conv.persona)}`
            : null,
          partner,
          messagesSent: student.sent,
          guess: student.guess,
          correct: conv && student.guess ? student.guess === conv.type : null,
        };
      });

    const inRound = students.filter((s) => s.inRound);
    const answered = inRound.filter((s) => s.guess);
    const correct = answered.filter((s) => s.correct);
    const humanSide = answered.filter((s) => s.partnerType === 'human');
    const aiSide = answered.filter((s) => s.partnerType === 'ai');

    return {
      phase: this.phase,
      roundNumber: this.roundNumber,
      endsAt: this.endsAt,
      durationSec: this.durationSec,
      aiRatio: this.aiRatio,
      modelMix: this.modelMix,
      personaMix: this.personaMix,
      usedLiveBot: this.usedLiveBot,
      students,
      byModel: this.modelBreakdown(),
      byPersona: this.personaBreakdown(),
      stats: {
        joined: students.length,
        connected: students.filter((s) => s.connected).length,
        paired: inRound.length,
        withAi: inRound.filter((s) => s.partnerType === 'ai').length,
        withHuman: inRound.filter((s) => s.partnerType === 'human').length,
        answered: answered.length,
        correct: correct.length,
        accuracy: answered.length ? Math.round((correct.length / answered.length) * 100) : null,
        humanAccuracy: humanSide.length
          ? Math.round((humanSide.filter((s) => s.correct).length / humanSide.length) * 100)
          : null,
        aiAccuracy: aiSide.length
          ? Math.round((aiSide.filter((s) => s.correct).length / aiSide.length) * 100)
          : null,
      },
    };
  }

  /**
   * Per-model results.
   *
   * The headline number for a teacher is `foolRate`: of the students who faced
   * this model and answered, how many believed it was a classmate.
   */
  modelBreakdown() {
    const rows = new Map();

    for (const conv of this.conversations.values()) {
      if (conv.type !== 'ai') continue;
      const id = conv.model || 'unknown';
      if (!rows.has(id)) {
        rows.set(id, {
          id,
          label: modelLabel(id),
          students: 0,
          answered: 0,
          caught: 0,
          fooled: 0,
          studentMessages: 0,
          botTurns: 0,
          liveTurns: 0,
          tokensIn: 0,
          tokensOut: 0,
        });
      }
      const row = rows.get(id);
      row.tokensIn += conv.tokensIn;
      row.tokensOut += conv.tokensOut;
      row.botTurns += conv.botTurns;
      row.liveTurns += conv.liveTurns;

      for (const code of conv.members) {
        const student = this.students.get(code);
        if (!student) continue;
        row.students += 1;
        row.studentMessages += student.sent;
        if (student.guess) {
          row.answered += 1;
          if (student.guess === 'ai') row.caught += 1;
          else row.fooled += 1;
        }
      }
    }

    return [...rows.values()].map((row) => ({
      ...row,
      foolRate: row.answered ? Math.round((row.fooled / row.answered) * 100) : null,
      costUsd: Number(estimateCost(row.id, row.tokensIn, row.tokensOut).toFixed(4)),
    }));
  }

  /**
   * Per-persona results, the same shape as the model breakdown. Which persona
   * survived contact with the class is the question the pack is built around.
   */
  personaBreakdown() {
    const rows = new Map();

    for (const conv of this.conversations.values()) {
      if (conv.type !== 'ai' || !conv.persona) continue;
      const id = conv.persona;
      if (!rows.has(id)) {
        rows.set(id, {
          id,
          label: personaLabel(id),
          students: 0,
          answered: 0,
          caught: 0,
          fooled: 0,
          studentMessages: 0,
          botTurns: 0,
        });
      }
      const row = rows.get(id);
      row.botTurns += conv.botTurns;

      for (const code of conv.members) {
        const student = this.students.get(code);
        if (!student) continue;
        row.students += 1;
        row.studentMessages += student.sent;
        if (student.guess) {
          row.answered += 1;
          if (student.guess === 'ai') row.caught += 1;
          else row.fooled += 1;
        }
      }
    }

    return [...rows.values()].map((row) => ({
      ...row,
      foolRate: row.answered ? Math.round((row.fooled / row.answered) * 100) : null,
    }));
  }

  /** Full transcripts, for the teacher to review after the reveal. */
  transcripts() {
    return [...this.conversations.values()].map((conv) => ({
      id: conv.id,
      type: conv.type,
      model: conv.model || null,
      persona: conv.persona || null,
      personaLabel: conv.persona ? `${conv.persona} — ${personaLabel(conv.persona)}` : null,
      modelLabel: conv.type === 'ai' ? modelLabel(conv.model) : null,
      members: conv.members,
      botTurns: conv.botTurns,
      liveTurns: conv.liveTurns,
      tokensIn: conv.tokensIn,
      tokensOut: conv.tokensOut,
      messages: conv.messages.map((m) => ({
        sender: m.sender === 'bot' ? modelLabel(conv.model) : m.sender,
        isBot: m.sender === 'bot',
        text: m.text,
        ts: m.ts,
      })),
    }));
  }

  /** Everything the downloadable teacher report needs, in one object. */
  reportData() {
    const view = this.teacherView();
    return {
      generatedAt: Date.now(),
      roundNumber: this.roundNumber,
      durationSec: this.durationSec,
      startedAt: this.startedAt,
      endedAt: this.endedAt,
      aiRatio: this.aiRatio,
      modelMix: this.modelMix,
      personaMix: this.personaMix,
      usedLiveBot: this.usedLiveBot,
      stats: view.stats,
      byModel: view.byModel,
      byPersona: view.byPersona,
      students: view.students,
      transcripts: this.transcripts(),
    };
  }
}


/** All personas from the pack, equally weighted. */
export function defaultPersonaMix() {
  const mix = {};
  for (const persona of personaCatalog) mix[persona.id] = 1;
  return mix;
}

/** Drop anything the pack does not define, and fall back to all of them. */
export function normalisePersonaMix(mix) {
  const cleaned = {};
  for (const [id, weight] of Object.entries(mix || {})) {
    const value = Number(weight);
    if (isKnownPersona(id) && Number.isFinite(value) && value > 0) cleaned[id] = value;
  }
  return Object.keys(cleaned).length ? cleaned : defaultPersonaMix();
}
