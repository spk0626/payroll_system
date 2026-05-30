/**
 * main.js — Syntax Asia Salary System
 *
 * Deliberately minimal. No framework. Vanilla JS only.
 * Each function is small, focused, and independently readable.
 */

'use strict';

/**
 * Toggle a password input between visible and masked.
 *
 * @param {string} inputId - The id of the password <input>.
 * @param {HTMLButtonElement} btn - The toggle button element.
 */
function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;

  const isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';

  // Swap the eye / eye-off SVG icons
  const eyeIcon    = document.getElementById('icon-eye-' + inputId);
  const eyeOffIcon = document.getElementById('icon-eye-off-' + inputId);
  if (eyeIcon)    eyeIcon.style.display    = isHidden ? 'none' : '';
  if (eyeOffIcon) eyeOffIcon.style.display = isHidden ? '' : 'none';

  btn.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');
  btn.setAttribute('title',      isHidden ? 'Hide password' : 'Show password');
}

/**
 * Auto-dismiss flash messages after 6 seconds.
 * Users can still close them manually via the × button.
 */
(function autoDismissMessages() {
  const messages = document.querySelectorAll('.message');
  messages.forEach(function(msg) {
    setTimeout(function() {
      msg.style.transition = 'opacity 400ms ease';
      msg.style.opacity = '0';
      setTimeout(function() { msg.remove(); }, 420);
    }, 6000);
  });
})();