// Sign-up password checks (unit-tested). The server enforces the length too; these
// just catch problems before a round trip, and typos before they lock you out.
export const MIN_PASSWORD = 10;

/** What's wrong with a new password, or null when it's fine. */
export function newPasswordProblem(password: string, confirm: string): string | null {
  if (password.length < MIN_PASSWORD) return `Use at least ${MIN_PASSWORD} characters for your password.`;
  if (password !== confirm) return "The passwords don't match.";
  return null;
}

/** Live hint under the confirm field: only once they've started typing it. */
export function confirmHint(password: string, confirm: string): string | null {
  if (!confirm) return null;
  if (password === confirm) return "Passwords match.";
  return password.startsWith(confirm) ? null : "Passwords don't match yet.";
}
