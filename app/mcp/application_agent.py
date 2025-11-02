"""Application Agent MCP for automated job application submission."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from app.mcp.base_agent import BaseAgent, AgentError
from app.services.browser_automation_service import (
    browser_automation_service, 
    BrowserAutomationError,
    FormDetectionError,
    FileUploadError
)
from app.repositories.job_repository import job_repository
from app.repositories.application_repository import application_repository
from app.repositories.user_repository import user_repository
from app.models.application import Application, ApplicationStatus
from app.models.job import Job


class ApplicationAgent(BaseAgent):
    """MCP Agent for automated job application submission."""
    
    def __init__(self):
        """Initialize the Application Agent."""
        super().__init__(
            name="application_agent",
            description="Automated job application submission agent"
        )
        self.browser_service = browser_automation_service
        
    async def _initialize(self) -> None:
        """Initialize agent-specific resources."""
        self.logger.info("Initializing Application Agent")
        
        # Initialize browser automation service
        try:
            await self.browser_service.initialize(headless=True)
            self.logger.info("Browser automation service initialized")
        except Exception as e:
            self.logger.warning(f"Browser service initialization failed: {e}")
    
    async def _cleanup(self) -> None:
        """Cleanup agent-specific resources."""
        self.logger.info("Cleaning up Application Agent")
        try:
            await self.browser_service.cleanup()
        except Exception as e:
            self.logger.warning(f"Browser cleanup failed: {e}")
    
    async def _execute_task_impl(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute application submission task.
        
        Args:
            task_data: Task parameters containing:
                - action: Task action (submit_application, detect_form, test_navigation)
                - user_id: User ID
                - job_id: Job ID
                - resume_path: Path to resume file (optional)
                
        Returns:
            Task execution result
        """
        action = task_data.get("action")
        
        if action == "submit_application":
            return await self._submit_job_application(task_data)
        elif action == "detect_form":
            return await self._detect_application_form(task_data)
        elif action == "test_navigation":
            return await self._test_job_navigation(task_data)
        elif action == "take_screenshot":
            return await self._take_page_screenshot(task_data)
        elif action == "fill_form":
            return await self._fill_application_form(task_data)
        else:
            raise AgentError(f"Unknown action: {action}")
    
    async def _submit_job_application(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a complete job application.
        
        Args:
            task_data: Task data with user_id, job_id, and optional resume_path
            
        Returns:
            Application submission result
        """
        user_id = task_data.get("user_id")
        job_id = task_data.get("job_id")
        resume_path = task_data.get("resume_path")
        
        if not user_id or not job_id:
            raise AgentError("user_id and job_id are required for application submission")
        
        try:
            # Get job and user details
            job = await job_repository.get_by_id(job_id)
            if not job:
                raise AgentError(f"Job not found: {job_id}")
            
            user = await user_repository.get_by_id(user_id)
            if not user:
                raise AgentError(f"User not found: {user_id}")
            
            # Create application record
            application = Application(
                user_id=user_id,
                job_id=job_id,
                status=ApplicationStatus.IN_PROGRESS,
                applied_at=datetime.utcnow(),
                metadata={
                    "job_title": job.title,
                    "company": job.company,
                    "job_url": job.url,
                    "resume_path": resume_path
                }
            )
            
            # Save initial application record
            saved_application = await application_repository.create(application)
            
            # Create optimized browser session for application workflow
            context, page = await self._create_application_workflow_session()
            
            try:
                # Navigate to job posting with enhanced navigation
                navigation_result = await self._navigate_to_application_page(page, job.url)
                
                if not navigation_result["success"]:
                    raise AgentError(f"Failed to navigate to job after {navigation_result['attempts']} attempts")
                
                # Take initial screenshot with metadata
                screenshot_path = await self._capture_submission_screenshot(
                    page, job_id, "initial"
                )
                
                # Detect application form
                form_info = await self.browser_service.detect_application_form(page)
                
                if not form_info['detected']:
                    # Update application status
                    application.status = ApplicationStatus.FAILED
                    application.metadata.update({
                        "error": "No application form detected",
                        "screenshot": screenshot_path
                    })
                    await application_repository.update(str(saved_application.id), application)
                    
                    return {
                        "success": False,
                        "error": "No application form detected on the page",
                        "application_id": str(saved_application.id),
                        "screenshot": screenshot_path
                    }
                
                # Fill application form
                fill_result = await self._fill_form_with_user_data(
                    page, form_info, user, resume_path
                )
                
                if not fill_result["success"]:
                    # Update application status
                    application.status = ApplicationStatus.FAILED
                    application.metadata.update({
                        "error": fill_result.get("error", "Form filling failed"),
                        "screenshot": screenshot_path,
                        "form_info": form_info,
                        "navigation_result": navigation_result
                    })
                    await application_repository.update(str(saved_application.id), application)
                    
                    return {
                        "success": False,
                        "error": fill_result.get("error", "Form filling failed"),
                        "application_id": str(saved_application.id),
                        "screenshot": screenshot_path
                    }
                
                # Validate form readiness before submission
                validation_result = await self._validate_form_submission_readiness(
                    page, form_info, user.profile
                )
                
                # Take screenshot before submission
                pre_submit_screenshot = await self._capture_submission_screenshot(
                    page, job_id, "pre_submit"
                )
                
                # Submit form (if enabled)
                submit_enabled = task_data.get("submit_form", False)
                submit_result = {"success": False, "message": "Submission not enabled"}
                
                if submit_enabled and form_info.get("submit_button"):
                    submit_result = await self._submit_form(page, form_info)
                    
                    # Take screenshot after submission attempt
                    post_submit_screenshot = await self._capture_submission_screenshot(
                        page, job_id, "post_submit"
                    )
                    
                    if submit_result["success"]:
                        application.status = ApplicationStatus.SUBMITTED
                        application.submitted_at = datetime.utcnow()
                        
                        # Take success confirmation screenshot
                        success_screenshot = await self._capture_submission_screenshot(
                            page, job_id, "success_confirmation"
                        )
                    else:
                        application.status = ApplicationStatus.FAILED
                        application.metadata["submit_error"] = submit_result.get("error")
                        
                        # Take error screenshot
                        error_screenshot = await self._capture_submission_screenshot(
                            page, job_id, "submission_error"
                        )
                else:
                    application.status = ApplicationStatus.READY_TO_SUBMIT
                
                # Take final screenshot
                final_screenshot = await self._capture_submission_screenshot(
                    page, job_id, "final"
                )
                
                # Collect all screenshots
                screenshots = {
                    "initial": screenshot_path,
                    "pre_submit": pre_submit_screenshot,
                    "final": final_screenshot
                }
                
                # Add submission-specific screenshots if they exist
                if submit_enabled and 'post_submit_screenshot' in locals():
                    screenshots["post_submit"] = post_submit_screenshot
                if submit_result.get("success") and 'success_screenshot' in locals():
                    screenshots["success_confirmation"] = success_screenshot
                if not submit_result.get("success") and 'error_screenshot' in locals():
                    screenshots["submission_error"] = error_screenshot
                
                # Update application record with comprehensive metadata
                application.metadata.update({
                    "navigation_result": navigation_result,
                    "form_info": form_info,
                    "form_fields_filled": fill_result.get("fields_filled", []),
                    "validation_result": validation_result,
                    "submit_result": submit_result if submit_enabled else {"enabled": False},
                    "screenshots": screenshots,
                    "workflow_completed": True,
                    "submission_confidence": submit_result.get("confidence", 0.0) if submit_enabled else 0.0
                })
                
                await application_repository.update(str(saved_application.id), application)
                
                self.logger.info(f"Application process completed for job {job_id}")
                
                return {
                    "success": True,
                    "application_id": str(saved_application.id),
                    "status": application.status.value,
                    "form_fields_detected": len(form_info.get("fields", {})),
                    "form_filled": fill_result["success"],
                    "submitted": submit_enabled and submit_result.get("success", False) if submit_enabled else False,
                    "screenshots": application.metadata["screenshots"]
                }
                
            finally:
                # Close browser context
                await self.browser_service.browser_manager.close_context(context)
                
        except Exception as e:
            self.logger.error(f"Application submission failed: {e}")
            
            # Update application status if we have one
            if 'saved_application' in locals():
                try:
                    application.status = ApplicationStatus.FAILED
                    application.metadata["error"] = str(e)
                    await application_repository.update(str(saved_application.id), application)
                except:
                    pass
            
            raise AgentError(f"Application submission failed: {e}")
    
    async def _fill_form_with_user_data(
        self,
        page,
        form_info: Dict[str, Any],
        user,
        resume_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fill application form with user data.
        
        Args:
            page: Playwright page object
            form_info: Form detection information
            user: User object with profile data
            resume_path: Optional path to resume file
            
        Returns:
            Form filling result
        """
        try:
            fields_filled = []
            form_fields = form_info.get("fields", {})
            
            # Fill personal information
            if "first_name" in form_fields and user.profile.get("first_name"):
                await page.fill(form_fields["first_name"]["selector"], user.profile["first_name"])
                fields_filled.append("first_name")
            
            if "last_name" in form_fields and user.profile.get("last_name"):
                await page.fill(form_fields["last_name"]["selector"], user.profile["last_name"])
                fields_filled.append("last_name")
            
            if "full_name" in form_fields and user.profile.get("name"):
                await page.fill(form_fields["full_name"]["selector"], user.profile["name"])
                fields_filled.append("full_name")
            
            if "email" in form_fields and user.email:
                await page.fill(form_fields["email"]["selector"], user.email)
                fields_filled.append("email")
            
            if "phone" in form_fields and user.profile.get("phone"):
                await page.fill(form_fields["phone"]["selector"], user.profile["phone"])
                fields_filled.append("phone")
            
            # Fill address information
            if "address" in form_fields and user.profile.get("address"):
                await page.fill(form_fields["address"]["selector"], user.profile["address"])
                fields_filled.append("address")
            
            if "city" in form_fields and user.profile.get("city"):
                await page.fill(form_fields["city"]["selector"], user.profile["city"])
                fields_filled.append("city")
            
            if "state" in form_fields and user.profile.get("state"):
                # Handle both select and input fields
                field_type = form_fields["state"]["attributes"]["tagName"].lower()
                if field_type == "select":
                    await page.select_option(form_fields["state"]["selector"], user.profile["state"])
                else:
                    await page.fill(form_fields["state"]["selector"], user.profile["state"])
                fields_filled.append("state")
            
            if "zip_code" in form_fields and user.profile.get("zip_code"):
                await page.fill(form_fields["zip_code"]["selector"], user.profile["zip_code"])
                fields_filled.append("zip_code")
            
            # Fill professional links
            if "linkedin" in form_fields and user.profile.get("linkedin"):
                await page.fill(form_fields["linkedin"]["selector"], user.profile["linkedin"])
                fields_filled.append("linkedin")
            
            if "website" in form_fields and user.profile.get("website"):
                await page.fill(form_fields["website"]["selector"], user.profile["website"])
                fields_filled.append("website")
            
            # Upload resume if available
            if "resume_upload" in form_fields and resume_path:
                try:
                    upload_success = await self.browser_service.file_upload_handler.upload_file(
                        page, form_fields["resume_upload"]["selector"], resume_path
                    )
                    if upload_success:
                        fields_filled.append("resume_upload")
                except FileUploadError as e:
                    self.logger.warning(f"Resume upload failed: {e}")
            
            self.logger.info(f"Filled {len(fields_filled)} form fields")
            
            return {
                "success": True,
                "fields_filled": fields_filled,
                "total_fields": len(form_fields)
            }
            
        except Exception as e:
            self.logger.error(f"Form filling failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "fields_filled": fields_filled
            }
    
    async def _submit_form(self, page, form_info: Dict[str, Any]) -> Dict[str, Any]:
        """Submit the application form with comprehensive verification.
        
        Args:
            page: Playwright page object
            form_info: Form information with submit button
            
        Returns:
            Submission result with verification details
        """
        try:
            submit_button = form_info.get("submit_button")
            if not submit_button:
                return {"success": False, "error": "No submit button found"}
            
            # Get initial page state for comparison
            initial_url = page.url
            initial_title = await page.title()
            
            self.logger.info(f"Submitting form on page: {initial_title}")
            
            # Click submit button
            await page.click(submit_button["selector"])
            
            # Wait for potential navigation or page changes
            submission_result = await self._verify_submission(
                page, initial_url, initial_title
            )
            
            return submission_result
            
        except Exception as e:
            self.logger.error(f"Form submission failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "verification_details": {}
            }
    
    async def _verify_submission(
        self,
        page,
        initial_url: str,
        initial_title: str,
        timeout: int = 15000
    ) -> Dict[str, Any]:
        """Verify application submission using multiple methods.
        
        Args:
            page: Playwright page object
            initial_url: URL before submission
            initial_title: Page title before submission
            timeout: Verification timeout in milliseconds
            
        Returns:
            Verification result with details
        """
        verification_details = {
            "initial_url": initial_url,
            "initial_title": initial_title,
            "navigation_occurred": False,
            "url_changed": False,
            "title_changed": False,
            "success_indicators_found": [],
            "error_indicators_found": [],
            "final_url": "",
            "final_title": "",
            "page_state_checks": {}
        }
        
        try:
            # Wait for potential navigation with timeout
            try:
                await page.wait_for_load_state('networkidle', timeout=timeout)
                verification_details["navigation_occurred"] = True
            except:
                # No navigation occurred, check current page state
                pass
            
            # Get final page state
            final_url = page.url
            final_title = await page.title()
            
            verification_details["final_url"] = final_url
            verification_details["final_title"] = final_title
            verification_details["url_changed"] = final_url != initial_url
            verification_details["title_changed"] = final_title != initial_title
            
            # Check for success indicators in page content
            page_content = await page.content()
            page_text = page_content.lower()
            
            success_indicators = [
                "thank you for your application",
                "application submitted successfully",
                "your application has been received",
                "application received",
                "successfully submitted",
                "thank you for applying",
                "application complete",
                "we have received your application",
                "your resume has been submitted"
            ]
            
            error_indicators = [
                "error submitting",
                "submission failed",
                "please correct the following",
                "required field",
                "invalid",
                "application not submitted"
            ]
            
            # Check for success indicators
            for indicator in success_indicators:
                if indicator in page_text:
                    verification_details["success_indicators_found"].append(indicator)
            
            # Check for error indicators
            for indicator in error_indicators:
                if indicator in page_text:
                    verification_details["error_indicators_found"].append(indicator)
            
            # Additional page state checks
            verification_details["page_state_checks"] = await self._perform_page_state_checks(page)
            
            # Determine overall success
            has_success_indicators = len(verification_details["success_indicators_found"]) > 0
            has_error_indicators = len(verification_details["error_indicators_found"]) > 0
            navigation_suggests_success = verification_details["url_changed"] or verification_details["title_changed"]
            
            # Success determination logic
            if has_success_indicators and not has_error_indicators:
                success = True
                message = f"Application submitted successfully. Found indicators: {verification_details['success_indicators_found']}"
            elif has_error_indicators:
                success = False
                message = f"Application submission failed. Found errors: {verification_details['error_indicators_found']}"
            elif navigation_suggests_success:
                success = True
                message = "Application likely submitted (page navigation detected)"
            else:
                success = False
                message = "Application submission unclear (no clear indicators found)"
            
            self.logger.info(f"Submission verification: {message}")
            
            return {
                "success": success,
                "message": message,
                "verification_details": verification_details,
                "confidence": self._calculate_confidence_score(verification_details)
            }
            
        except Exception as e:
            self.logger.error(f"Submission verification failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "verification_details": verification_details
            }
    
    async def _perform_page_state_checks(self, page) -> Dict[str, Any]:
        """Perform additional page state checks for submission verification.
        
        Args:
            page: Playwright page object
            
        Returns:
            Page state check results
        """
        checks = {}
        
        try:
            # Check for form presence (form might disappear after submission)
            form_elements = await page.query_selector_all("form")
            checks["forms_present"] = len(form_elements)
            
            # Check for submit buttons (might be disabled after submission)
            submit_buttons = await page.query_selector_all('button[type="submit"], input[type="submit"]')
            checks["submit_buttons_present"] = len(submit_buttons)
            
            # Check if submit buttons are disabled
            disabled_buttons = 0
            for button in submit_buttons:
                is_disabled = await button.is_disabled()
                if is_disabled:
                    disabled_buttons += 1
            checks["disabled_submit_buttons"] = disabled_buttons
            
            # Check for progress indicators or loading states
            progress_indicators = await page.query_selector_all(
                '.loading, .spinner, .progress, [class*="loading"], [class*="spinner"]'
            )
            checks["progress_indicators"] = len(progress_indicators)
            
            # Check for success/confirmation elements
            success_elements = await page.query_selector_all(
                '.success, .confirmation, .thank-you, [class*="success"], [class*="confirmation"]'
            )
            checks["success_elements"] = len(success_elements)
            
            # Check for error elements
            error_elements = await page.query_selector_all(
                '.error, .alert, .warning, [class*="error"], [class*="alert"]'
            )
            checks["error_elements"] = len(error_elements)
            
        except Exception as e:
            checks["error"] = str(e)
        
        return checks
    
    def _calculate_confidence_score(self, verification_details: Dict[str, Any]) -> float:
        """Calculate confidence score for submission verification.
        
        Args:
            verification_details: Verification details
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        score = 0.0
        
        # Success indicators boost confidence
        success_count = len(verification_details.get("success_indicators_found", []))
        score += min(success_count * 0.3, 0.6)  # Max 0.6 from success indicators
        
        # Navigation changes suggest success
        if verification_details.get("url_changed") or verification_details.get("title_changed"):
            score += 0.2
        
        # Page state checks
        page_checks = verification_details.get("page_state_checks", {})
        if page_checks.get("success_elements", 0) > 0:
            score += 0.15
        
        if page_checks.get("disabled_submit_buttons", 0) > 0:
            score += 0.1
        
        # Error indicators reduce confidence
        error_count = len(verification_details.get("error_indicators_found", []))
        score -= error_count * 0.2
        
        if page_checks.get("error_elements", 0) > 0:
            score -= 0.15
        
        return max(0.0, min(1.0, score))  # Clamp between 0 and 1
    
    async def _capture_submission_screenshot(
        self,
        page,
        job_id: str,
        stage: str,
        include_metadata: bool = True
    ) -> str:
        """Capture screenshot during submission workflow with metadata.
        
        Args:
            page: Playwright page object
            job_id: Job ID for filename
            stage: Submission stage (initial, pre_submit, post_submit, etc.)
            include_metadata: Whether to include page metadata
            
        Returns:
            Screenshot file path
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"job_{job_id}_{stage}_{timestamp}.png"
            
            screenshot_path = await self.browser_service.take_screenshot(
                page, filename, full_page=True
            )
            
            if include_metadata:
                # Save screenshot metadata
                metadata = {
                    "job_id": job_id,
                    "stage": stage,
                    "timestamp": timestamp,
                    "url": page.url,
                    "title": await page.title(),
                    "viewport": await page.viewport_size(),
                    "screenshot_path": screenshot_path
                }
                
                # Save metadata to JSON file
                metadata_path = Path(screenshot_path).with_suffix('.json')
                import json
                import aiofiles
                
                async with aiofiles.open(metadata_path, 'w') as f:
                    await f.write(json.dumps(metadata, indent=2))
            
            self.logger.info(f"Captured {stage} screenshot: {screenshot_path}")
            return screenshot_path
            
        except Exception as e:
            self.logger.error(f"Screenshot capture failed for {stage}: {e}")
            return ""
    
    async def _navigate_to_application_page(
        self,
        page,
        job_url: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Navigate to job application page with retry logic.
        
        Args:
            page: Playwright page object
            job_url: Job posting URL
            max_retries: Maximum retry attempts
            
        Returns:
            Navigation result with details
        """
        navigation_result = {
            "success": False,
            "attempts": 0,
            "final_url": "",
            "page_title": "",
            "load_time": 0.0,
            "errors": []
        }
        
        for attempt in range(max_retries):
            navigation_result["attempts"] = attempt + 1
            
            try:
                start_time = datetime.utcnow()
                
                self.logger.info(f"Navigation attempt {attempt + 1} to: {job_url}")
                
                # Navigate with timeout
                response = await page.goto(job_url, timeout=60000)
                
                if not response:
                    raise Exception("No response received")
                
                if response.status >= 400:
                    raise Exception(f"HTTP error: {response.status}")
                
                # Wait for page to be fully loaded
                await page.wait_for_load_state('networkidle', timeout=30000)
                
                end_time = datetime.utcnow()
                load_time = (end_time - start_time).total_seconds()
                
                # Get final page state
                final_url = page.url
                page_title = await page.title()
                
                navigation_result.update({
                    "success": True,
                    "final_url": final_url,
                    "page_title": page_title,
                    "load_time": load_time
                })
                
                self.logger.info(f"Successfully navigated to: {final_url} (Load time: {load_time:.2f}s)")
                break
                
            except Exception as e:
                error_msg = f"Attempt {attempt + 1} failed: {str(e)}"
                navigation_result["errors"].append(error_msg)
                self.logger.warning(error_msg)
                
                if attempt < max_retries - 1:
                    # Wait before retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.logger.error(f"All navigation attempts failed for: {job_url}")
        
        return navigation_result
    
    async def _create_application_workflow_session(
        self,
        user_agent: Optional[str] = None
    ) -> Tuple:
        """Create optimized browser session for application workflow.
        
        Args:
            user_agent: Optional custom user agent
            
        Returns:
            Tuple of (context, page) optimized for job applications
        """
        # Use realistic user agent if not provided
        if not user_agent:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        
        # Create context with job application optimizations
        context, page = await self.browser_service.create_session(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080}
        )
        
        # Set additional page configurations for job applications
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })
        
        # Set reasonable timeouts for job application forms
        page.set_default_timeout(45000)  # 45 seconds
        page.set_default_navigation_timeout(90000)  # 90 seconds
        
        return context, page
    
    async def _validate_form_submission_readiness(
        self,
        page,
        form_info: Dict[str, Any],
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that form is ready for submission.
        
        Args:
            page: Playwright page object
            form_info: Detected form information
            user_data: User profile data
            
        Returns:
            Validation result with readiness status
        """
        validation_result = {
            "ready": False,
            "required_fields_filled": 0,
            "total_required_fields": 0,
            "missing_required_data": [],
            "form_validation_errors": [],
            "warnings": []
        }
        
        try:
            form_fields = form_info.get("fields", {})
            
            # Check required fields
            for field_type, field_info in form_fields.items():
                if field_info["attributes"].get("required", False):
                    validation_result["total_required_fields"] += 1
                    
                    # Check if we have data for this field
                    has_data = False
                    
                    if field_type in ["first_name", "last_name", "full_name"] and user_data.get("name"):
                        has_data = True
                    elif field_type == "email" and user_data.get("email"):
                        has_data = True
                    elif field_type == "phone" and user_data.get("phone"):
                        has_data = True
                    # Add more field type checks as needed
                    
                    if has_data:
                        validation_result["required_fields_filled"] += 1
                    else:
                        validation_result["missing_required_data"].append(field_type)
            
            # Check for client-side validation errors
            error_elements = await page.query_selector_all(
                '.error, .invalid, [class*="error"], [class*="invalid"]'
            )
            
            for element in error_elements:
                try:
                    error_text = await element.text_content()
                    if error_text and error_text.strip():
                        validation_result["form_validation_errors"].append(error_text.strip())
                except:
                    pass
            
            # Determine readiness
            all_required_filled = (
                validation_result["required_fields_filled"] == validation_result["total_required_fields"]
            )
            no_validation_errors = len(validation_result["form_validation_errors"]) == 0
            
            validation_result["ready"] = all_required_filled and no_validation_errors
            
            if not validation_result["ready"]:
                if not all_required_filled:
                    validation_result["warnings"].append(
                        f"Missing data for required fields: {validation_result['missing_required_data']}"
                    )
                if not no_validation_errors:
                    validation_result["warnings"].append(
                        f"Form validation errors present: {len(validation_result['form_validation_errors'])}"
                    )
            
            return validation_result
            
        except Exception as e:
            validation_result["error"] = str(e)
            return validation_result
    
    async def _detect_application_form(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect application form on a job page.
        
        Args:
            task_data: Task data with job_url
            
        Returns:
            Form detection result
        """
        job_url = task_data.get("job_url")
        if not job_url:
            raise AgentError("job_url is required for form detection")
        
        try:
            # Create browser session
            context, page = await self.browser_service.create_session()
            
            try:
                # Navigate to job page
                navigation_success = await self.browser_service.navigate_to_job(page, job_url)
                
                if not navigation_success:
                    return {
                        "success": False,
                        "error": f"Failed to navigate to: {job_url}"
                    }
                
                # Detect form
                form_info = await self.browser_service.detect_application_form(page)
                
                # Take screenshot
                screenshot_path = await self.browser_service.take_screenshot(
                    page, f"form_detection_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                )
                
                return {
                    "success": True,
                    "form_detected": form_info["detected"],
                    "form_info": form_info,
                    "screenshot": screenshot_path,
                    "url": job_url
                }
                
            finally:
                await self.browser_service.browser_manager.close_context(context)
                
        except Exception as e:
            self.logger.error(f"Form detection failed: {e}")
            raise AgentError(f"Form detection failed: {e}")
    
    async def _test_job_navigation(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test navigation to a job URL.
        
        Args:
            task_data: Task data with job_url
            
        Returns:
            Navigation test result
        """
        job_url = task_data.get("job_url")
        if not job_url:
            raise AgentError("job_url is required for navigation test")
        
        try:
            context, page = await self.browser_service.create_session()
            
            try:
                start_time = datetime.utcnow()
                
                # Test navigation
                navigation_success = await self.browser_service.navigate_to_job(page, job_url)
                
                end_time = datetime.utcnow()
                load_time = (end_time - start_time).total_seconds()
                
                # Get page info
                title = await page.title()
                url = page.url
                
                # Take screenshot
                screenshot_path = await self.browser_service.take_screenshot(
                    page, f"navigation_test_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                )
                
                return {
                    "success": navigation_success,
                    "load_time": load_time,
                    "page_title": title,
                    "final_url": url,
                    "screenshot": screenshot_path,
                    "tested_at": start_time.isoformat()
                }
                
            finally:
                await self.browser_service.browser_manager.close_context(context)
                
        except Exception as e:
            self.logger.error(f"Navigation test failed: {e}")
            raise AgentError(f"Navigation test failed: {e}")
    
    async def _take_page_screenshot(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Take a screenshot of a page.
        
        Args:
            task_data: Task data with job_url and optional filename
            
        Returns:
            Screenshot result
        """
        job_url = task_data.get("job_url")
        filename = task_data.get("filename")
        
        if not job_url:
            raise AgentError("job_url is required for screenshot")
        
        try:
            context, page = await self.browser_service.create_session()
            
            try:
                # Navigate to page
                await self.browser_service.navigate_to_job(page, job_url)
                
                # Take screenshot
                screenshot_path = await self.browser_service.take_screenshot(page, filename)
                
                return {
                    "success": True,
                    "screenshot_path": screenshot_path,
                    "url": job_url,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
            finally:
                await self.browser_service.browser_manager.close_context(context)
                
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            raise AgentError(f"Screenshot failed: {e}")
    
    # Public methods for external use
    async def submit_application(
        self,
        user_id: str,
        job_id: str,
        resume_path: Optional[str] = None,
        submit_form: bool = False
    ) -> Dict[str, Any]:
        """Public method to submit job application.
        
        Args:
            user_id: User ID
            job_id: Job ID
            resume_path: Optional path to resume file
            submit_form: Whether to actually submit the form
            
        Returns:
            Application submission result
        """
        return await self.execute_task({
            "action": "submit_application",
            "user_id": user_id,
            "job_id": job_id,
            "resume_path": resume_path,
            "submit_form": submit_form
        })
    
    async def detect_form(self, job_url: str) -> Dict[str, Any]:
        """Public method to detect application form.
        
        Args:
            job_url: Job posting URL
            
        Returns:
            Form detection result
        """
        return await self.execute_task({
            "action": "detect_form",
            "job_url": job_url
        })
    
    async def test_navigation(self, job_url: str) -> Dict[str, Any]:
        """Public method to test job navigation.
        
        Args:
            job_url: Job posting URL
            
        Returns:
            Navigation test result
        """
        return await self.execute_task({
            "action": "test_navigation",
            "job_url": job_url
        })


# Global agent instance
application_agent = ApplicationAgent()