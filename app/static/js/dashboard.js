(() => {
  const buttons = document.querySelectorAll("[data-copy-target]");

  buttons.forEach((button) => {
    button.addEventListener("click", async () => {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) {
        return;
      }

      const original = button.textContent;
      try {
        await navigator.clipboard.writeText(target.textContent || "");
        button.textContent = "Copied";
        button.classList.add("is-copied");
      } catch {
        button.textContent = "Copy failed";
      }

      window.setTimeout(() => {
        button.textContent = original;
        button.classList.remove("is-copied");
      }, 1600);
    });
  });
})();
