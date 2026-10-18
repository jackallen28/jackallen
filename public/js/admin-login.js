// Staff login page.

import { api, setupPage, announce, esc } from './common.js';

setupPage();
const form = document.getElementById('login');
const message = document.getElementById('message');

const options = await api('/admin/api/login-options').catch(() => ({ mode: 'accounts', hasAccounts: true }));
const accounts = options.mode === 'accounts';
document.querySelectorAll('[data-for="accounts"]').forEach((el) => (el.hidden = !accounts));
if (accounts) {
  document.getElementById('email').required = true;
  document.getElementById('code').required = true;
}
if (!options.hasAccounts) document.getElementById('no-accounts').hidden = false;
else form.hidden = false;
(accounts ? document.getElementById('email') : document.getElementById('password')).focus();

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const button = form.querySelector('button');
  button.disabled = true;
  try {
    await api('/admin/api/login', {
      method: 'POST',
      body: { email: form.email.value, password: form.password.value, code: form.code.value },
    });
    location.reload();
  } catch (err) {
    announce(message, esc(err.message), 'error');
    form.code.value = '';
    (accounts ? form.code : form.password).focus();
  } finally {
    button.disabled = false;
  }
});
