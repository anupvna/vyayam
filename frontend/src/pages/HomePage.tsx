// Placeholder home screen. Step 1 replaces this with onboarding, then the Today screen.
import { useAuth } from "../auth";

export function HomePage() {
  const { state, logout } = useAuth();
  const email = state.status === "authenticated" ? state.user.email : "";

  return (
    <main className="home">
      <header className="topbar">
        <strong>Vyayam</strong>
        <button className="ghost" onClick={() => void logout()}>
          Log out
        </button>
      </header>

      <section className="card">
        <h2>Welcome 👋</h2>
        <p className="muted">Signed in as {email}</p>
        <p>Next up: set up your profile, goal and gym equipment.</p>
      </section>
    </main>
  );
}
