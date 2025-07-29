document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("form");

  if (form) {
    form.addEventListener("submit", (e) => {
      const inputs = form.querySelectorAll("input[required]");
      let isValid = true;

      inputs.forEach(input => {
        if (!input.value.trim()) {
          alert(`Please fill out the ${input.name} field.`);
          input.focus();
          isValid = false;
          e.preventDefault();
          return false;
        }
      });

      return isValid;
    });
  }

  console.log("Script loaded.");
});
