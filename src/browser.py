"""
browser.py — Playwright browser lifecycle management.

Provides a reusable async browser manager that launches once and can fetch
multiple URLs without restarting. Every fetch returns a structured PageResult
regardless of success or failure — the caller never sees an unhandled exception.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
)

from src.config import settings
from src.utils import get_logger

logger = get_logger(__name__)

# Realistic desktop user-agent to reduce bot-detection blocks.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# HTTP status codes we treat as explicit failures.
HTTP_ERROR_CODES = frozenset({403, 404, 500, 502, 503})


@dataclass(frozen=True)
class PageResult:
    """Structured result of a single page fetch.

    Every call to ``BrowserManager.fetch`` returns one of these — on success
    *and* on failure — so downstream code never needs to handle raw exceptions.
    """

    requested_url: str
    final_url: str = ""
    page_title: str = ""
    html: str = ""
    status_code: int = 0
    success: bool = False
    error: str = ""


class BrowserManager:
    """Reusable Playwright browser that stays alive across multiple fetches.

    Usage (as async context manager)::

        async with BrowserManager() as bm:
            result = await bm.fetch("https://example.com")
            print(result.success, result.page_title)

    Or manual lifecycle::

        bm = BrowserManager()
        await bm.launch()
        result = await bm.fetch("https://example.com")
        await bm.close()
    """

    def __init__(
        self,
        headless: bool | None = None,
        timeout_ms: int | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._headless = headless if headless is not None else settings.browser_headless
        self._timeout_ms = timeout_ms if timeout_ms is not None else settings.browser_timeout_ms
        self._user_agent = user_agent

        # Playwright runtime objects — populated by launch().
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    # ------------------------------------------------------------------
    # Async context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> Self:
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def launch(self) -> None:
        """Start Playwright and launch a Chromium browser instance."""
        if self._browser is not None:
            logger.debug("Browser already running — skipping launch")
            return

        logger.info(
            "Launching Chromium (headless=%s, timeout=%dms)",
            self._headless,
            self._timeout_ms,
        )
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        logger.info("Browser launched successfully")

    async def close(self) -> None:
        """Gracefully shut down the browser and Playwright runtime."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
            logger.info("Browser closed")

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
            logger.debug("Playwright runtime stopped")

    # ------------------------------------------------------------------
    # Fetching
    # ------------------------------------------------------------------

    async def fetch(self, url: str) -> PageResult:
        """Navigate to *url* and return a structured :class:`PageResult`.

        Creates a fresh browser context + page for isolation, then tears
        them down after the fetch.  The browser itself stays alive.

        Args:
            url: The URL to fetch.  If no scheme is provided, ``https://``
                 is prepended automatically.

        Returns:
            A :class:`PageResult` — always, even on failure.
        """
        if self._browser is None:
            raise RuntimeError(
                "Browser not launched. Call launch() or use 'async with BrowserManager()'."
            )

        # Normalise URL.
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        context: BrowserContext | None = None
        page: Page | None = None

        try:
            # Fresh context per fetch — isolated cookies/storage.
            context = await self._browser.new_context(
                user_agent=self._user_agent,
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            page = await context.new_page()

            logger.info("Fetching: %s", url)

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )

            # Wait a bit for JS to render remaining content.
            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeout:
                # networkidle is best-effort; domcontentloaded already succeeded.
                logger.debug("networkidle timed out for %s — continuing", url)

            status_code = response.status if response else 0
            final_url = page.url
            page_title = await page.title()
            html = await page.content()

            # Check for HTTP-level errors.
            if status_code in HTTP_ERROR_CODES:
                msg = f"HTTP {status_code} for {url}"
                logger.warning(msg)
                return PageResult(
                    requested_url=url,
                    final_url=final_url,
                    page_title=page_title,
                    html=html,
                    status_code=status_code,
                    success=False,
                    error=msg,
                )

            logger.info(
                "Fetched OK: %s -> %s (HTTP %d, title=%r)",
                url,
                final_url,
                status_code,
                page_title,
            )
            return PageResult(
                requested_url=url,
                final_url=final_url,
                page_title=page_title,
                html=html,
                status_code=status_code,
                success=True,
            )

        except PlaywrightTimeout:
            msg = f"Timeout after {self._timeout_ms}ms navigating to {url}"
            logger.error(msg)
            return PageResult(requested_url=url, error=msg)

        except PlaywrightError as exc:
            msg = f"Playwright error for {url}: {exc}"
            logger.error(msg)
            return PageResult(requested_url=url, error=msg)

        except Exception as exc:
            msg = f"Unexpected error fetching {url}: {exc}"
            logger.error(msg, exc_info=True)
            return PageResult(requested_url=url, error=msg)

        finally:
            # Tear down the page and context; browser stays alive.
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
            if context is not None:
                try:
                    await context.close()
                except Exception:
                    pass
