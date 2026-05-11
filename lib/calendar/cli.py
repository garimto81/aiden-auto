"""
Calendar CLI

Usage:
    python -m lib.calendar login
    python -m lib.calendar status
    python -m lib.calendar today
    python -m lib.calendar week
    python -m lib.calendar list --days 14
    python -m lib.calendar create "Meeting" "2026-03-15 14:00" "2026-03-15 15:00"
    python -m lib.calendar calendars
"""

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
from datetime import datetime, date
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

app = typer.Typer(
    name="calendar",
    help="Google Calendar CLI - Manage events from command line",
    add_completion=False,
)
console = Console()


@app.command()
def login():
    """Authenticate with Google Calendar via OAuth."""
    from .auth import login as do_login
    from .errors import CalendarError

    try:
        do_login()
        console.print("[green]✓ Calendar authenticated successfully![/green]")
    except CalendarError as e:
        console.print(f"[red]✗ Login failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Check current authentication status."""
    from .auth import get_credentials
    from .calendar_client import CalendarClient
    from .errors import CalendarError

    creds = get_credentials()

    if creds is None:
        if json_output:
            print(json.dumps({"authenticated": False, "error": "Not logged in"}, ensure_ascii=False))
        else:
            console.print("[yellow]Not logged in. Run 'python -m lib.calendar login' first.[/yellow]")
        raise typer.Exit(1)

    valid = False
    try:
        client = CalendarClient(credentials=creds)
        calendars = client.list_calendars()
        valid = True
        primary = next((c for c in calendars if c.primary), None)
    except CalendarError:
        primary = None

    if json_output:
        print(json.dumps({
            "authenticated": True,
            "valid": valid,
            "primary_calendar": primary.id if primary else None,
            "gws_available": client._gws_available if valid else False,
        }, ensure_ascii=False, indent=2))
    else:
        console.print("[bold]Calendar Status:[/bold]")
        if valid:
            console.print("  Status: [green]Valid[/green]")
            if primary:
                console.print(f"  Primary: {primary.id}")
            console.print(f"  Backend: {'gws CLI' if client._gws_available else 'Python API'}")
        else:
            console.print("  Status: [red]Invalid (re-login required)[/red]")


@app.command()
def today(
    calendar_id: str = typer.Option("primary", "--calendar", "-c", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show today's events."""
    from .calendar_client import CalendarClient
    from .errors import CalendarError

    try:
        client = CalendarClient()
        events = client.today(calendar_id=calendar_id)

        if json_output:
            _json_events(events)
        else:
            _display_events(events, "Today")
    except CalendarError as e:
        _handle_cli_error(e, json_output)


@app.command()
def week(
    calendar_id: str = typer.Option("primary", "--calendar", "-c", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show this week's events."""
    from .calendar_client import CalendarClient
    from .errors import CalendarError

    try:
        client = CalendarClient()
        events = client.week(calendar_id=calendar_id)

        if json_output:
            _json_events(events)
        else:
            _display_events(events, "This Week")
    except CalendarError as e:
        _handle_cli_error(e, json_output)


@app.command("list")
def list_events(
    days: int = typer.Option(7, "--days", "-d", help="Days to look ahead"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max events"),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Search query"),
    calendar_id: str = typer.Option("primary", "--calendar", "-c", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List upcoming events."""
    from .calendar_client import CalendarClient
    from .errors import CalendarError

    try:
        client = CalendarClient()
        events = client.list_events(
            calendar_id=calendar_id,
            days=days,
            max_results=limit,
            query=query,
        )

        if json_output:
            _json_events(events)
        else:
            _display_events(events, f"Next {days} days")
    except CalendarError as e:
        _handle_cli_error(e, json_output)


@app.command()
def create(
    summary: str = typer.Argument(..., help="Event title"),
    start: str = typer.Argument(..., help="Start time (YYYY-MM-DD HH:MM or YYYY-MM-DD)"),
    end: Optional[str] = typer.Argument(None, help="End time (default: +1 hour or same day)"),
    description: str = typer.Option("", "--desc", help="Event description"),
    location: str = typer.Option("", "--location", "-l", help="Location"),
    calendar_id: str = typer.Option("primary", "--calendar", "-c", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Create a new event."""
    from .calendar_client import CalendarClient
    from .models import CreateEventRequest
    from .errors import CalendarError
    from datetime import timedelta

    try:
        req = _parse_create_request(
            summary, start, end, description, location, calendar_id
        )
        client = CalendarClient()
        event = client.create_event(req)

        if json_output:
            print(json.dumps({
                "ok": True,
                "id": event.id,
                "summary": event.summary,
                "permalink": event.permalink,
            }, ensure_ascii=False, indent=2))
        else:
            console.print(f"[green]✓ Event created: {event.summary}[/green]")
            console.print(f"  Link: {event.permalink}")
    except CalendarError as e:
        _handle_cli_error(e, json_output)
    except ValueError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Invalid input: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def calendars(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List all calendars."""
    from .calendar_client import CalendarClient
    from .errors import CalendarError

    try:
        client = CalendarClient()
        cals = client.list_calendars()

        if json_output:
            output = [{
                "id": c.id,
                "summary": c.summary,
                "time_zone": c.time_zone,
                "primary": c.primary,
            } for c in cals]
            print(json.dumps({"count": len(cals), "calendars": output}, ensure_ascii=False, indent=2))
        else:
            table = Table(title=f"Calendars ({len(cals)})")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Timezone")
            table.add_column("Primary", justify="center")

            for c in cals:
                table.add_row(
                    c.id[:40],
                    c.summary,
                    c.time_zone,
                    "★" if c.primary else "",
                )
            console.print(table)
    except CalendarError as e:
        _handle_cli_error(e, json_output)


@app.command()
def delete(
    event_id: str = typer.Argument(..., help="Event ID"),
    calendar_id: str = typer.Option("primary", "--calendar", "-c", help="Calendar ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Delete an event."""
    from .calendar_client import CalendarClient
    from .errors import CalendarError

    try:
        client = CalendarClient()
        client.delete_event(event_id, calendar_id=calendar_id)

        if json_output:
            print(json.dumps({"ok": True, "id": event_id}, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Event deleted[/green]")
    except CalendarError as e:
        _handle_cli_error(e, json_output)


# ── Helpers ───────────────────────────────────────────────


def _parse_create_request(
    summary, start_str, end_str, description, location, calendar_id
):
    """Parse CLI args into CreateEventRequest."""
    from .models import CreateEventRequest
    from datetime import timedelta

    # Try datetime first, then date-only
    start_dt = None
    start_date = None

    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            start_date = date.fromisoformat(start_str)
        except ValueError:
            raise ValueError(f"Invalid start format: {start_str}. Use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'")

    if start_dt:
        # Timed event
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M")
            except ValueError:
                raise ValueError(f"Invalid end format: {end_str}. Use 'YYYY-MM-DD HH:MM'")
        else:
            end_dt = start_dt + timedelta(hours=1)

        return CreateEventRequest(
            summary=summary,
            description=description,
            location=location,
            start_time=start_dt,
            end_time=end_dt,
            calendar_id=calendar_id,
        )
    else:
        # All-day event
        if end_str:
            try:
                end_date = date.fromisoformat(end_str)
            except ValueError:
                raise ValueError(f"Invalid end date format: {end_str}. Use 'YYYY-MM-DD'")
        else:
            end_date = start_date
        return CreateEventRequest(
            summary=summary,
            description=description,
            location=location,
            all_day_start=start_date,
            all_day_end=end_date,
            calendar_id=calendar_id,
        )


def _display_events(events, title: str):
    """Display events in table format."""
    if not events:
        console.print(f"[yellow]No events found for {title}.[/yellow]")
        return

    table = Table(title=f"{title} ({len(events)} events)")
    table.add_column("Time", style="cyan", min_width=16)
    table.add_column("Event", max_width=40)
    table.add_column("Location", style="dim", max_width=20)

    for e in events:
        if e.is_all_day:
            time_str = e.start.date.isoformat() if e.start and e.start.date else "All day"
        elif e.start and e.start.date_time:
            time_str = e.start.date_time.strftime("%Y-%m-%d %H:%M")
        else:
            time_str = "-"

        summary = e.summary[:40] + "..." if len(e.summary) > 40 else e.summary
        location = (e.location[:20] + "...") if len(e.location) > 20 else e.location

        table.add_row(time_str, summary, location)

    console.print(table)


def _json_events(events):
    """Output events as JSON."""
    output = [{
        "id": e.id,
        "summary": e.summary,
        "start": (e.start.date_time.isoformat() if e.start and e.start.date_time
                  else e.start.date.isoformat() if e.start and e.start.date
                  else None),
        "end": (e.end.date_time.isoformat() if e.end and e.end.date_time
                else e.end.date.isoformat() if e.end and e.end.date
                else None),
        "location": e.location,
        "is_all_day": e.is_all_day,
        "permalink": e.permalink,
    } for e in events]
    print(json.dumps({"count": len(events), "events": output}, ensure_ascii=False, indent=2))


def _handle_cli_error(error, json_output: bool):
    """Handle error in CLI context."""
    if json_output:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
    else:
        console.print(f"[red]✗ {error}[/red]")
    raise typer.Exit(1)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
