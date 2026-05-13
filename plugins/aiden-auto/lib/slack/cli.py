"""
Slack CLI

Usage:
    python -m lib.slack login
    python -m lib.slack send "#general" "Hello!"
    python -m lib.slack history "#general" --limit 10
    python -m lib.slack channels --include-private
    python -m lib.slack user U123456789
    python -m lib.slack list-create "My List" --description "Todo list"
    python -m lib.slack list-add F0ACFAJ50BE "Task 1"
"""

import sys
import io
from pathlib import Path

# Windows 콘솔 UTF-8 인코딩 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import typer
from rich.console import Console
from rich.table import Table
from typing import Optional

app = typer.Typer(
    name="slack",
    help="Slack CLI - Message sending and channel management",
    add_completion=False,
)
console = Console()


@app.command()
def login(
    port: int = typer.Option(None, "--port", "-p", help="OAuth callback port (default: auto-detect)"),
    user: bool = typer.Option(False, "--user", "-u", help="Also request user token for Lists API"),
):
    """
    Authenticate with Slack via OAuth.

    Opens browser for Slack authorization and saves token locally.

    Use --user flag to also request user token with lists:read/write scopes
    for Slack Lists API access.
    """
    from .auth import login as do_login
    from .errors import SlackError

    try:
        if user:
            console.print("[cyan]Requesting both bot and user tokens...[/cyan]")
            console.print("[dim]User token required for Slack Lists API (lists:read, lists:write)[/dim]")

        token = do_login(port=port, include_user_scopes=user)
        console.print("[green]✓ Logged in successfully![/green]")
        console.print(f"  Bot User: {token.bot_user_id}")
        console.print(f"  Workspace: {token.team.name}")
        console.print(f"  Scopes: {token.scope}")

        if user:
            from .auth import get_user_token
            user_token = get_user_token()
            if user_token:
                console.print("\n[green]✓ User token obtained![/green]")
                console.print(f"  User Scopes: {user_token.scope}")
            else:
                console.print("\n[yellow]⚠ User token not obtained. Check Slack App settings.[/yellow]")
    except SlackError as e:
        console.print(f"[red]✗ Login failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Check current authentication status.
    """
    from .auth import get_token
    from .client import SlackClient
    from .errors import SlackError

    token = get_token()

    if token is None:
        if json_output:
            print(json.dumps({"authenticated": False, "error": "Not logged in"}, ensure_ascii=False))
        else:
            console.print("[yellow]Not logged in. Run 'python -m lib.slack login' first.[/yellow]")
        raise typer.Exit(1)

    # Validate token
    valid = False
    try:
        client = SlackClient(token=token.access_token)
        valid = client.validate_token()
    except SlackError:
        pass

    if json_output:
        print(json.dumps({
            "authenticated": True,
            "valid": valid,
            "bot_user_id": token.bot_user_id,
            "workspace": token.team.name,
            "team_id": token.team.id,
            "scopes": token.scope.split(",") if token.scope else [],
        }, ensure_ascii=False, indent=2))
    else:
        console.print("[bold]Token Info:[/bold]")
        console.print(f"  Bot User: {token.bot_user_id}")
        console.print(f"  Workspace: {token.team.name}")
        console.print(f"  Scopes: {token.scope}")
        if valid:
            console.print("  Status: [green]Valid[/green]")
        else:
            console.print("  Status: [red]Invalid (re-login required)[/red]")


@app.command()
def send(
    channel: str = typer.Argument(..., help="Channel ID (C...) or name (#general)"),
    message: str = typer.Argument(..., help="Message text"),
    thread_ts: Optional[str] = typer.Option(None, "--thread", "-t", help="Thread timestamp for reply"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Send a message to a Slack channel.
    """
    from .client import SlackClient
    from .errors import SlackError

    try:
        client = SlackClient()
        result = client.send_message(channel, message, thread_ts=thread_ts)

        if json_output:
            print(json.dumps({
                "ok": True,
                "channel": result.channel,
                "ts": result.ts,
                "permalink": result.permalink,
            }, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Message sent![/green]")
            console.print(f"  Channel: {result.channel}")
            console.print(f"  Timestamp: {result.ts}")
            console.print(f"  Permalink: {result.permalink}")
    except SlackError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to send message: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def update(
    channel: str = typer.Argument(..., help="Channel ID (C...) where the message exists"),
    ts: str = typer.Argument(..., help="Timestamp of the message to update"),
    message: str = typer.Argument(..., help="New message text"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Update an existing message in a Slack channel.
    """
    from .client import SlackClient
    from .errors import SlackError

    try:
        client = SlackClient()
        result = client.update_message(channel, ts, message)

        if json_output:
            print(json.dumps({
                "ok": True,
                "channel": result.channel,
                "ts": result.ts,
            }, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Message updated![/green]")
            console.print(f"  Channel: {result.channel}")
            console.print(f"  Timestamp: {result.ts}")
    except SlackError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to update message: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def history(
    channel: str = typer.Argument(..., help="Channel ID (C...) or name"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of messages to retrieve"),
    cursor: Optional[str] = typer.Option(None, "--cursor", help="Pagination cursor from previous response"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Read message history from a channel.
    """
    from .client import SlackClient
    from .errors import SlackError

    try:
        client = SlackClient()
        messages, next_cursor = client.get_history_with_cursor(channel, limit=limit, cursor=cursor)

        if json_output:
            output = [{
                "ts": msg.ts,
                "user": msg.user,
                "text": msg.text,
                "thread_ts": msg.thread_ts,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
            } for msg in messages]
            result = {
                "channel": channel,
                "count": len(messages),
                "messages": output,
                "response_metadata": {"next_cursor": next_cursor or ""},
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if not messages:
                console.print("[yellow]No messages found.[/yellow]")
                return

            console.print(f"[bold]Messages in {channel} (latest {len(messages)}):[/bold]\n")

            for msg in reversed(messages):  # Show oldest first
                user_display = msg.user or "bot"
                text_preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
                timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M") if msg.timestamp else msg.ts

                if msg.thread_ts and msg.thread_ts != msg.ts:
                    console.print(f"  [dim]↳ {timestamp}[/dim] [cyan]{user_display}[/cyan]: {text_preview}")
                else:
                    console.print(f"  [dim]{timestamp}[/dim] [cyan]{user_display}[/cyan]: {text_preview}")

            if next_cursor:
                console.print(f"\n[dim]더 많은 메시지가 있습니다. --cursor {next_cursor} 옵션으로 다음 페이지 조회[/dim]")
    except SlackError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to read history: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def channels(
    include_private: bool = typer.Option(False, "--private", "-p", help="Include private channels"),
    show_archived: bool = typer.Option(False, "--archived", "-a", help="Include archived channels"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    List all accessible channels.
    """
    from .client import SlackClient
    from .errors import SlackError

    try:
        client = SlackClient()
        channel_list = client.list_channels(
            include_private=include_private,
            exclude_archived=not show_archived,
        )

        if json_output:
            output = [{
                "id": ch.id,
                "name": ch.name,
                "is_private": ch.is_private,
                "is_archived": ch.is_archived,
                "num_members": ch.num_members,
            } for ch in channel_list]
            print(json.dumps({"count": len(channel_list), "channels": output}, ensure_ascii=False, indent=2))
        else:
            if not channel_list:
                console.print("[yellow]No channels found.[/yellow]")
                return

            table = Table(title=f"Channels ({len(channel_list)})")
            table.add_column("ID", style="dim")
            table.add_column("Name", style="cyan")
            table.add_column("Private", justify="center")
            table.add_column("Members", justify="right")

            for ch in channel_list:
                private_icon = "🔒" if ch.is_private else ""
                members = str(ch.num_members) if ch.num_members else "-"
                table.add_row(ch.id, f"#{ch.name}", private_icon, members)

            console.print(table)
    except SlackError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to list channels: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def user(
    user_id: str = typer.Argument(..., help="User ID (U...)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Get user information.
    """
    from .client import SlackClient
    from .errors import SlackError

    try:
        client = SlackClient()
        user_info = client.get_user(user_id)

        if json_output:
            print(json.dumps({
                "id": user_info.id,
                "name": user_info.name,
                "real_name": user_info.real_name,
                "display_name": user_info.display_name,
                "email": user_info.email,
                "is_bot": user_info.is_bot,
            }, ensure_ascii=False, indent=2))
        else:
            console.print("[bold]User Info:[/bold]")
            console.print(f"  ID: {user_info.id}")
            console.print(f"  Username: @{user_info.name}")
            if user_info.real_name:
                console.print(f"  Real Name: {user_info.real_name}")
            if user_info.display_name:
                console.print(f"  Display Name: {user_info.display_name}")
            if user_info.email:
                console.print(f"  Email: {user_info.email}")
            console.print(f"  Is Bot: {'Yes' if user_info.is_bot else 'No'}")
    except SlackError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to get user info: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def info(
    channel: str = typer.Argument(..., help="Channel ID (C...)"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Get channel information."""
    from .client import SlackClient
    from .errors import SlackError
    try:
        client = SlackClient()
        data = client.get_channel_info(channel)
        if json_output:
            print(json.dumps({"channel": data}, ensure_ascii=False, indent=2))
        else:
            console.print(f"Channel: #{data.get('name')} ({channel})")
    except SlackError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        raise typer.Exit(1)


@app.command()
def members(
    channel: str = typer.Argument(..., help="Channel ID (C...)"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Get channel members."""
    from .client import SlackClient
    from .errors import SlackError
    try:
        client = SlackClient()
        member_list = client.get_channel_members(channel)
        if json_output:
            print(json.dumps({"members": member_list, "count": len(member_list)}, ensure_ascii=False, indent=2))
        else:
            console.print(f"Members: {len(member_list)}")
    except SlackError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        raise typer.Exit(1)


@app.command()
def pins(
    channel: str = typer.Argument(..., help="Channel ID (C...)"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Get pinned messages."""
    from .client import SlackClient
    from .errors import SlackError
    try:
        client = SlackClient()
        items = client.get_pins(channel)
        if json_output:
            print(json.dumps({"items": items, "count": len(items)}, ensure_ascii=False, indent=2))
        else:
            console.print(f"Pins: {len(items)}")
    except SlackError as e:
        if json_output:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        raise typer.Exit(1)


# Cache directory for list schemas
_CLI_BASE = Path(__file__).resolve().parent.parent.parent  # → C:/claude/
LIST_SCHEMA_CACHE = _CLI_BASE / "json" / "slack_list_schemas.json"


def _load_schema_cache() -> dict:
    """Load cached list schemas."""
    if LIST_SCHEMA_CACHE.exists():
        try:
            return json.loads(LIST_SCHEMA_CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_schema_cache(cache: dict) -> None:
    """Save list schemas to cache."""
    LIST_SCHEMA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    LIST_SCHEMA_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_primary_column_id(list_id: str, cache: dict) -> Optional[str]:
    """Get primary column ID from cache."""
    if list_id in cache:
        schema = cache[list_id].get("schema", [])
        for col in schema:
            if col.get("is_primary_column") or col.get("key") == "name":
                return col.get("id")
    return None


@app.command("list-create")
def list_create(
    name: str = typer.Argument(..., help="List name/title"),
    description: str = typer.Option("", "--description", "-d", help="List description"),
    todo_mode: bool = typer.Option(True, "--todo/--no-todo", help="Create as todo list with completion/assignee/due date columns"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Create a new Slack List.

    Requires user token (xoxp-). Add 'user_token' to slack_credentials.json
    or run 'python -m lib.slack login --user' for OAuth.
    """
    from .client import SlackUserClient
    from .errors import SlackError, SlackAuthError

    try:
        client = SlackUserClient()
        result = client.create_list(name, description, todo_mode=todo_mode)

        list_id = result.get("list_id", "")
        metadata = result.get("list_metadata", {})
        schema = metadata.get("schema", [])

        # Cache schema for later use
        if list_id and schema:
            cache = _load_schema_cache()
            cache[list_id] = {"name": name, "schema": schema}
            _save_schema_cache(cache)

        if json_output:
            print(json.dumps({
                "ok": True,
                "list_id": list_id,
                "name": name,
                "columns": [col.get("name") for col in schema],
            }, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ List created![/green]")
            console.print(f"  List ID: {list_id}")
            console.print(f"  Name: {name}")
            if schema:
                cols = ", ".join(col.get("name", "") for col in schema)
                console.print(f"  Columns: {cols}")
    except SlackAuthError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Auth error: {e}[/red]")
            console.print("[yellow]Hint: Add 'user_token' to slack_credentials.json or run 'login --user'[/yellow]")
        raise typer.Exit(1)
    except SlackError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to create list: {e}[/red]")
        raise typer.Exit(1)


@app.command("list-add")
def list_add(
    list_id: str = typer.Argument(..., help="List ID (F...)"),
    title: str = typer.Argument(..., help="Item title/name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Add an item to a Slack List.

    Requires user token (xoxp-). The list must be created via 'list-create' first
    to cache the schema, or manually provide column_id.
    """
    from .client import SlackUserClient
    from .errors import SlackError, SlackAuthError

    try:
        client = SlackUserClient()

        # Get primary column ID from cache
        cache = _load_schema_cache()
        primary_col = _get_primary_column_id(list_id, cache)

        if not primary_col:
            # Fallback: try common default patterns or raise error
            if json_output:
                print(json.dumps({
                    "ok": False,
                    "error": f"Schema not cached for list {list_id}. Create list via 'list-create' first.",
                }, ensure_ascii=False))
            else:
                console.print(f"[red]✗ Schema not cached for list {list_id}[/red]")
                console.print("[yellow]Hint: Create list via 'list-create' to cache schema, or use 'list-register'[/yellow]")
            raise typer.Exit(1)

        result = client.add_list_item(list_id, {primary_col: title})

        if json_output:
            print(json.dumps({
                "ok": True,
                "list_id": list_id,
                "item": result.get("item", {}),
            }, ensure_ascii=False, indent=2))
        else:
            console.print("[green]✓ Item added![/green]")
            console.print(f"  List ID: {list_id}")
            console.print(f"  Title: {title}")
    except SlackAuthError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Auth error: {e}[/red]")
        raise typer.Exit(1)
    except SlackError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to add item: {e}[/red]")
        raise typer.Exit(1)


@app.command("list-register")
def list_register(
    list_id: str = typer.Argument(..., help="List ID (F...)"),
    primary_column_id: str = typer.Argument(..., help="Primary column ID (Col...)"),
    name: str = typer.Option("", "--name", "-n", help="List name for reference"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Register an existing Slack List schema for use with list-add.

    Use this to add items to lists not created via this CLI.
    Get the column ID from Slack's web interface (inspect network requests).
    """
    cache = _load_schema_cache()
    cache[list_id] = {
        "name": name or list_id,
        "schema": [{"id": primary_column_id, "key": "name", "is_primary_column": True}],
    }
    _save_schema_cache(cache)

    if json_output:
        print(json.dumps({
            "ok": True,
            "list_id": list_id,
            "primary_column_id": primary_column_id,
        }, ensure_ascii=False, indent=2))
    else:
        console.print("[green]✓ List schema registered![/green]")
        console.print(f"  List ID: {list_id}")
        console.print(f"  Primary Column: {primary_column_id}")
        console.print(f"  You can now use 'list-add {list_id} \"Item\"'")


@app.command("list-items")
def list_items(
    list_id: str = typer.Argument(..., help="List ID (F...)"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max items to retrieve"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Get items from a Slack List.

    Requires user token (xoxp-).
    """
    from .client import SlackUserClient
    from .errors import SlackError, SlackAuthError

    try:
        client = SlackUserClient()
        result = client.get_list_items(list_id, limit=limit)

        items = result.get("items", [])
        metadata = result.get("list_metadata", {})

        if json_output:
            print(json.dumps({
                "ok": True,
                "list_id": list_id,
                "count": len(items),
                "items": items,
                "metadata": metadata,
            }, ensure_ascii=False, indent=2))
        else:
            if not items:
                console.print("[yellow]No items in list.[/yellow]")
                return

            console.print(f"[bold]Items in list {list_id} ({len(items)}):[/bold]\n")
            for item in items:
                fields = item.get("fields", [])
                # Try to get the name/title field (fields is a list, not dict)
                name_value = "Unknown"
                for field in fields:
                    if field.get("key") == "name" and field.get("text"):
                        name_value = field.get("text")
                        break
                console.print(f"  • {name_value}")
    except SlackAuthError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Auth error: {e}[/red]")
        raise typer.Exit(1)
    except SlackError as e:
        if json_output:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            console.print(f"[red]✗ Failed to get items: {e}[/red]")
        raise typer.Exit(1)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
