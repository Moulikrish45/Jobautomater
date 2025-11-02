"""Browser automation service using Playwright for job application submission."""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import json
import base64

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import settings
from app.services.retry_service import (
    retry_service, 
    fallback_strategy,
    RetryConfig, 
    RetryStrategy,
    BrowserError,
    NavigationError,
    FormError,
    NetworkError,
    PortalChangeError,
    ErrorSeverity
)


class BrowserAutomationError(Exception):
    """Base exception for browser automation errors."""
    pass


class FormDetectionError(BrowserAutomationError):
    """Exception for form detection failures."""
    pass


class FileUploadError(BrowserAutomationError):
    """Exception for file upload failures."""
    pass


class FormFieldMapper:
    """Utility class for detecting and mapping form fields."""
    
    # Common field selectors for job application forms
    FIELD_SELECTORS = {
        "first_name": [
            'input[name*="first" i][name*="name" i]',
            'input[id*="first" i][id*="name" i]',
            'input[placeholder*="first" i][placeholder*="name" i]',
            'input[name="firstName"]',
            'input[id="firstName"]'
        ],
        "last_name": [
            'input[name*="last" i][name*="name" i]',
            'input[id*="last" i][id*="name" i]',
            'input[placeholder*="last" i][placeholder*="name" i]',
            'input[name="lastName"]',
            'input[id="lastName"]'
        ],
        "full_name": [
            'input[name*="name" i]:not([name*="first" i]):not([name*="last" i])',
            'input[id*="name" i]:not([id*="first" i]):not([id*="last" i])',
            'input[placeholder*="full" i][placeholder*="name" i]',
            'input[name="name"]',
            'input[id="name"]'
        ],
        "email": [
            'input[type="email"]',
            'input[name*="email" i]',
            'input[id*="email" i]',
            'input[placeholder*="email" i]'
        ],
        "phone": [
            'input[type="tel"]',
            'input[name*="phone" i]',
            'input[id*="phone" i]',
            'input[placeholder*="phone" i]',
            'input[name*="mobile" i]',
            'input[id*="mobile" i]'
        ],
        "address": [
            'input[name*="address" i]',
            'input[id*="address" i]',
            'textarea[name*="address" i]',
            'textarea[id*="address" i]'
        ],
        "city": [
            'input[name*="city" i]',
            'input[id*="city" i]',
            'input[placeholder*="city" i]'
        ],
        "state": [
            'select[name*="state" i]',
            'select[id*="state" i]',
            'input[name*="state" i]',
            'input[id*="state" i]'
        ],
        "zip_code": [
            'input[name*="zip" i]',
            'input[id*="zip" i]',
            'input[name*="postal" i]',
            'input[id*="postal" i]',
            'input[placeholder*="zip" i]'
        ],
        "resume_upload": [
            'input[type="file"][name*="resume" i]',
            'input[type="file"][id*="resume" i]',
            'input[type="file"][name*="cv" i]',
            'input[type="file"][id*="cv" i]',
            'input[type="file"]'
        ],
        "cover_letter": [
            'textarea[name*="cover" i]',
            'textarea[id*="cover" i]',
            'textarea[name*="letter" i]',
            'textarea[id*="letter" i]',
            'input[type="file"][name*="cover" i]'
        ],
        "linkedin": [
            'input[name*="linkedin" i]',
            'input[id*="linkedin" i]',
            'input[placeholder*="linkedin" i]'
        ],
        "website": [
            'input[name*="website" i]',
            'input[id*="website" i]',
            'input[name*="portfolio" i]',
            'input[id*="portfolio" i]'
        ],
        "experience_years": [
            'select[name*="experience" i]',
            'select[id*="experience" i]',
            'input[name*="experience" i]',
            'input[id*="experience" i]'
        ]
    }
    
    @classmethod
    async def detect_form_fields(cls, page: Page) -> Dict[str, Any]:
        """Detect form fields on the current page.
        
        Args:
            page: Playwright page object
            
        Returns:
            Dictionary mapping field types to detected elements
        """
        detected_fields = {}
        
        for field_type, selectors in cls.FIELD_SELECTORS.items():
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # Get element attributes
                        attributes = await element.evaluate("""
                            (element) => {
                                return {
                                    tagName: element.tagName,
                                    type: element.type || '',
                                    name: element.name || '',
                                    id: element.id || '',
                                    placeholder: element.placeholder || '',
                                    required: element.required || false,
                                    visible: element.offsetParent !== null
                                };
                            }
                        """)
                        
                        if attributes['visible']:
                            detected_fields[field_type] = {
                                'selector': selector,
                                'element': element,
                                'attributes': attributes
                            }
                            break
                            
                except Exception as e:
                    # Continue to next selector if this one fails
                    continue
        
        return detected_fields
    
    @classmethod
    async def detect_submit_button(cls, page: Page) -> Optional[Dict[str, Any]]:
        """Detect the submit button for the form.
        
        Args:
            page: Playwright page object
            
        Returns:
            Submit button information or None
        """
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send")',
            'a:has-text("Submit")',
            'a:has-text("Apply")'
        ]
        
        for selector in submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    attributes = await element.evaluate("""
                        (element) => {
                            return {
                                tagName: element.tagName,
                                type: element.type || '',
                                text: element.textContent || '',
                                visible: element.offsetParent !== null
                            };
                        }
                    """)
                    
                    if attributes['visible']:
                        return {
                            'selector': selector,
                            'element': element,
                            'attributes': attributes
                        }
                        
            except Exception:
                continue
        
        return None


