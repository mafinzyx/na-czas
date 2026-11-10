"""Weekly advice in plain language.

The numbers always come from the planner. The LLM only turns them into a short,
readable briefing; it never calculates anything. Without an API key (or if the
call fails) a rule-based summary is returned instead, so the feature never breaks.
"""

import json
import logging

import anthropic

from app.config import get_settings
from app.schemas import Advice, Language, RouteOption, TripPlan, WeekPlan

logger = logging.getLogger(__name__)

LANGUAGE_NAMES: dict[str, str] = {"en": "English", "pl": "Polish"}

SYSTEM_PROMPT = """\
You are a commute assistant inside a weekly travel planner. You receive a JSON plan \
that the app has already calculated: for each trip the recommended transport mode, \
the transit lines if any, when to leave, the cost, a backup mode and the time until which the backup is still \
possible ("decide_by"), plus weather and traffic notes.

Write a short briefing for the week that helps the person avoid last-minute surprises:
- start with the one or two trips that need the most attention (important trips, rush \
hour, bad weather, a backup that has to leave earlier than the main option) and say \
exactly when to decide or leave;
- mention where money is saved compared with driving everywhere, if it is;
- finish with one practical tip for the week.

Rules: use only the numbers from the JSON and never invent times or prices. Write 4 to 6 \
lines, each starting with "- ". Plain text, no markdown headings, no bold. Write in {language}."""

# Rule-based fallback texts.
_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "empty": "- No trips in this period. Add one to get a plan.",
        "summary": "- {count} trips this week, about {minutes} min of travel and {cost:.2f} zł in total.",
        "saving": "- That is {saving:.2f} zł less than driving everywhere ({car:.2f} zł).",
        "commit": "- {day} {title}: go by {mode}, leave by {leave}. The backup ({backup}) leaves earlier, so decide by {decide}.",
        "rush": "- {day} {title} falls in rush hour: traffic adds about {percent}% to driving time.",
        "weather": "- {day} {title}: rain is expected, so {mode} was chosen over cycling or walking.",
        "calm": "- No trip needs an early decision this week: every backup is still available at departure time.",
    },
    "pl": {
        "empty": "- Brak przejazdów w tym okresie. Dodaj pierwszy, aby zobaczyć plan.",
        "summary": "- {count} przejazdów w tym tygodniu, około {minutes} min w drodze i łącznie {cost:.2f} zł.",
        "saving": "- To o {saving:.2f} zł mniej niż jeżdżenie wszędzie samochodem ({car:.2f} zł).",
        "commit": "- {day} {title}: jedź środkiem „{mode}”, wyjdź do {leave}. Plan B ({backup}) rusza wcześniej, więc zdecyduj do {decide}.",
        "rush": "- {day} {title} wypada w godzinach szczytu: korki wydłużają jazdę o około {percent}%.",
        "weather": "- {day} {title}: zapowiadany jest deszcz, dlatego wybrano „{mode}” zamiast roweru lub spaceru.",
        "calm": "- Żaden przejazd nie wymaga wcześniejszej decyzji: plan B jest zawsze dostępny w chwili wyjścia.",
    },
}
_MODE_NAMES: dict[str, dict[str, str]] = {
    "en": {"car": "car", "taxi": "taxi", "transit": "public transport", "bike": "bike", "scooter": "scooter", "walk": "walking"},
    "pl": {"car": "samochód", "taxi": "taxi", "transit": "komunikacja", "bike": "rower", "scooter": "hulajnoga", "walk": "pieszo"},
}
_DAY_NAMES: dict[str, list[str]] = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "pl": ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."],
}


def _upcoming_trips(plan: WeekPlan) -> list[TripPlan]:
    return [trip for day in plan.days for trip in day.trips if trip.status != "past"]


def _chosen(trip: TripPlan) -> RouteOption:
    return next(option for option in trip.options if option.id == trip.recommended)


