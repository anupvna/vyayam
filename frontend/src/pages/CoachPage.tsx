// Coach: chat about your training. Replies are grounded in your own data, and any
// change the coach suggests is checked by the training engine before it's offered as
// a button (and again when you tap it).
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, api } from "../api";
import { savedMinutes, saveMinutes, sendsOnEnter, suggestions } from "../coach";
import { TabBar } from "../components/TabBar";
import { getStatus, subscribe } from "../offline/status";
import { localISO } from "../plan";
import type { CoachAction, CoachMessage } from "../types";

type DayInfo = { status: "rest" | "planned" | "skipped" };

const touchScreen = () => typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;

export function CoachPage() {
  const today = localISO();
  const [params, setParams] = useSearchParams();
  const { online } = useSyncExternalStore(subscribe, getStatus);
  const [messages, setMessages] = useState<CoachMessage[] | null>(null);
  const [ai, setAi] = useState(true);
  const [trainingDay, setTrainingDay] = useState(true);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; today: boolean } | null>(null);
  const [applying, setApplying] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  useEffect(() => {
    api<CoachMessage[]>("/coach/messages")
      .then(setMessages)
      .catch(() => setMessages([]));
    api<{ ai: boolean }>("/coach/status")
      .then((s) => setAi(s.ai))
      .catch(() => undefined);
    api<DayInfo>(`/plan/today?today=${today}`)
      .then((d) => setTrainingDay(d.status === "planned"))
      .catch(() => undefined);
  }, [today]);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: "end" });
  }, [messages, sending]);

  const send = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q || sending) return;
      setSending(true);
      setError(null);
      setNotice(null);
      try {
        const pair = await api<CoachMessage[]>("/coach/messages", { method: "POST", body: { text: q, today } });
        setMessages((m) => [...(m ?? []), ...pair]);
        setDraft("");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't reach the coach. Try again.");
        setDraft(q);
      } finally {
        setSending(false);
      }
    },
    [sending, today],
  );

  // "Ask why" links from Today arrive as /coach?ask=...: send once, then tidy the URL.
  useEffect(() => {
    const q = params.get("ask");
    if (!q || asked.current || messages === null) return;
    asked.current = true;
    setParams({}, { replace: true });
    void send(q);
  }, [params, setParams, messages, send]);

  async function applyAction(m: CoachMessage, a: CoachAction) {
    setApplying(`${m.id}-${a.index}`);
    setError(null);
    try {
      const res = await api<{ message: string; minutes: number | null }>(
        `/coach/messages/${m.id}/actions/${a.index}`,
        { method: "POST", body: { today } },
      );
      if (res.minutes) saveMinutes(today, res.minutes);
      if (a.type === "restore_today" && savedMinutes(today)) saveMinutes(today, null);
      setMessages((all) =>
        (all ?? []).map((x) =>
          x.id === m.id ? { ...x, actions: x.actions.map((y) => (y.index === a.index ? { ...y, applied: true } : y)) } : x,
        ),
      );
      setNotice({ text: res.message, today: a.type.endsWith("_today") });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't do that. Try again.");
    } finally {
      setApplying(null);
    }
  }

  async function clear() {
    if (!window.confirm("Clear this conversation? The coach will forget it too.")) return;
    try {
      await api("/coach/messages", { method: "DELETE" });
      setMessages([]);
      setNotice(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't clear. Try again.");
    }
  }

  const empty = messages !== null && messages.length === 0;

  return (
    <>
      <main className="page coach-page">
        <header className="page-head">
          <div>
            <p className="greeting">Ask about your training</p>
            <h1>Coach</h1>
          </div>
          {!!messages?.length && (
            <button type="button" className="link small" onClick={clear}>
              Clear
            </button>
          )}
        </header>

        {messages === null && <p className="muted">Loading…</p>}

        {empty && (
          <section className="coach-intro">
            <p>
              I know your plan, your logged sets and your progress. Ask why a target is what it is, or tell me what's
              changed today. Any change I suggest is checked by your training plan before you can apply it.
            </p>
            <p className="muted small">A training aid, not medical advice.</p>
            {!ai && <p className="muted small">AI is off, so answers come from the app's own rules.</p>}
          </section>
        )}

        <ol className="chat" aria-live="polite">
          {messages?.map((m) => (
            <li key={m.id} className={`msg ${m.role} ${m.source === "safety" ? "msg-safety" : ""}`}>
              <p>{m.text}</p>
              {m.role === "coach" && m.source === "engine" && ai && (
                <span className="msg-note">AI unavailable, so this answer is from the app's own rules.</span>
              )}
              {m.actions.length > 0 && (
                <div className="msg-actions">
                  {m.actions.map((a) =>
                    a.applied ? (
                      <span key={a.index} className="action-done">
                        ✓ {a.label}
                      </span>
                    ) : (
                      <button
                        key={a.index}
                        type="button"
                        className="action"
                        disabled={!online || applying !== null}
                        onClick={() => applyAction(m, a)}
                      >
                        {applying === `${m.id}-${a.index}` ? "…" : a.label}
                      </button>
                    ),
                  )}
                </div>
              )}
            </li>
          ))}
          {sending && (
            <li className="msg coach typing" aria-label="Coach is replying">
              <span />
              <span />
              <span />
            </li>
          )}
        </ol>

        {notice && (
          <p className="coach-notice" role="status">
            {notice.text}{" "}
            {notice.today && (
              <Link to="/" className="link small">
                Open Today
              </Link>
            )}
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {empty && (
          <div className="chips" aria-label="Suggested questions">
            {suggestions(trainingDay).map((s) => (
              <button key={s} type="button" className="chip" disabled={!online || sending} onClick={() => void send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
        <div ref={end} className="chat-end" />
      </main>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
      >
        <textarea
          rows={1}
          maxLength={1000}
          value={draft}
          aria-label="Message the coach"
          placeholder={online ? "Ask your coach…" : "The coach needs a connection"}
          disabled={!online}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (sendsOnEnter(e, touchScreen())) {
              e.preventDefault();
              void send(e.currentTarget.value); // not `draft`: it may be a render behind
            }
          }}
        />
        <button type="submit" className="send" aria-label="Send" disabled={!online || sending || !draft.trim()}>
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
      <TabBar />
    </>
  );
}
