"""
Gmail CLI

Usage:
    python -m lib.gmail login
    python -m lib.gmail status
    python -m lib.gmail inbox --limit 10
    python -m lib.gmail unread
    python -m lib.gmail read <email_id>
    python -m lib.gmail send "to@example.com" "Subject" "Body"
    python -m lib.gmail labels
    python -m lib.gmail search "from:boss@company.com"
"""

import sys
import io

# Windows console UTF-8 encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Optional

app = typer.Typer(
    name="gmail",
    help="Gmail CLI - Email management from command line",
    add_completion=False,
)
console = Console()


@app.command()
def login():
    """
    Authenticate with Gmail via OAuth.

    Opens browser for Google authorization and saves token locally.
    """
    from .auth import login as do_login
    from .errors import GmailError

    try:
        token = do_login()
        console.print("[green]✓ Logged in successfully![/green]")
        console.print(f"  Scopes: {', '.join(token.scopes[:3])}...")
    except GmailError as e:
        console.print(f"[red]✗ Login failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Check current authentication status.
    """
    from .auth import get_credentials
    from .client import GmailClient
    from .errors import GmailError

    creds = get_credentials()

    if creds is None:
        if json_output:
            print(json.dumps({"authenticated": False, "error": "Not logged in"}, ensure_ascii=False))
        else:
            console.print("[yellow]Not logged in. Run 'python -m lib.gmail login' first.[/yellow]")
        raise typer.Exit(1)

    # Validate token
    valid = False
    email = "unknown"
    try:
        client = GmailClient(credentials=creds)
        profile = client.get_profile()
        valid = True
        email = profile.get("emailAddress", "unknown")
    except GmailError:
        pass

    if json_output:
        print(json.dumps({
            "authenticated": True,
            "valid": valid,
            "email": email,
        }, ensure_ascii=False, indent=2))
    else:
        console.print("[bold]Gmail Status:[/bold]")
        console.print(f"  Email: {email}")
        if valid:
            console.print("  Status: [green]Valid[/green]")
        else:
            console.print("  Status: [red]Invalid (re-login required)[/red]")


@app.command()
def inbox(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of emails to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show inbox emails.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        emails = client.list_emails(query="in:inbox", max_results=limit)

        if json_output:
            output = [{
                "id": e.id,
                "subject": e.subject,
                "from": e.sender,
                "date": e.date.isoformat() if e.date else None,
                "snippet": e.snippet,
                "is_unread": e.is_unread,
            } for e in emails]
            print(json.dumps({"count": len(emails), "emails": output}, ensure_ascii=False, indent=2))
        else:
            _display_email_list(emails, "Inbox")
    except GmailError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to read inbox: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def unread(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of emails to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Show unread emails.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        emails = client.list_emails(query="is:unread", max_results=limit)

        if json_output:
            output = [{
                "id": e.id,
                "subject": e.subject,
                "from": e.sender,
                "date": e.date.isoformat() if e.date else None,
                "snippet": e.snippet,
            } for e in emails]
            print(json.dumps({"count": len(emails), "emails": output}, ensure_ascii=False, indent=2))
        else:
            _display_email_list(emails, "Unread")
    except GmailError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to read unread: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Gmail search query (e.g., 'from:boss@company.com')"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of emails to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Search emails with Gmail query syntax.

    Examples:
        from:example@gmail.com
        subject:meeting
        after:2024/01/01 before:2024/12/31
        has:attachment
        is:starred
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        emails = client.list_emails(query=query, max_results=limit)

        if json_output:
            output = [{
                "id": e.id,
                "subject": e.subject,
                "from": e.sender,
                "date": e.date.isoformat() if e.date else None,
                "snippet": e.snippet,
                "is_unread": e.is_unread,
            } for e in emails]
            print(json.dumps({"query": query, "count": len(emails), "emails": output}, ensure_ascii=False, indent=2))
        else:
            _display_email_list(emails, f"Search: {query}")
    except GmailError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Search failed: {e}[/red]")
        raise typer.Exit(1)


@app.command("read")
def read_email(
    email_id: str = typer.Argument(..., help="Email ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    mark_read: bool = typer.Option(False, "--mark-read", "-m", help="Mark as read"),
):
    """
    Read full email content.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        email = client.get_email(email_id)

        if mark_read and email.is_unread:
            client.mark_as_read(email_id)

        if json_output:
            print(json.dumps({
                "id": email.id,
                "thread_id": email.thread_id,
                "subject": email.subject,
                "from": email.sender,
                "to": email.to,
                "cc": email.cc,
                "date": email.date.isoformat() if email.date else None,
                "body_text": email.body_text,
                "body_html": email.body_html,
                "labels": email.labels,
                "is_unread": email.is_unread,
                "attachments": [{"filename": a.filename, "size": a.size} for a in email.attachments],
                "permalink": email.permalink,
            }, ensure_ascii=False, indent=2))
        else:
            _display_email_detail(email)
    except GmailError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to read email: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def send(
    to: str = typer.Argument(..., help="Recipient email address"),
    subject: str = typer.Argument(..., help="Email subject"),
    body: str = typer.Argument(..., help="Email body"),
    cc: Optional[str] = typer.Option(None, "--cc", help="CC recipients"),
    bcc: Optional[str] = typer.Option(None, "--bcc", help="BCC recipients"),
    html: bool = typer.Option(False, "--html", help="Body is HTML"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Send an email.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        result = client.send(to, subject, body, cc=cc, bcc=bcc, html=html)

        if json_output:
            print(json.dumps({
                "ok": True,
                "id": result.id,
                "thread_id": result.thread_id,
                "permalink": result.permalink,
            }, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Email sent![/green]")
            console.print(f"  To: {to}")
            console.print(f"  Subject: {subject}")
            console.print(f"  Permalink: {result.permalink}")
    except GmailError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to send email: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def labels(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    List all labels.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        label_list = client.list_labels()

        if json_output:
            output = [{
                "id": l.id,
                "name": l.name,
                "type": l.type,
                "messages_total": l.messages_total,
                "messages_unread": l.messages_unread,
            } for l in label_list]
            print(json.dumps({"count": len(label_list), "labels": output}, ensure_ascii=False, indent=2))
        else:
            table = Table(title=f"Labels ({len(label_list)})")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Type")
            table.add_column("Total", justify="right")
            table.add_column("Unread", justify="right", style="yellow")

            for l in sorted(label_list, key=lambda x: x.name):
                table.add_row(
                    l.id,
                    l.name,
                    l.type,
                    str(l.messages_total) if l.messages_total else "-",
                    str(l.messages_unread) if l.messages_unread else "-",
                )

            console.print(table)
    except GmailError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to list labels: {e}[/red]")
        raise typer.Exit(1)


@app.command("mark-read")
def mark_read(
    email_id: str = typer.Argument(..., help="Email ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Mark email as read.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        email = client.mark_as_read(email_id)

        if json_output:
            print(json.dumps({"ok": True, "id": email.id, "is_unread": email.is_unread}, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Marked as read[/green]")
    except GmailError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def archive(
    email_id: str = typer.Argument(..., help="Email ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Archive email (remove from inbox).
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        email = client.archive(email_id)

        if json_output:
            print(json.dumps({"ok": True, "id": email.id}, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Email archived[/green]")
    except GmailError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def trash(
    email_id: str = typer.Argument(..., help="Email ID"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Move email to trash.
    """
    from .client import GmailClient
    from .errors import GmailError

    try:
        client = GmailClient()
        client.trash(email_id)

        if json_output:
            print(json.dumps({"ok": True, "id": email_id}, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Email moved to trash[/green]")
    except GmailError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed: {e}[/red]")
        raise typer.Exit(1)


def _display_email_list(emails, title: str):
    """Display list of emails in table format."""
    if not emails:
        console.print(f"[yellow]No emails found in {title}.[/yellow]")
        return

    table = Table(title=f"{title} ({len(emails)})")
    table.add_column("ID", style="dim", max_width=20)
    table.add_column("From", style="cyan", max_width=30)
    table.add_column("Subject", max_width=40)
    table.add_column("Date", style="dim")
    table.add_column("", justify="center")

    for e in emails:
        unread_icon = "●" if e.is_unread else ""
        date_str = e.date.strftime("%Y-%m-%d %H:%M") if e.date else "-"
        subject = e.subject[:40] + "..." if len(e.subject) > 40 else e.subject
        sender = e.sender[:30] + "..." if len(e.sender) > 30 else e.sender

        table.add_row(
            e.id[:20],
            sender,
            subject,
            date_str,
            f"[blue]{unread_icon}[/blue]"
        )

    console.print(table)


def _display_email_detail(email):
    """Display full email content."""
    console.print(Panel(
        f"[bold]{email.subject}[/bold]\n\n"
        f"[dim]From:[/dim] {email.sender}\n"
        f"[dim]To:[/dim] {', '.join(email.to)}\n"
        f"[dim]Date:[/dim] {email.date.strftime('%Y-%m-%d %H:%M:%S') if email.date else 'Unknown'}\n"
        f"[dim]Labels:[/dim] {', '.join(email.labels)}",
        title="Email Details"
    ))

    if email.attachments:
        console.print("\n[bold]Attachments:[/bold]")
        for a in email.attachments:
            size_kb = a.size / 1024 if a.size else 0
            console.print(f"  📎 {a.filename} ({size_kb:.1f} KB)")

    console.print("\n[bold]Body:[/bold]")
    body = email.body_text or email.snippet or "(No content)"
    console.print(body[:2000] + "..." if len(body) > 2000 else body)

    console.print(f"\n[dim]Permalink: {email.permalink}[/dim]")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
