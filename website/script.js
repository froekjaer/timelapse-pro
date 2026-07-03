const header = document.querySelector('[data-header]')

function updateHeader() {
  if (!header) return
  header.classList.toggle('is-scrolled', window.scrollY > 18)
}

updateHeader()
window.addEventListener('scroll', updateHeader, { passive: true })
