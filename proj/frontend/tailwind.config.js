export default { content: ["./index.html","./src/**/*.{ts,tsx}"], theme: { extend: { colors: {
  primary:"var(--c-primary)", "primary-light":"var(--c-primary-light)", soft:"var(--c-soft)", bg:"var(--c-bg)", card:"var(--c-card)",
  ink:"var(--c-text)", muted:"var(--c-muted)", line:"var(--c-border)", success:"var(--c-success)", warning:"var(--c-warning)", danger:"var(--c-danger)", critical:"var(--c-critical)" },
  fontFamily:{ sans:["Inter","system-ui","sans-serif"] }, boxShadow:{ card:"0 1px 2px rgba(15,23,42,.04),0 8px 24px rgba(37,99,235,.06)" } } } };
