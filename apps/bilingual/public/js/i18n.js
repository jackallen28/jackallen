/**
 * UI strings for both activity languages.
 *
 * Elements carry data-i18n="key" and are filled by applyLanguage(). Anything set
 * from script asks t(key) directly.
 */
window.HON_I18N = (() => {
  const STRINGS = {
    en: {
      // language gate
      chooseLanguage: 'Choose your language',
      chooseLanguageSub: 'The whole activity, including the chat, will be in the language you pick.',
      continueBtn: 'Continue',

      // sign in
      appTitle: 'Human or Not?',
      signinLead: 'Enter the login on the card you were given.',
      loginLabel: 'Your login — four letters, then four numbers',
      joinBtn: 'Join',
      changeLanguage: 'Change language',
      errFormat: 'Four letters then four numbers, like WXYZ1234.',
      errReset: 'The facilitator reset the activity. Wait for the next round.',
      errRemoved: 'You were removed from the room.',

      // conduct
      rulesTitle: 'Before you start',
      rule1: 'You might be talking to <strong>a colleague</strong> or to <strong>an AI</strong>. You will not be told which.',
      rule2: 'Be respectful. If you would not say it out loud in the room, do not type it.',
      rule3: '<strong>Never share personal information.</strong> No real names, no workplace, no address, no phone number, no socials.',
      rule4: 'Everything you type is recorded, and the facilitator can read all of it.',

      // waiting
      youreIn: "You're in",
      youAre: 'You are',
      waitingBody: 'Waiting for the facilitator to start the round.',
      inRoom: 'in the room',

      // late
      lateTitle: 'Round in progress',
      lateBody: 'You joined after this round started, so you are sitting this one out. Hang tight for the next round.',

      // chat
      someone: 'Someone',
      chatSub: 'A colleague or an AI? No personal information.',
      saySomething: 'Say something…',
      sendBtn: 'Send',

      // guess
      timesUp: "Time's up",
      guessBody: 'Who were you just chatting with?',
      guessHuman: '🧑 A person',
      guessAi: '🤖 An AI',

      // reveal
      revealRight: 'You got it right',
      revealWrong: 'Not this time',
      wasAi: 'You were chatting with <strong>an AI</strong>.',
      wasHuman: 'You were chatting with <strong>a real person</strong>.',
      youGuessed: 'You guessed',
      guessedAi: 'AI',
      guessedHuman: 'a person',
      waitForResults: 'The facilitator will show the class results shortly.',

      // class summary
      summaryTitle: 'How the room did',
      summarySub: 'Everyone together. No individual results are shown.',
      sumParticipants: 'Took part',
      sumCorrect: 'Identified correctly',
      sumVsAi: 'Right about the AI',
      sumVsPeer: 'Right about people',
      ofAnswered: 'of those who answered',

      // teacher console extras
      reportLanguage: 'Report language',
    },

    zh: {
      chooseLanguage: '选择你的语言',
      chooseLanguageSub: '整个活动，包括聊天，都将使用你选择的语言。',
      continueBtn: '继续',

      appTitle: '人类还是机器？',
      signinLead: '请输入卡片上的登录码。',
      loginLabel: '你的登录码 — 四个字母，然后四个数字',
      joinBtn: '加入',
      changeLanguage: '更改语言',
      errFormat: '四个字母加四个数字，例如 WXYZ1234。',
      errReset: '主持人重置了活动，请等待下一轮。',
      errRemoved: '你已被移出房间。',

      rulesTitle: '开始之前',
      rule1: '你的聊天对象可能是<strong>一位同事</strong>，也可能是<strong>一个 AI</strong>。系统不会告诉你是哪一个。',
      rule2: '请保持尊重。在现场不会说出口的话，这里也不要打出来。',
      rule3: '<strong>切勿分享个人信息。</strong>不要提供真实姓名、工作单位、住址、电话号码或社交账号。',
      rule4: '你输入的所有内容都会被记录，主持人可以查看全部内容。',

      youreIn: '你已加入',
      youAre: '你是',
      waitingBody: '请等待主持人开始本轮活动。',
      inRoom: '人在房间里',

      lateTitle: '本轮已开始',
      lateBody: '你是在本轮开始之后加入的，所以这一轮你先休息。请稍等下一轮。',

      someone: '某人',
      chatSub: '是同事还是 AI？请勿透露个人信息。',
      saySomething: '说点什么……',
      sendBtn: '发送',

      timesUp: '时间到',
      guessBody: '你刚才在和谁聊天？',
      guessHuman: '🧑 真人',
      guessAi: '🤖 AI',

      revealRight: '你猜对了',
      revealWrong: '这次没猜对',
      wasAi: '你刚才在和<strong>一个 AI</strong> 聊天。',
      wasHuman: '你刚才在和<strong>一位真人</strong>聊天。',
      youGuessed: '你的判断是',
      guessedAi: 'AI',
      guessedHuman: '真人',
      waitForResults: '主持人稍后会展示全班结果。',

      summaryTitle: '全场结果',
      summarySub: '这是所有人的汇总，不显示任何个人结果。',
      sumParticipants: '参与人数',
      sumCorrect: '判断正确',
      sumVsAi: '正确识别出 AI',
      sumVsPeer: '正确识别出真人',
      ofAnswered: '在已作答的人中',

      reportLanguage: '报告语言',
    },
  };

  let current = 'en';

  function t(key) {
    const table = STRINGS[current] || STRINGS.en;
    return table[key] ?? STRINGS.en[key] ?? key;
  }

  /** Fill every [data-i18n] element on the page and set the document language. */
  function applyLanguage(lang) {
    current = STRINGS[lang] ? lang : 'en';
    document.documentElement.lang = current === 'zh' ? 'zh-CN' : 'en';
    document.documentElement.classList.toggle('lang-zh', current === 'zh');

    for (const el of document.querySelectorAll('[data-i18n]')) {
      el.innerHTML = t(el.dataset.i18n);
    }
    for (const el of document.querySelectorAll('[data-i18n-placeholder]')) {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    }
    return current;
  }

  return { t, applyLanguage, get current() { return current; }, languages: Object.keys(STRINGS) };
})();
