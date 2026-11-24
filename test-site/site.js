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
  const form = document.getElementById('chapterContactForm');
  if (!form) return;
  const endpoint = 'https://agr-beta-epsilon-submission-api.onrender.com/api/submit';
  const status = document.getElementById('contactFormStatus');
  const submitButton = form.querySelector('button[type="submit"]');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    submitButton.disabled = true;
    submitButton.textContent = 'SUBMITTING…';
    status.textContent = 'Submitting your inquiry securely…';
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          purpose: document.getElementById('inquiryPurpose').value,
          name: document.getElementById('contactName').value.trim(),
          email: document.getElementById('contactEmail').value.trim(),
          message: document.getElementById('contactMessage').value.trim(),
          website: form.querySelector('[name="website"]')?.value || ''
        })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.status !== 'submitted') {
        throw new Error(result.error || 'Your inquiry could not be delivered. Please try again later.');
      }
      status.textContent = result.route === 'recruitment'
        ? 'Thank you. Your recruitment inquiry was received and added to the chapter follow-up list.'
        : 'Thank you. Your inquiry was delivered to the chapter administrator.';
      form.reset();
    } catch (error) {
      status.textContent = error.message || 'The chapter form is temporarily unavailable. Please try again later.';
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = 'SUBMIT →';
    }
  });
})();