class BrowserManager:
    """Manages Playwright browser instances and contexts."""
    
    def __init__(self):
        """Initialize browser manager."""
        self.logger = logging.getLogger(__name__)
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: List[BrowserContext] = []
    
    async def start(self, headless: bool = True, browser_type: str = "chromium") -> None:
        """Start Playwright and browser.
        
        Args:
            headless: Whether to run browser in headless mode
            browser_type: Browser type (chromium, firefox, webkit)
        """
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser
            if browser_type == "firefox":
                self.browser = await self.playwright.firefox.launch(headless=headless)
            elif browser_type == "webkit":
                self.browser = await self.playwright.webkit.launch(headless=headless)
            else:  # chromium (default)
                self.browser = await self.playwright.chromium.launch(
                    headless=headless,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
            
            self.logger.info(f"Browser started: {browser_type} (headless: {headless})")
            
        except Exception as e:
            self.logger.error(f"Failed to start browser: {e}")
            raise BrowserAutomationError(f"Browser startup failed: {e}")
    
    async def create_context(
        self,
        user_agent: Optional[str] = None,
        viewport: Optional[Dict[str, int]] = None
    ) -> BrowserContext:
        """Create a new browser context.
        
        Args:
            user_agent: Custom user agent string
            viewport: Viewport size dictionary
            
        Returns:
            Browser context
        """
        if not self.browser:
            raise BrowserAutomationError("Browser not started")
        
        try:
            context_options = {}
            
            if user_agent:
                context_options['user_agent'] = user_agent
            
            if viewport:
                context_options['viewport'] = viewport
            else:
                context_options['viewport'] = {'width': 1920, 'height': 1080}
            
            context = await self.browser.new_context(**context_options)
            self.contexts.append(context)
            
            self.logger.info(f"Created browser context (total: {len(self.contexts)})")
            
            return context
            
        except Exception as e:
            self.logger.error(f"Failed to create context: {e}")
            raise BrowserAutomationError(f"Context creation failed: {e}")
    
    async def close_context(self, context: BrowserContext) -> None:
        """Close a browser context.
        
        Args:
            context: Browser context to close
        """
        try:
            await context.close()
            if context in self.contexts:
                self.contexts.remove(context)
            
            self.logger.info(f"Closed browser context (remaining: {len(self.contexts)})")
            
        except Exception as e:
            self.logger.warning(f"Failed to close context: {e}")
    
    async def stop(self) -> None:
        """Stop browser and cleanup resources."""
        try:
            # Close all contexts
            for context in self.contexts.copy():
                await self.close_context(context)
            
            # Close browser
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            # Stop playwright
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
            
            self.logger.info("Browser stopped and resources cleaned up")
            
        except Exception as e:
            self.logger.error(f"Error during browser cleanup: {e}")


class FileUploadHandler:
    """Handles file uploads with error handling and validation."""
    
    def __init__(self):
        """Initialize file upload handler."""
        self.logger = logging.getLogger(__name__)
    
    async def upload_file(
        self,
        page: Page,
        file_input_selector: str,
        file_path: str,
        timeout: int = 30000,
        retry_config: Optional[RetryConfig] = None
    ) -> bool:
        """Upload a file to a file input element with retry logic.
        
        Args:
            page: Playwright page object
            file_input_selector: CSS selector for file input
            file_path: Path to file to upload
            timeout: Timeout in milliseconds
            retry_config: Optional retry configuration
            
        Returns:
            True if upload successful
            
        Raises:
            FileUploadError: If upload fails
        """
        if retry_config is None:
            retry_config = RetryConfig(
                max_attempts=3,
                strategy=RetryStrategy.LINEAR_BACKOFF,
                base_delay=1.0
            )
        
        async def _upload():
            try:
                # Validate file exists
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    raise FileUploadError(f"File not found: {file_path}", ErrorSeverity.HIGH)
                
                # Find file input element with fallback
                file_input = await fallback_strategy.find_element_with_fallback(
                    page, file_input_selector, 'file_input', timeout
                )
                
                if not file_input:
                    raise FileUploadError(f"File input not found: {file_input_selector}", ErrorSeverity.MEDIUM)
                
                # Upload file
                await file_input.set_input_files(str(file_path_obj))
                
                # Verify upload
                uploaded_files = await file_input.evaluate("element => element.files.length")
                
                if uploaded_files > 0:
                    self.logger.info(f"Successfully uploaded file: {file_path}")
                    return True
                else:
                    raise FileUploadError("File upload verification failed", ErrorSeverity.MEDIUM)
                    
            except PlaywrightTimeoutError as e:
                raise FileUploadError(f"Timeout waiting for file input: {file_input_selector}", ErrorSeverity.MEDIUM)
            except FileUploadError:
                raise  # Re-raise FileUploadError as-is
            except Exception as e:
                self.logger.error(f"File upload failed: {e}")
                raise FileUploadError(f"File upload failed: {e}", ErrorSeverity.MEDIUM)
        
        return await retry_service.retry_with_backoff(
            _upload,
            config=retry_config,
            context={"file_path": file_path, "selector": file_input_selector, "operation": "file_upload"}
        )
    
    async def upload_resume(
        self,
        page: Page,
        resume_path: str,
        timeout: int = 30000
    ) -> bool:
        """Upload resume file using auto-detected file input.
        
        Args:
            page: Playwright page object
            resume_path: Path to resume file
            timeout: Timeout in milliseconds
            
        Returns:
            True if upload successful
        """
        try:
            # Detect resume upload field
            form_fields = await FormFieldMapper.detect_form_fields(page)
            
            if 'resume_upload' not in form_fields:
                raise FileUploadError("Resume upload field not found")
            
            resume_field = form_fields['resume_upload']
            selector = resume_field['selector']
            
            return await self.upload_file(page, selector, resume_path, timeout)
            
        except Exception as e:
            self.logger.error(f"Resume upload failed: {e}")
            raise FileUploadError(f"Resume upload failed: {e}")


class BrowserAutomationService:
    """Main service for browser automation with Playwright."""
    
    def __init__(self):
        """Initialize browser automation service."""
        self.logger = logging.getLogger(__name__)
        self.browser_manager = BrowserManager()
        self.file_upload_handler = FileUploadHandler()
        self._initialized = False
    
    async def initialize(
        self,
        headless: bool = True,
        browser_type: str = "chromium"
    ) -> None:
        """Initialize the browser automation service.
        
        Args:
            headless: Whether to run browser in headless mode
            browser_type: Browser type to use
        """
        if self._initialized:
            return
        
        try:
            await self.browser_manager.start(headless=headless, browser_type=browser_type)
            self._initialized = True
            self.logger.info("Browser automation service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize browser automation: {e}")
            raise BrowserAutomationError(f"Initialization failed: {e}")
    
    async def create_session(
        self,
        user_agent: Optional[str] = None,
        viewport: Optional[Dict[str, int]] = None
    ) -> Tuple[BrowserContext, Page]:
        """Create a new browser session (context + page).
        
        Args:
            user_agent: Custom user agent
            viewport: Viewport size
            
        Returns:
            Tuple of (context, page)
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            context = await self.browser_manager.create_context(
                user_agent=user_agent,
                viewport=viewport
            )
            
            page = await context.new_page()
            
            # Set default timeouts
            page.set_default_timeout(30000)  # 30 seconds
            page.set_default_navigation_timeout(60000)  # 60 seconds
            
            self.logger.info("Created new browser session")
            
            return context, page
            
        except Exception as e:
            self.logger.error(f"Failed to create session: {e}")
            raise BrowserAutomationError(f"Session creation failed: {e}")
    
    async def navigate_to_job(
        self,
        page: Page,
        job_url: str,
        wait_for_load: bool = True,
        retry_config: Optional[RetryConfig] = None
    ) -> bool:
        """Navigate to job posting URL with retry logic.
        
        Args:
            page: Playwright page object
            job_url: Job posting URL
            wait_for_load: Whether to wait for page load
            retry_config: Optional retry configuration
            
        Returns:
            True if navigation successful
        """
        if retry_config is None:
            retry_config = RetryConfig(
                max_attempts=3,
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                base_delay=2.0,
                max_delay=10.0
            )
        
        async def _navigate():
            try:
                self.logger.info(f"Navigating to job: {job_url}")
                
                # Navigate to URL
                response = await page.goto(job_url, timeout=60000)
                
                if not response:
                    raise NavigationError("No response received from server", ErrorSeverity.MEDIUM)
                
                if response.status >= 500:
                    raise NavigationError(f"Server error: HTTP {response.status}", ErrorSeverity.MEDIUM)
                elif response.status >= 400:
                    raise NavigationError(f"Client error: HTTP {response.status}", ErrorSeverity.HIGH)
                
                if wait_for_load:
                    # Wait for page to be fully loaded
                    await page.wait_for_load_state('networkidle', timeout=30000)
                
                self.logger.info(f"Successfully navigated to: {job_url}")
                return True
                
            except PlaywrightTimeoutError as e:
                raise NavigationError(f"Timeout navigating to {job_url}: {e}", ErrorSeverity.MEDIUM)
            except Exception as e:
                if "net::" in str(e).lower() or "connection" in str(e).lower():
                    raise NetworkError(f"Network error: {e}", ErrorSeverity.MEDIUM)
                else:
                    raise NavigationError(f"Navigation failed: {e}", ErrorSeverity.HIGH)
        
        try:
            return await retry_service.retry_with_backoff(
                _navigate,
                config=retry_config,
                context={"job_url": job_url, "operation": "navigation"}
            )
        except Exception as e:
            self.logger.error(f"Navigation failed after retries: {e}")
            return False
    
    async def detect_application_form(
        self, 
        page: Page,
        retry_config: Optional[RetryConfig] = None
    ) -> Dict[str, Any]:
        """Detect job application form on the current page with fallback strategies.
        
        Args:
            page: Playwright page object
            retry_config: Optional retry configuration
            
        Returns:
            Form detection results
        """
        if retry_config is None:
            retry_config = RetryConfig(
                max_attempts=2,
                strategy=RetryStrategy.FIXED_DELAY,
                base_delay=1.0
            )
        
        async def _detect_form():
            try:
                self.logger.info("Detecting application form...")
                
                # Detect form fields with fallback
                form_fields = await self._detect_form_fields_with_fallback(page)
                
                # Detect submit button with fallback
                submit_button = await self._detect_submit_button_with_fallback(page)
                
                # Check for portal changes
                expected_elements = ['form', 'input[type="email"]', 'button[type="submit"]']
                change_detection = await fallback_strategy.detect_portal_changes(page, expected_elements)
                
                # Check if this looks like an application form
                required_fields = ['email']  # Minimum requirement
                has_required_fields = any(field in form_fields for field in required_fields)
                
                form_info = {
                    'detected': has_required_fields,
                    'fields': form_fields,
                    'submit_button': submit_button,
                    'field_count': len(form_fields),
                    'has_file_upload': 'resume_upload' in form_fields,
                    'portal_changes': change_detection,
                    'confidence_score': change_detection.get('confidence_score', 1.0),
                    'detected_at': datetime.utcnow().isoformat()
                }
                
                if form_info['detected']:
                    self.logger.info(f"Application form detected with {len(form_fields)} fields")
                else:
                    if change_detection.get('changes_detected'):
                        raise PortalChangeError(
                            f"Portal interface may have changed (confidence: {change_detection.get('confidence_score', 0):.2f})",
                            ErrorSeverity.MEDIUM
                        )
                    else:
                        self.logger.warning("No application form detected")
                
                return form_info
                
            except Exception as e:
                if isinstance(e, PortalChangeError):
                    raise e
                self.logger.error(f"Form detection failed: {e}")
                raise FormError(f"Form detection failed: {e}", ErrorSeverity.MEDIUM)
        
        try:
            return await retry_service.retry_with_backoff(
                _detect_form,
                config=retry_config,
                context={"operation": "form_detection", "url": page.url}
            )
        except Exception as e:
            # Return minimal form info on failure
            return {
                'detected': False,
                'fields': {},
                'submit_button': None,
                'field_count': 0,
                'has_file_upload': False,
                'error': str(e),
                'detected_at': datetime.utcnow().isoformat()
            }
    
    async def _detect_form_fields_with_fallback(self, page: Page) -> Dict[str, Any]:
        """Detect form fields with fallback strategies.
        
        Args:
            page: Playwright page object
            
        Returns:
            Detected form fields
        """
        # Try primary detection first
        try:
            return await FormFieldMapper.detect_form_fields(page)
        except Exception as e:
            self.logger.warning(f"Primary form detection failed, trying fallback: {e}")
            
            # Fallback: try to find common form elements
            fallback_fields = {}
            
            # Try to find email field with fallback
            email_element = await fallback_strategy.find_element_with_fallback(
                page, 'input[type="email"]', 'email'
            )
            if email_element:
                fallback_fields['email'] = {
                    'selector': 'input[type="email"]',
                    'element': email_element,
                    'attributes': {'tagName': 'input', 'type': 'email'}
                }
            
            return fallback_fields
    
    async def _detect_submit_button_with_fallback(self, page: Page) -> Optional[Dict[str, Any]]:
        """Detect submit button with fallback strategies.
        
        Args:
            page: Playwright page object
            
        Returns:
            Submit button information or None
        """
        # Try primary detection first
        try:
            return await FormFieldMapper.detect_submit_button(page)
        except Exception as e:
            self.logger.warning(f"Primary submit button detection failed, trying fallback: {e}")
            
            # Fallback: try to find submit button
            submit_element = await fallback_strategy.find_element_with_fallback(
                page, 'button[type="submit"]', 'submit'
            )
            
            if submit_element:
                return {
                    'selector': 'button[type="submit"]',
                    'element': submit_element,
                    'attributes': {'tagName': 'button', 'type': 'submit'}
                }
            
            return None
    
    async def take_screenshot(
        self,
        page: Page,
        filename: Optional[str] = None,
        full_page: bool = True
    ) -> str:
        """Take a screenshot of the current page.
        
        Args:
            page: Playwright page object
            filename: Optional filename for screenshot
            full_page: Whether to capture full page
            
        Returns:
            Screenshot file path
        """
        try:
            if not filename:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            # Ensure screenshots directory exists
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_path = screenshots_dir / filename
            
            await page.screenshot(
                path=str(screenshot_path),
                full_page=full_page
            )
            
            self.logger.info(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            raise BrowserAutomationError(f"Screenshot failed: {e}")
    
    async def cleanup(self) -> None:
        """Cleanup browser resources."""
        try:
            await self.browser_manager.stop()
            self._initialized = False
            self.logger.info("Browser automation service cleaned up")
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")


# Global service instance
browser_automation_service = BrowserAutomationService()