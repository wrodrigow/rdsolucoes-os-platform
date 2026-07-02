/* RD Soluções OS — Marketing Site JS */

// ── Mobile Menu ──────────────────────────────────────────────────
const toggle = document.getElementById('nav-toggle');
const mobileMenu = document.getElementById('mobile-menu');
if (toggle && mobileMenu) {
  toggle.addEventListener('click', () => {
    mobileMenu.classList.toggle('open');
    toggle.innerHTML = mobileMenu.classList.contains('open') ? '✕' : '☰';
  });
}

// ── FAQ Accordion ─────────────────────────────────────────────────
document.querySelectorAll('.faq-question').forEach(btn => {
  btn.addEventListener('click', () => {
    const item = btn.closest('.faq-item');
    const isOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
    if (!isOpen) item.classList.add('open');
  });
});

// ── Scroll Animations (Intersection Observer) ─────────────────────
const observerOpts = { threshold: 0.15, rootMargin: '0px 0px -40px 0px' };
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('animate-fade-in-up');
      observer.unobserve(entry.target);
    }
  });
}, observerOpts);

document.querySelectorAll('.feature-card, .step-card, .testimonial-card, .faq-item, .stat-item, .comparison-card').forEach(el => {
  el.style.opacity = '0';
  observer.observe(el);
});

// ── Navbar scroll effect ──────────────────────────────────────────
const navbar = document.querySelector('.navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.style.background = window.scrollY > 60
      ? 'rgba(8,12,20,0.97)'
      : 'rgba(8,12,20,0.85)';
  }, { passive: true });
}

// ── Smooth scroll for anchor links ───────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (mobileMenu) mobileMenu.classList.remove('open');
    }
  });
});

// ── Counter animation ─────────────────────────────────────────────
function animateCounter(el, target, duration = 1500) {
  const start = Date.now();
  const isDecimal = target % 1 !== 0;
  const update = () => {
    const elapsed = Date.now() - start;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const value = target * ease;
    el.textContent = isDecimal
      ? value.toFixed(1).replace('.', ',')
      : Math.round(value).toLocaleString('pt-BR');
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

const counterObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const el = entry.target;
      const val = parseFloat(el.dataset.count);
      if (!isNaN(val)) animateCounter(el, val);
      counterObserver.unobserve(el);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('[data-count]').forEach(el => counterObserver.observe(el));

// ── Auto-dismiss flash messages ───────────────────────────────────
setTimeout(() => {
  document.querySelectorAll('.flash-msg').forEach(el => {
    el.style.transition = 'opacity 0.5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  });
}, 4500);
