import io
import asyncio
import argparse
import sys
import logging
from rich.console import Console
from rich.table import Table
import json

from app.db.session import async_session_factory
from app.services.discovery.orchestrator import DiscoveryOrchestrator
from app.models.search_profile import SearchProfile
from sqlalchemy import select

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
console = Console()

async def main():
    parser = argparse.ArgumentParser(description="Run Autonomous Discovery cycles")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Do not prepare applications or launch Playwright")
    parser.add_argument("--profile", type=str, help="Specific SearchProfile ID to run")
    args = parser.parse_args()

    if not args.once:
        console.print("[red]Only --once mode is supported in this script. Use Arq for continuous scheduling.[/red]")
        sys.exit(1)

    async with async_session_factory() as session:
        if args.profile:
            stmt = select(SearchProfile).where(SearchProfile.id == args.profile)
        else:
            stmt = select(SearchProfile).where(SearchProfile.enabled == True)
            
        result = await session.execute(stmt)
        profiles = result.scalars().all()

        if not profiles:
            console.print("[yellow]No active SearchProfiles found.[/yellow]")
            return

        orchestrator = DiscoveryOrchestrator(session)

        for profile in profiles:
            console.print(f"\n[bold cyan]Starting discovery for profile: '{profile.name}'[/bold cyan] (dry-run: {args.dry_run})")
            
            try:
                stats = await orchestrator.run_search_profile(profile.id, dry_run=args.dry_run)
                
                table = Table(title=f"Discovery Results: {profile.name}")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", justify="right")
                
                table.add_row("Queries Generated", str(stats["queries_generated"]))
                table.add_row("Providers Used", ", ".join(stats["providers_used"]))
                table.add_row("Raw Results", str(stats["raw_results"]))
                table.add_row("Unique Jobs", str(stats["unique_jobs"]))
                table.add_row("Eligible (Pre-filter)", str(stats["eligible"]))
                table.add_row("Ineligible (Pre-filter)", str(stats["ineligible"]))
                table.add_row("Shortlisted (LLM Match)", str(stats["shortlisted"]))
                table.add_row("Selected for Preparation", str(stats["selected_for_prep"]))
                
                console.print(table)
                
                if stats["skipped_reasons"]:
                    console.print("\n[yellow]Skipped Reasons:[/yellow]")
                    for reason, count in stats["skipped_reasons"].items():
                        console.print(f"  - {reason}: {count}")
                        
            except Exception as e:
                console.print(f"[red]Failed to run profile {profile.name}: {e}[/red]")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
