"""The coach without AI: rule-based answers from the engine's own data.

Used when no provider is configured or every provider fails, so the coach still
answers the common questions (targets, today's plan, shorten, skip, swap, replace an
exercise, progress, goal timeline) and proposes the same checked actions.
"""

import re

from app.coach.actions import Action
from app.coach.context import CoachContext
from app.engine.alternatives import find_alternatives
from app.library import Exercise, load_library

_GENERIC = {"barbell", "dumbbell", "dumbbells", "cable", "machine", "the", "a", "of", "with"}


def _words(text: str) -> set[str]:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return words | {w[:-1] for w in words if w.endswith("s") and len(w) > 3}


def find_exercise(message: str, ctx: CoachContext) -> Exercise | None:
    """The exercise the user names, preferring ones in today's plan and fuller matches."""
    words = _words(message)
    raw = re.findall(r"[a-z]+", message.lower())
    singular = [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in raw]
    text = " " + " ".join(raw) + " " + " | " + " ".join(singular) + " "
    best: tuple[tuple, Exercise] | None = None
    for ex in load_library().values():
        name = re.sub(r"\(.*?\)", "", ex.name.lower())
        tokens = [t for t in re.findall(r"[a-z]+", name) if t not in _GENERIC]
        exact = f" {' '.join(re.findall(r'[a-z]+', name))} " in text
        if not tokens or not (exact or all(t in words for t in tokens)):
            continue
        score = (exact, ex.id in ctx.today.exercise_ids, len(tokens), -len(name))
        if best is None or score > best[0]:
            best = (score, ex)
    if best:
        return best[1]
    # Loose match ("my squat"): a word from the name of an exercise this person does.
    yours = [e["name"] for e in ctx.data["today_plan"]["exercises"]] + [
        x["exercise"] for x in ctx.data["strength"]
    ]
    by_name = {ex.name: ex for ex in load_library().values()}
    for name in yours:
        tokens = [
            t for t in re.findall(r"[a-z]+", name.lower()) if t not in _GENERIC and len(t) > 3
        ]
        if any(t in words for t in tokens) and name in by_name:
            return by_name[name]
    return None


def _has(pattern: str, message: str) -> bool:
    return re.search(pattern, message, re.IGNORECASE) is not None


_SESSION_WORDS = {
    "leg": ("lower", "leg"),
    "legs": ("lower", "leg"),
    "lower": ("lower", "leg"),
    "upper": ("upper",),
    "push": ("push",),
    "pull": ("pull",),
    "full": ("full",),
    "chest": ("push", "upper"),
    "back": ("pull", "upper"),
    "arms": ("upper", "push", "pull"),
}


def _session_for(message: str, ctx: CoachContext) -> str | None:
    for word in re.findall(r"[a-z]+", message.lower()):
        for hint in _SESSION_WORDS.get(word, ()):
            for key, name in ctx.sessions.items():
                if hint in name.lower() and key != ctx.today.session_key:
                    return key
    return None


def _today_lines(ctx: CoachContext) -> str:
    p = ctx.data["today_plan"]
    if p["status"] == "rest":
        nxt = next(
            (
                d
                for d in ctx.data["this_week"]
                if d["date"] > ctx.today.day.isoformat() and d["status"] == "planned"
            ),
            None,
        )
        tail = f" Next up: {nxt['session']} on {nxt['day']}." if nxt else ""
        return "Today is a rest day. Recovery is when the muscle you trained is built." + tail
    if p["status"] == "skipped":
        return "You skipped today. The planner has spread the work over the rest of your week."
    if ctx.today.stop:
        return (
            "Today's check-in says no training. Please rest, and get checked if anything "
            "feels wrong."
        )
    lines = [f"Today is {p['session']}, about {p['minutes']} minutes:"]
    for e in p["exercises"]:
        lines.append(f"- {e['name']}: {e['sets']} sets of {e['reps']}, target {e['target']}")
    return "\n".join(lines)


