/**
 * Report and server-side strings in both activity languages.
 *
 * The teacher picks the report language on the console; the participant app has its
 * own dictionary in public/js/i18n.js because it ships to the browser.
 */

const STRINGS = {
  en: {
    reportTitle: 'Human or Not? — round',
    generated: 'Report generated',
    started: 'Started',
    length: 'Length',
    minutes: 'min',
    targetAiShare: 'Target AI share',
    modelsUsed: 'Models used',
    offlineNote: 'Note: no live API responses were recorded this round — the AI partners used the offline fallback, so these results are not representative of the models.',

    tileParticipants: 'Participants',
    tileWithPeer: 'With a peer',
    tileWithAi: 'With AI',
    tileAnswered: 'Answered',
    tileAccuracy: 'Accuracy',
    tileCost: 'Est. API cost',

    byModel: 'By model',
    byPersona: 'By persona',
    noAi: 'No AI partners in this round.',
    colModel: 'Model',
    colPersona: 'Persona',
    colParticipants: 'Participants',
    colAnswered: 'Answered',
    colBelievedHuman: 'Believed it was human',
    colSpottedAi: 'Identified as AI',
    colFooledRate: 'Fooled rate',
    colBotTurns: 'Bot turns',
    colTokens: 'Tokens in / out',
    colCost: 'Est. cost',
    colMessages: 'Messages',
    foolNote: 'Fooled rate is the share of participants facing that model who believed they were talking to a person. Higher means more convincing.',

    byPartnerType: 'Accuracy by partner type',
    colPartner: 'Partner',
    realPerson: 'A real person',
    aiBot: 'AI',
    colCorrect: 'Correct',

    participants: 'Participants',
    colParticipant: 'Participant',
    colPairedWith: 'Paired with',
    colTheirAnswer: 'Their answer',
    colResult: 'Result',
    answerPeer: 'A person',
    answerAi: 'AI',
    noAnswer: 'no answer',
    correct: 'Correct',
    wrong: 'Wrong',
    peer: 'Peer',

    transcripts: 'Transcripts',
    noConversations: 'No conversations recorded.',
    noMessages: 'No messages were sent.',
    talkedTo: 'with',
    persona: 'persona',
    botTurns: 'bot turns',
    tokens: 'tokens',
    languageLabel: 'Language',
    translatedNote: 'Messages between participants who chose different languages were translated automatically. The text below is what each person actually sent.',
  },

  zh: {
    reportTitle: '人类还是机器？— 第',
    generated: '报告生成时间',
    started: '开始时间',
    length: '时长',
    minutes: '分钟',
    targetAiShare: '配对 AI 的比例',
    modelsUsed: '使用的模型',
    offlineNote: '注意：本轮未记录到任何实时 API 回复，AI 伙伴使用的是离线备用回复，因此结果不能代表这些模型的真实表现。',

    tileParticipants: '参与人数',
    tileWithPeer: '与真人配对',
    tileWithAi: '与 AI 配对',
    tileAnswered: '已作答',
    tileAccuracy: '正确率',
    tileCost: '预计 API 费用',

    byModel: '按模型统计',
    byPersona: '按人物设定统计',
    noAi: '本轮没有 AI 伙伴。',
    colModel: '模型',
    colPersona: '人物设定',
    colParticipants: '参与人数',
    colAnswered: '已作答',
    colBelievedHuman: '认为是真人',
    colSpottedAi: '识别出是 AI',
    colFooledRate: '被误认为真人的比例',
    colBotTurns: 'AI 回复次数',
    colTokens: '输入 / 输出词元',
    colCost: '预计费用',
    colMessages: '消息数',
    foolNote: '「被误认为真人的比例」指与该模型对话的参与者中，认为对方是真人的比例。比例越高，说明该模型越有说服力。',

    byPartnerType: '按伙伴类型统计正确率',
    colPartner: '伙伴',
    realPerson: '真人',
    aiBot: 'AI',
    colCorrect: '正确',

    participants: '参与者',
    colParticipant: '参与者',
    colPairedWith: '配对对象',
    colTheirAnswer: '其判断',
    colResult: '结果',
    answerPeer: '真人',
    answerAi: 'AI',
    noAnswer: '未作答',
    correct: '正确',
    wrong: '错误',
    peer: '真人',

    transcripts: '对话记录',
    noConversations: '没有对话记录。',
    noMessages: '没有发送任何消息。',
    talkedTo: '与',
    persona: '人物设定',
    botTurns: '次 AI 回复',
    tokens: '词元',
    languageLabel: '语言',
    translatedNote: '选择了不同语言的参与者之间的消息会自动翻译。下方显示的是每个人实际发送的原文。',
  },
};

export const REPORT_LANGUAGES = Object.keys(STRINGS);

/** A lookup bound to one language, falling back to English for any missing key. */
export function strings(lang) {
  const table = STRINGS[lang] || STRINGS.en;
  return (key) => table[key] ?? STRINGS.en[key] ?? key;
}
