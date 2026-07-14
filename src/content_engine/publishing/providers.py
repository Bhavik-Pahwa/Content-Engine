"""Publishing provider implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
import re
import time

from content_engine.providers import ProviderMetadata
from content_engine.publishing.models import AuthenticationRequiredError, PublishRequest, PublishResult, PublishingProviderError


class Publisher(Protocol):
    metadata: ProviderMetadata

    def publish(self, request: PublishRequest) -> PublishResult:
        """Publish a prepared content asset."""


class MockPublisher:
    metadata = ProviderMetadata(
        name="mock_publisher",
        provider_type="publisher",
        version="0.1.0",
        requires_network=False,
        cost_profile="free",
        capabilities=("dry_run", "testing"),
    )

    def publish(self, request: PublishRequest) -> PublishResult:
        request.screenshot_dir.mkdir(parents=True, exist_ok=True)
        before = request.screenshot_dir / f"{request.attempt_id}_before.txt"
        after = request.screenshot_dir / f"{request.attempt_id}_after.txt"
        before.write_text("mock before publish\n", encoding="utf-8")
        after.write_text("mock after publish\n", encoding="utf-8")
        return PublishResult(
            published=not request.dry_run,
            status_url=f"https://www.linkedin.com/feed/update/{request.attempt_id}" if not request.dry_run else None,
            screenshot_before_path=before,
            screenshot_after_path=after,
            metadata={"simulated": True, "image_attached": request.image is not None},
        )


class LinkedInPublisher:
    metadata = ProviderMetadata(
        name="linkedin",
        provider_type="publisher",
        version="0.1.0",
        requires_network=True,
        cost_profile="free",
        capabilities=("linkedin", "playwright", "persistent_context"),
    )

    def open_login_session(self, *, session_dir: Path, timeout_seconds: float) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PublishingProviderError(
                "Playwright is not installed. Install with: .venv/bin/python -m pip install -e '.[publish]' "
                "and then run: .venv/bin/python -m playwright install chromium"
            ) from exc

        session_dir.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(session_dir),
                headless=False,
                timeout=timeout_seconds * 1000,
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(timeout_seconds * 1000)
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            input("Log in to LinkedIn in the browser window, then press Enter here to save the session...")
            context.close()

    def publish(self, request: PublishRequest) -> PublishResult:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise PublishingProviderError(
                "Playwright is not installed. Install with: .venv/bin/python -m pip install -e '.[publish]' "
                "and then run: .venv/bin/python -m playwright install chromium"
            ) from exc

        request.screenshot_dir.mkdir(parents=True, exist_ok=True)
        request.session_dir.mkdir(parents=True, exist_ok=True)
        before = request.screenshot_dir / f"{request.attempt_id}_before.png"
        after = request.screenshot_dir / f"{request.attempt_id}_after.png"
        error = request.screenshot_dir / f"{request.attempt_id}_error.png"
        started = time.monotonic()
        try:
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(request.session_dir),
                    headless=request.headless,
                    timeout=request.timeout_seconds * 1000,
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(request.timeout_seconds * 1000)
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                page.screenshot(path=str(before), full_page=True)
                if _login_required(page):
                    context.close()
                    raise AuthenticationRequiredError(
                        f"LinkedIn login required. Run publish once, log in manually in the opened browser, then retry."
                    )
                if request.dry_run:
                    context.close()
                    return PublishResult(
                        published=False,
                        screenshot_before_path=before,
                        screenshot_after_path=before,
                        metadata={"dry_run": True, "duration_seconds": time.monotonic() - started},
                    )
                _compose_post(
                    page,
                    request.text,
                    request.image.file_path if request.image else None,
                    author_name=request.linkedin_author_name,
                    target_page_name=request.linkedin_target_page_name,
                )
                page.screenshot(path=str(after), full_page=True)
                url = page.url if "linkedin.com" in page.url else None
                context.close()
                return PublishResult(
                    published=True,
                    status_url=url,
                    screenshot_before_path=before,
                    screenshot_after_path=after,
                    metadata={
                        "duration_seconds": time.monotonic() - started,
                        "image_attached": request.image is not None,
                        "linkedin_target_page_name": request.linkedin_target_page_name,
                        "headless": request.headless,
                    },
                )
        except AuthenticationRequiredError:
            raise
        except PlaywrightTimeoutError as exc:
            _safe_error_screenshot(locals().get("page"), error)
            raise PublishingProviderError(f"LinkedIn publishing timed out: {exc}") from exc
        except Exception as exc:
            _safe_error_screenshot(locals().get("page"), error)
            raise PublishingProviderError(f"LinkedIn publishing failed: {exc}") from exc


def _login_required(page) -> bool:
    url = page.url.lower()
    if "login" in url or "checkpoint" in url:
        return True
    try:
        return page.get_by_text("Sign in", exact=False).count() > 0
    except Exception:
        return False


def _compose_post(
    page,
    text: str,
    image_path: Path | None,
    *,
    author_name: str | None = None,
    target_page_name: str | None = None,
) -> None:
    composer = _open_composer(page)
    if target_page_name:
        _select_posting_identity(page, composer, author_name=author_name, target_page_name=target_page_name)
        composer = _composer_scope(page)
    if image_path is not None:
        _attach_image(page, composer, image_path)
        _complete_media_editor(page)
        composer = _composer_scope(page)
    _fill_post_text(composer, text)
    publish_button = _publish_button(composer)
    publish_button.wait_for(state="visible")
    publish_button.click()
    page.wait_for_timeout(5_000)


def _open_composer(page):
    start_button = page.get_by_text("Start a post", exact=False).first
    start_button.click()
    try:
        page.get_by_text("What do you want to talk about?", exact=False).wait_for(state="visible", timeout=30_000)
    except Exception:
        page.locator("[contenteditable='true']").first.wait_for(state="visible", timeout=30_000)
    return _composer_scope(page)


def _fill_post_text(composer, text: str) -> None:
    editor = composer.locator("[contenteditable='true']").first
    editor.wait_for(state="visible")
    editor.fill(text)


def _select_posting_identity(page, composer, *, author_name: str | None, target_page_name: str) -> None:
    if author_name:
        author_pattern = _loose_label_pattern(author_name)
        if not _click_first_visible(
            (
                composer.get_by_role("button", name=author_pattern),
                composer.get_by_text(author_pattern),
            )
        ):
            raise PublishingProviderError(f"LinkedIn posting identity control was not found for {author_name!r}")
        page.wait_for_timeout(750)

        identity_dialog = _composer_scope(page)
        if not _click_first_visible(
            (
                identity_dialog.get_by_role("button", name=author_pattern),
                identity_dialog.get_by_text(author_pattern),
                page.get_by_role("button", name=author_pattern),
                page.get_by_text(author_pattern),
            )
        ) and not _click_post_settings_author_row(page, author_name):
            raise PublishingProviderError(f"LinkedIn posting identity picker was not found for {author_name!r}")
        page.wait_for_timeout(750)

    page_pattern = _loose_label_pattern(target_page_name)
    if not _click_first_visible(
        (
            page.get_by_role("button", name=page_pattern),
            page.get_by_role("option", name=page_pattern),
            page.get_by_text(page_pattern),
        )
    ):
        raise PublishingProviderError(f"LinkedIn target page option was not found: {target_page_name}")
    page.wait_for_timeout(500)
    _save_posting_identity(page)
    page.wait_for_timeout(500)
    _finish_post_settings(page)
    page.wait_for_timeout(1_000)


def _save_posting_identity(page) -> None:
    save_button = page.get_by_role("button", name=re.compile("^\\s*save\\s*$", re.IGNORECASE)).last
    try:
        if save_button.count() > 0 and save_button.is_visible():
            save_button.click(timeout=5_000, force=True)
            return
    except Exception:
        pass
    if not _click_first_visible((page.get_by_text("Save", exact=True),)):
        raise PublishingProviderError("LinkedIn posting identity save button was not found")


def _finish_post_settings(page) -> None:
    done_button = page.get_by_role("button", name=re.compile("^\\s*done\\s*$", re.IGNORECASE)).last
    try:
        if done_button.count() > 0 and done_button.is_visible():
            done_button.click(timeout=5_000, force=True)
            return
    except Exception:
        pass
    if not _click_first_visible((page.get_by_text("Done", exact=True),)):
        raise PublishingProviderError("LinkedIn post settings Done button was not found")


def _click_post_settings_author_row(page, author_name: str) -> bool:
    dialogs = page.locator("div[role='dialog']")
    for index in range(dialogs.count() - 1, -1, -1):
        dialog = dialogs.nth(index)
        try:
            text = dialog.inner_text(timeout=1_000)
        except Exception:
            continue
        if "Post settings" not in text or author_name.lower() not in text.lower():
            continue
        box = dialog.bounding_box()
        if box is None:
            continue
        # LinkedIn's author row in Post settings is not exposed as a stable button.
        # Click the right side of the first row where the chevron opens identity selection.
        page.mouse.click(box["x"] + box["width"] - 24, box["y"] + 88)
        return True
    return False


def _click_first_visible(candidates) -> bool:
    for candidate in candidates:
        try:
            count = candidate.count()
        except Exception:
            continue
        for index in range(count):
            item = candidate.nth(index)
            try:
                if item.is_visible():
                    item.click(timeout=3_000)
                    return True
            except Exception:
                continue
    return False


def _click_optional(page, labels: tuple[str, ...]) -> bool:
    for label in labels:
        button = page.get_by_role("button", name=re.compile(f"^\\s*{re.escape(label)}\\s*$", re.IGNORECASE))
        if _click_first_visible((button, page.get_by_text(label, exact=True))):
            return True
    return False


def _loose_label_pattern(label: str) -> re.Pattern[str]:
    pieces = [re.escape(piece) for piece in re.split(r"\s+", label.strip()) if piece]
    return re.compile(r"\s*".join(pieces), re.IGNORECASE)


def _composer_scope(page):
    dialogs = page.locator("div[role='dialog']")
    try:
        for index in range(dialogs.count() - 1, -1, -1):
            dialog = dialogs.nth(index)
            if dialog.is_visible() and dialog.bounding_box() is not None:
                return dialog
    except Exception:
        pass
    return page


def _attach_image(page, composer, image_path: Path) -> None:
    if not image_path.exists():
        raise PublishingProviderError(f"LinkedIn image file does not exist: {image_path}")

    if _set_existing_file_input(page, image_path) or _set_existing_file_input(composer, image_path):
        _wait_for_uploaded_media(composer)
        return

    media_controls = (
        composer.get_by_label(re.compile("add media|media|photo|image", re.IGNORECASE)),
        composer.get_by_text(re.compile("^\\s*(add media|media|photo)\\s*$", re.IGNORECASE)),
        composer.locator(
            "button[aria-label*='media' i], button[aria-label*='photo' i], "
            "button[aria-label*='image' i], button:has(svg[data-test-icon*='image'])"
        ),
        page.get_by_text(re.compile("^\\s*photo\\s*$", re.IGNORECASE)),
    )
    for control in media_controls:
        try:
            if control.count() == 0:
                continue
            with page.expect_file_chooser(timeout=3_000) as chooser:
                control.first.click()
            chooser.value.set_files(str(image_path))
            _wait_for_uploaded_media(composer)
            return
        except Exception:
            if _set_existing_file_input(page, image_path) or _set_existing_file_input(composer, image_path):
                _wait_for_uploaded_media(composer)
                return
            continue
    raise PublishingProviderError("LinkedIn image upload control was not found")


def _set_existing_file_input(scope, image_path: Path) -> bool:
    try:
        file_inputs = scope.locator("input[type='file']")
        if file_inputs.count() == 0:
            return False
        file_inputs.first.set_input_files(str(image_path))
        return True
    except Exception:
        return False


def _wait_for_uploaded_media(composer) -> None:
    try:
        composer.locator("img, video, [data-test-media-attachment]").first.wait_for(state="visible", timeout=15_000)
    except Exception:
        # LinkedIn changes upload preview markup frequently. If set_input_files succeeded,
        # continue and let the final publish step determine whether the page accepted it.
        return


def _complete_media_editor(page) -> None:
    for label in ("Next", "Done"):
        dialog = _composer_scope(page)
        button = dialog.get_by_text(label, exact=True).last
        try:
            if button.count() == 0 or not button.is_visible():
                continue
            button.click()
            page.wait_for_timeout(1_000)
        except Exception:
            continue


def _publish_button(composer):
    candidates = (
        composer.get_by_role("button", name=re.compile("^\\s*post\\s*$", re.IGNORECASE)),
        composer.get_by_text("Post", exact=True),
        composer.locator("button[aria-label*='post' i]"),
    )
    for candidate in candidates:
        try:
            if candidate.count() > 0:
                return candidate.last
        except Exception:
            continue
    return composer.get_by_text("Post", exact=True).last


def _safe_error_screenshot(page, path: Path) -> None:
    try:
        if page is not None:
            page.screenshot(path=str(path), full_page=True)
    except Exception:
        return
