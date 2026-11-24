(function () {
  const toggle = document.getElementById('navToggle');
  const nav = document.getElementById('mainNav');
  const groups = [...document.querySelectorAll('.nav-dropdown')];
  if (toggle && nav) toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  groups.forEach(group => {
    const btn = group.querySelector('button');
    btn.addEventListener('click', () => {
      const next = !group.classList.contains('open');
      groups.forEach(g => {g.classList.remove('open');g.querySelector('button').setAttribute('aria-expanded','false');});
      group.classList.toggle('open', next);
      btn.setAttribute('aria-expanded', String(next));
    });
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.nav-dropdown')) groups.forEach(g => {
      g.classList.remove('open'); g.querySelector('button').setAttribute('aria-expanded','false');
    });
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') groups.forEach(g => {g.classList.remove('open');g.querySelector('button').setAttribute('aria-expanded','false');});
  });
  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());
})();

(function () {
  const endpoint = 'https://agr-beta-epsilon-submission-api.onrender.com/api/submit';
  async function send(form, status, payload, button, originalLabel, successMessage) {
    if (!form.reportValidity()) return;
    button.disabled = true;
    button.textContent = 'SUBMITTING…';
    status.textContent = 'Submitting securely…';
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({...payload, website: form.querySelector('[name="website"]')?.value || ''})
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.status !== 'submitted')
        throw new Error(result.error || 'Your request could not be recorded. Please try again.');
      status.textContent = successMessage;
      form.reset();
    } catch (error) {
      status.textContent = error.message || 'Your request could not be recorded. Please try again.';
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }
  const contact = document.getElementById('chapterContactForm');
  if (contact) contact.addEventListener('submit', event => {
    event.preventDefault();
    send(contact, document.getElementById('contactFormStatus'), {
      purpose: document.getElementById('inquiryPurpose').value,
      name: document.getElementById('contactName').value.trim(),
      email: document.getElementById('contactEmail').value.trim(),
      message: document.getElementById('contactMessage').value.trim()
    }, contact.querySelector('button[type="submit"]'), 'SUBMIT →',
    'Thank you. Your question was saved to the chapter follow-up list.');
  });
  const member = document.getElementById('memberRequestForm');
  if (member) member.addEventListener('submit', event => {
    event.preventDefault();
    send(member, document.getElementById('memberFormStatus'), {
      purpose: 'Member Account Request',
      name: document.getElementById('memberName').value.trim(),
      email: document.getElementById('memberEmail').value.trim(),
      address: document.getElementById('memberAddress').value.trim(),
      phone: document.getElementById('memberPhone').value.trim()
    }, member.querySelector('button[type="submit"]'), 'SUBMIT MEMBER REQUEST →',
    'Your member account request has been recorded and sent to the chapter administrator for review. Access is not granted until approved.');
  });
})();
