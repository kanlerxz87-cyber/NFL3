// Client-side row filter for tables (no external dependencies).
document.querySelectorAll('input.filter').forEach((input) => {
  const table = document.getElementById(input.dataset.target);
  if (!table) return;
  const counter = document.querySelector(`[data-count="${input.dataset.target}"]`);
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    let shown = 0;
    table.tBodies[0].querySelectorAll('tr').forEach((tr) => {
      const hit = !q || tr.textContent.toLowerCase().includes(q);
      tr.style.display = hit ? '' : 'none';
      if (hit) shown++;
    });
    if (counter) counter.textContent = shown;
  });
});