def reply(message: str, ctx: CoachContext) -> tuple[str, list[Action]]:
    m = message.lower()
    p = ctx.data["today_plan"]

    if _has(r"\bundo\b|\brestore\b|put (it|today) back|change (it|today) back", m):
        return "Sure. This puts today back to the original plan.", [Action(type="restore_today")]

    if _has(
        r"\b(at home|home workout|on (a|the|my) mat|floor (workout|exercises)|no gym|"
        r"not going to the gym|don'?t (want to )?go to the gym|skip the gym|from home)\b",
        m,
    ):
        if ctx.today.status == "planned" and not ctx.today.stop:
            return (
                "Sure: tap below and today's session switches to floor versions of each "
                "exercise you can do on a mat at home. Only today changes; you can switch "
                "back from the top of Today.",
                [Action(type="train_at_home_today")],
            )
        return (
            "No workout is planned today, but a mat session still counts: log it on Today "
            "under Activity and tick the moves you did.",
            [],
        )
    if _has(r"\bback to (the|my) gym\b|going to the gym after all", m):
        return "Done: today goes back to your usual gym.", [Action(type="back_to_gym_today")]

    c = ctx.data["cardio"]
    if _has(r"stretch|cool ?down|mobility|flexib", m):
        names = c["cool_down_stretches_today"]
        if names:
            return (
                "After today's session, hold each for about 30 seconds (each side where it "
                f"applies): {', '.join(names)}. They're on Today under Cool-down.",
                [],
            )
        return (
            "On a rest day, 10 minutes of easy stretching or yoga feels great. Log it on "
            "Today under Activity as Stretching.",
            [],
        )

    if _has(
        r"cardio|treadmill|elliptical|stair ?climber|stairmaster|rower|rowing|"
        r"\bbike\b|cycling|jump ?rope|skipping|\bhiit\b|\bwalk|\brun\b|running|"
        r"calorie|kcal|burn",
        m,
    ):
        parts = []
        if c["warm_up_today"]:
            parts.append(f"Warm-up (advised): {c['warm_up_today']}")
        if c["finisher_today"]:
            parts.append(c["finisher_today"])
        if c["rest_day_suggestion"]:
            parts.append(c["rest_day_suggestion"])
        parts.append(
            f"This week: {c['done_this_week_minutes']} of {c['weekly_target_minutes']} "
            "minutes of cardio."
        )
        if c["logged_this_week"]:
            parts.append("Logged: " + "; ".join(c["logged_this_week"][-3:]) + ".")
        parts.append(
            "Log any cardio on Today under Activity: time, plus speed, incline or the "
            "machine's calories if you have them."
        )
        minutes_said = re.search(r"\b(\d{2,3})\s*(min|mins|minutes)\b", m)
        actions = []
        if minutes_said and int(minutes_said.group(1)) < p["minutes"] and p["status"] == "planned":
            pick = 30 if int(minutes_said.group(1)) <= 37 else 45
            parts.insert(0, f"To fit {pick} minutes, tap below to trim today's accessories.")
            actions.append(Action(type="shorten_today", minutes=pick))
        return " ".join(parts), actions

    minutes = re.search(r"\b(\d{2,3})\s*(min|mins|minutes)\b", m)
    if minutes or _has(
        r"short on time|in a hurry|quick(er)? (session|workout)|less time|not much time", m
    ):
        want = int(minutes.group(1)) if minutes else 30
        pick = 30 if want <= 37 else 45
        return (
            f"Here's a shorter session: main lifts stay, accessories are trimmed to fit "
            f"{pick} minutes.",
            [Action(type="shorten_today", minutes=pick)],
        )

    if _has(
        r"\bskip\b|can'?t (make it|train|go)|no time today|busy today"
        r"|miss (today|the gym)|not going today",
        m,
    ):
        return (
            "No problem. If you skip today, the planner spreads the work over your other "
            "days this week so nothing important is lost.",
            [Action(type="skip_today")],
        )

    ex = find_exercise(m, ctx)
    if ex and _has(
        r"\b(hate|dislike|don'?t (like|want)|replace|swap out|instead of|never"
        r"|stop suggesting|can'?t do|no more|get rid)\b",
        m,
    ):
        hidden = frozenset(k for k, v in ctx.preferences.items() if v == "hidden") | {ex.id}
        alts = find_alternatives(
            ex, load_library().values(), equipment=ctx.equipment, injured=ctx.injured, hidden=hidden
        )
        names = ", ".join(a.name for a in alts)
        text = (
            f"Good alternatives for {ex.name} at your gym: {names}. "
            "If you stop suggesting it, your plan uses one of these instead."
            if alts
            else f"Nothing else at your gym trains the same thing as {ex.name}."
        )
        return text, [Action(type="hide_exercise", exercise_id=ex.id)]
    if ex and _has(r"\b(love|like|enjoy|favou?rite|more of)\b", m):
        return (
            f"Noted. Favorites are picked first when the planner has a choice, so you'll "
            f"see {ex.name} more often.",
            [Action(type="favorite_exercise", exercise_id=ex.id)],
        )

    key = _session_for(m, ctx)
    if not key and _has(
        r"\b(swap|switch)\b|something else|something different|another session|instead", m
    ):
        # No session named: offer the next one in the split.
        key = next((k for k in ctx.sessions if k != ctx.today.session_key), None)
    if key and _has(r"\b(swap|switch|change|instead|rather|do|train|else|different|another)\b", m):
        return (
            f"You can do {ctx.sessions[key]} today instead. The planner reshuffles the "
            "rest of the week to keep each muscle's recovery time.",
            [Action(type="swap_today", session_key=key)],
        )

    if _has(r"system prompt|your (instructions|rules|prompt)|how (are|were) you (made|built)", m):
        return (
            "I keep my instructions to myself, but here's what I can do: explain your "
            "targets, adjust today's workout, and sum up your progress. What would help?",
            [],
        )
    if _has(r"ignore (all |any )?(previous|prior|your) (instructions|rules)", m) or _has(
        r"\bset (my )?\w*\s*(target|weight|reps)\b.*\bto\b", m
    ):
        return (
            "I can't set targets myself: the training engine works them out from the sets "
            "you log, so they stay safe and keep progressing. I'm happy to explain them.",
            [],
        )

    if _has(
        r"travel|hotel|on holiday|on vacation|only have (dumbbells|bands|a)"
        r"|different gym|new gym|home gym",
        m,
    ):
        return (
            "For a short trip, add that gym in Profile under Your gyms and tick what it has, "
            "then choose it at the top of Today for each day you're there. Only those days "
            "change; your usual gym stays the default.",
            [],
        )
    if _has(
        r"(change|update|set|edit) (my )?(goal|target weight|training days|days|equipment"
        r"|injur|height|weight goal)",
        m,
    ):
        return (
            "You can change that in Profile (tap Edit setup). The plan updates as soon as "
            "you save.",
            [],
        )

    if _has(r"\bprotein\b", m):
        per = "1.6 to 2.2 g per kg" if ctx.units == "kg" else "0.7 to 1 g per lb"
        return (
            f"Most people who lift do well with about {per} of body weight of protein a "
            "day, spread over 3 or 4 meals. Hitting it most days matters more than exact timing.",
            [],
        )
    if _has(r"\bcreatine\b", m):
        return (
            "Creatine monohydrate is the best-studied supplement for strength: 3 to 5 g a "
            "day, any time, no loading needed. Check with your doctor first if you have "
            "kidney problems.",
            [],
        )
    if _has(r"\bdeload\b", m):
        now = "This week is a deload." if p["deload_week"] else "This week isn't a deload."
        return (
            "A deload is a lighter week, fewer sets and easier efforts, so your body "
            "catches up on recovery and you come back stronger. The planner adds one every "
            f"few weeks, or sooner if your check-ins show you're run down. {now}",
            [],
        )
    if _has(r"(main|big|compound) (lifts?|exercises?) first|why .* first\b|order of", m):
        return (
            "The main lifts are the heaviest and most technical, so they come first while "
            "you're fresh: better form, more weight, more progress. Smaller exercises "
            "follow, when tiredness matters less.",
            [],
        )
    if _has(r"enough (sets|volume|work)|how many sets|too (many|few) sets|volume", m):
        rows = ctx.data["sets_per_muscle"]["muscles"]
        named = [
            r for r in rows if r["muscle"].lower() in m or r["muscle"].lower().rstrip("s") in m
        ]
        rows = named or [r for r in rows if r["this_week_so_far"] or r["last_week"]][:6]
        if rows:
            lines = [
                f"{r['muscle']}: {r['this_week_so_far']:g} hard sets so far this week "
                f"(last week {r['last_week'] or 0:g}), target {r['weekly_target']} a week."
                for r in rows
            ]
            return "\n".join(lines), []

    if _has(r"how strong|\bbest\b|\bmax\b|1rm|one rep|stronger", m):
        said = _words(m)
        for lift in ctx.data["strength"]:
            tokens = {t for t in re.findall(r"[a-z]+", lift["exercise"].lower()) if len(t) > 3}
            if tokens & said and lift["best_estimated_1rm"]:
                return (
                    f"Your best estimated 1-rep max on {lift['exercise']} is "
                    f"{lift['best_estimated_1rm']:g} {ctx.units}, from {lift['sessions']} "
                    "sessions. That's an estimate from your logged sets, not a test.",
                    [],
                )

    if _has(r"\bwhy\b|\bexplain\b|how come|target", m):
        plan = {e["id"]: e for e in p["exercises"]}
        if ex and ex.id in plan:
            e = plan[ex.id]
            return f"{e['name']}: target {e['target']}. {e['target_reason']}", []
        if plan:
            lines = [
                f"{e['name']}: {e['target']}. {e['target_reason']}"
                for e in p["exercises"]
                if e["main_lift"]
            ]
            lines = lines or [
                f"{e['name']}: {e['target']}. {e['target_reason']}" for e in p["exercises"][:3]
            ]
            extra = (
                " This is a deload week: lighter on purpose so you recover and come back stronger."
                if p["deload_week"]
                else ""
            )
            return "\n".join(lines) + extra, []

    if _has(
        r"\bsore\b|tired|exhausted|fatigued|no energy|slept (badly|poorly)|didn'?t sleep|run down",
        m,
    ):
        c = ctx.data["check_in_today"]
        rest = ctx.data["recovery"]["needs_rest"]
        text = (
            " ".join(c["messages"])
            if c and c["messages"]
            else "Do today's check-in on the Today screen: sore muscles get light sets, and "
            "a poor night's sleep makes the session easier."
        )
        if rest:
            text += f" Still recovering from recent training: {', '.join(rest)}."
        return text, []

    if _has(r"\brir\b|reps in reserve|left in the tank|before failure", m):
        return (
            'Reps in reserve (RIR) is how many more reps you could have done. "2 left" '
            "means you stop with two good reps still in you. It keeps you training hard "
            "enough to grow while staying safe and recovering well.",
            [],
        )

    if _has(r"progress|how am i doing|results|improv|stronger|records?|\bprs?\b", m):
        g = ctx.data["progress_this_week"]
        text = " ".join(g["summary"]) or "Log a few workouts and I'll summarize your progress."
        best = [s for s in ctx.data["strength"] if s["best_estimated_1rm"]][:3]
        if best:
            text += (
                " Best estimated 1-rep max: "
                + ", ".join(
                    f"{s['exercise']} {s['best_estimated_1rm']:g} {ctx.units}" for s in best
                )
                + "."
            )
        return text, []

    if _has(
        r"\bgoal\b|target weight|when will|how long|\blos(e|ing)\b|\bgain(ing)?\b"
        r"|\bscale\b|\bweigh",
        m,
    ):
        b = ctx.data["body"]
        parts = [
            b["goal_timeline"]
            or "Log your weight most mornings and I'll estimate when you'll reach your goal."
        ]
        if b["rate_per_week"] is not None:
            parts.append(f"Your trend is changing by {b['rate_per_week']:+g} {ctx.units} a week.")
            if b["trend_weight"]:
                pct = abs(b["rate_per_week"]) / b["trend_weight"] * 100
                parts.append(
                    f"That's about {pct:.1f}% of your body weight a week; 0.5 to 1% is the "
                    "range that protects muscle."
                )
        parts += b["warnings"]
        return " ".join(parts), []

    if _has(r"\btoday\b|workout|session|\bplan\b|what (do|should) i do", m):
        return _today_lines(ctx), []

    return (
        "I'm here to help with your training. I can explain today's targets, shorten or "
        "skip today, swap today's session, stop suggesting an exercise you don't like, and "
        'sum up your progress. Try "Why this weight today?" or "I only have 30 minutes".',
        [],
    )
