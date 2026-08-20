"""PDF document renderers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
import structlog
from abc import ABC, abstractmethod
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.exceptions import GenerationError, TemplateError

logger = structlog.get_logger(__name__)


class BasePDFRenderer(ABC):
    @abstractmethod
    async def render(
        self,
        template_name: str,
        context: dict[str, Any],
        output_path: Path,
    ) -> Path:
        pass


class WeasyPrintPDFRenderer(BasePDFRenderer):
    """Legacy renderer using WeasyPrint (blocking I/O offloaded to thread)."""
    
    def __init__(self, templates_dir: Path = Path("templates")) -> None:
        self._templates_dir = templates_dir

    def _render_sync(self, template_name: str, context: dict[str, Any], output_path: Path) -> Path:
        import weasyprint
        
        env = Environment(
            loader=FileSystemLoader(self._templates_dir / "resume"),
            autoescape=select_autoescape(["html", "xml"]),
        )
        try:
            template = env.get_template(f"{template_name}/template.html")
        except Exception as exc:
            raise TemplateError(f"Template '{template_name}' not found: {exc}") from exc

        html_out = template.render(**context)
        
        try:
            # Weasyprint requires base_url for assets like images/css
            base_url = (self._templates_dir / "resume" / template_name).resolve().as_uri()
            weasyprint.HTML(string=html_out, base_url=base_url).write_pdf(str(output_path))
        except Exception as exc:
            raise GenerationError(f"WeasyPrint rendering failed: {exc}") from exc

        return output_path

    async def render(self, template_name: str, context: dict[str, Any], output_path: Path) -> Path:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._render_sync, template_name, context, output_path)


class PlaywrightPDFRenderer(BasePDFRenderer):
    """Modern renderer using Playwright Chromium."""
    
    def __init__(self, templates_dir: Path = Path("templates")) -> None:
        self._templates_dir = templates_dir

    async def render(self, template_name: str, context: dict[str, Any], output_path: Path) -> Path:
        from playwright.async_api import async_playwright
        
        env = Environment(
            loader=FileSystemLoader(self._templates_dir / "resume"),
            autoescape=select_autoescape(["html", "xml"]),
        )
        try:
            template = env.get_template(f"{template_name}/template.html")
        except Exception as exc:
            raise TemplateError(f"Template '{template_name}' not found: {exc}") from exc

        html_content = template.render(**context)
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="networkidle")
                await page.pdf(path=str(output_path), format="A4", print_background=True)
                await browser.close()
        except Exception as exc:
            raise GenerationError(f"Playwright rendering failed: {exc}") from exc
            
        return output_path

# Preserve backward compatibility for existing code that imports PDFRenderer
PDFRenderer = WeasyPrintPDFRenderer