def _facts_for_llm(plan: WeekPlan) -> str:
    """Compact JSON with only what the model needs."""
    trips = []
    for trip in _upcoming_trips(plan):
        chosen = _chosen(trip)
        trips.append(
            {
                "day": trip.time.strftime("%A %d.%m"),
                "title": trip.title,
                "to": trip.destination.name,
                "arrive_at": trip.time.strftime("%H:%M"),
                "importance": trip.importance,
                "recommended_mode": chosen.mode.value,
                "lines": chosen.label,
                "leave_by": chosen.depart_at.strftime("%H:%M"),
                "typical_minutes": chosen.typical_minutes,
                "bad_day_minutes": chosen.worst_minutes,
                "cost_pln": chosen.cost_pln,
                "climb_m": chosen.ascent_m,
                "warnings": chosen.warnings,
                "traffic_multiplier": trip.congestion,
                "weather": trip.weather.model_dump() if trip.weather else None,
                "backup": (
                    {
                        "mode": trip.backup.mode.value,
                        "lines": trip.backup.label,
                        "board_at_stop": trip.backup.board_stop,
                        "decide_by": trip.backup.decide_by.strftime("%H:%M"),
                        "must_decide_before_leaving": trip.backup.commit_early,
                    }
                    if trip.backup
                    else None
                ),
            }
        )
    return json.dumps({"summary": plan.summary.model_dump(), "trips": trips}, ensure_ascii=False)


def _ask_llm(plan: WeekPlan, language: Language) -> str | None:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=40.0, max_retries=1)
    try:
        response = client.messages.create(
            model=settings.advisor_model,
            max_tokens=2000,
            output_config={"effort": "low"},  # a short summary of given facts needs little reasoning
            system=SYSTEM_PROMPT.format(language=LANGUAGE_NAMES[language]),
            messages=[{"role": "user", "content": _facts_for_llm(plan)}],
        )
    except anthropic.APIError as error:
        logger.warning("AI advice failed, using the rule-based summary: %s", error)
        return None

    if response.stop_reason == "refusal":
        return None
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or None


def rule_based_advice(plan: WeekPlan, language: Language) -> str:
    texts, modes, days = _TEXTS[language], _MODE_NAMES[language], _DAY_NAMES[language]
    trips = _upcoming_trips(plan)
    if not trips:
        return texts["empty"]

    summary = plan.summary
    lines = [
        texts["summary"].format(
            count=summary.trips_count, minutes=summary.travel_minutes, cost=summary.recommended_cost_pln
        )
    ]
    if summary.car_only_cost_pln is not None:
        saving = summary.car_only_cost_pln - summary.recommended_cost_pln
        if saving >= 1:
            lines.append(texts["saving"].format(saving=saving, car=summary.car_only_cost_pln))

    def day_of(trip: TripPlan) -> str:
        return days[trip.time.weekday()]

    def name_of(mode: str, label: str | None) -> str:
        return f"{modes[mode]} {label}" if label else modes[mode]

    early = [t for t in trips if t.backup and t.backup.commit_early]
    for trip in early[:2]:
        chosen = _chosen(trip)
        lines.append(
            texts["commit"].format(
                day=day_of(trip),
                title=trip.title,
                mode=name_of(chosen.mode.value, chosen.label),
                leave=chosen.depart_at.strftime("%H:%M"),
                backup=name_of(trip.backup.mode.value, trip.backup.label),
                decide=trip.backup.decide_by.strftime("%H:%M"),
            )
        )
    if not early:
        lines.append(texts["calm"])

    busiest = max(trips, key=lambda t: t.congestion)
    if busiest.congestion >= 1.4:
        lines.append(
            texts["rush"].format(
                day=day_of(busiest), title=busiest.title, percent=round((busiest.congestion - 1) * 100)
            )
        )

    rainy = next((t for t in trips if t.weather and t.weather.is_wet), None)
    if rainy and _chosen(rainy).mode.value in ("car", "taxi", "transit"):
        lines.append(
            texts["weather"].format(day=day_of(rainy), title=rainy.title, mode=modes[_chosen(rainy).mode.value])
        )
    return "\n".join(lines)


def weekly_advice(plan: WeekPlan, language: Language) -> Advice:
    if get_settings().anthropic_api_key and not get_settings().offline and _upcoming_trips(plan):
        text = _ask_llm(plan, language)
        if text:
            return Advice(source="ai", text=text)
    return Advice(source="rules", text=rule_based_advice(plan, language))
