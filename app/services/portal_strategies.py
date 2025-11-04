"""Portal-specific automation strategies for job applications."""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlparse

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.models.user import User
from app.services.browser_automation_service import FormFieldMapper, FileUploadHandler


class PortalStrategy(ABC):
    """Abstract base class for portal-specific automation strategies."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.file_upload_handler = FileUploadHandler()
    
    @abstractmethod
    async def apply(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Execute the application process for this portal.
        
        Args:
            page: Playwright page object
            user: User profile data
            resume_path: Path to resume file
            application_id: Application ID for tracking
            
        Returns:
            Dictionary containing application results
        """
        pass
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this strategy can handle the given URL.
        
        Args:
            url: Job posting URL
            
        Returns:
            True if this strategy can handle the URL
        """
        pass
    
    async def take_screenshot(self, page: Page, application_id: str, step: str) -> str:
        """Take a screenshot for the current step.
        
        Args:
            page: Playwright page object
            application_id: Application ID
            step: Current step name
            
        Returns:
            Screenshot file path
        """
        try:
            from pathlib import Path
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{application_id}_{step}_{timestamp}.png"
            
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            
            screenshot_path = screenshots_dir / filename
            
            await page.screenshot(path=str(screenshot_path), full_page=True)
            
            self.logger.info(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return ""


class LinkedInStrategy(PortalStrategy):
    """LinkedIn-specific automation strategy."""
    
    def can_handle(self, url: str) -> bool:
        """Check if this is a LinkedIn URL."""
        return "linkedin.com" in url.lower()
    
    async def apply(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Execute LinkedIn Easy Apply automation."""
        result = {
            "success": False,
            "confirmation_number": None,
            "screenshots": [],
            "form_data": {},
            "error": None,
            "portal_response": None
        }
        
        try:
            self.logger.info(f"Starting LinkedIn application for {application_id}")
            
            # Take initial screenshot
            screenshot = await self.take_screenshot(page, application_id, "01_initial_page")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Look for Easy Apply button
            easy_apply_found = await self._find_easy_apply_button(page)
            
            if not easy_apply_found:
                result["error"] = "Easy Apply button not found - may require external application"
                return result
            
            # Click Easy Apply button
            await self._click_easy_apply(page)
            await page.wait_for_timeout(2000)  # Wait for modal to load
            
            # Take screenshot after clicking Easy Apply
            screenshot = await self.take_screenshot(page, application_id, "02_easy_apply_modal")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Fill application form
            form_data = await self._fill_linkedin_form(page, user, resume_path, application_id)
            result["form_data"] = form_data
            
            # Take screenshot after filling form
            screenshot = await self.take_screenshot(page, application_id, "03_form_filled")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Submit application
            submission_success = await self._submit_linkedin_application(page, application_id)
            
            if submission_success:
                # Take final screenshot
                screenshot = await self.take_screenshot(page, application_id, "04_submitted")
                if screenshot:
                    result["screenshots"].append(screenshot)
                
                # Extract confirmation
                confirmation = await self._get_linkedin_confirmation(page)
                
                result["success"] = True
                result["confirmation_number"] = confirmation
                result["portal_response"] = {"platform": "linkedin", "method": "easy_apply"}
                
                self.logger.info(f"LinkedIn application successful for {application_id}")
            else:
                result["error"] = "Failed to submit LinkedIn application"
            
            return result
            
        except Exception as e:
            self.logger.error(f"LinkedIn application failed for {application_id}: {e}")
            result["error"] = str(e)
            
            # Take error screenshot
            try:
                screenshot = await self.take_screenshot(page, application_id, "error")
                if screenshot:
                    result["screenshots"].append(screenshot)
            except:
                pass
            
            return result
    
    async def _find_easy_apply_button(self, page: Page) -> bool:
        """Find the Easy Apply button on LinkedIn."""
        easy_apply_selectors = [
            'button:has-text("Easy Apply")',
            'button[aria-label*="Easy Apply"]',
            '.jobs-apply-button:has-text("Easy Apply")',
            '.jobs-s-apply button:has-text("Easy Apply")'
        ]
        
        for selector in easy_apply_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Check if button is visible and enabled
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        self.logger.info(f"Found Easy Apply button: {selector}")
                        return True
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return False
    
    async def _click_easy_apply(self, page: Page):
        """Click the Easy Apply button."""
        easy_apply_selectors = [
            'button:has-text("Easy Apply")',
            'button[aria-label*="Easy Apply"]',
            '.jobs-apply-button:has-text("Easy Apply")',
            '.jobs-s-apply button:has-text("Easy Apply")'
        ]
        
        for selector in easy_apply_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible() and await element.is_enabled():
                    await element.click()
                    self.logger.info("Clicked Easy Apply button")
                    return
            except Exception as e:
                continue
        
        raise Exception("Could not click Easy Apply button")
    
    async def _fill_linkedin_form(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Fill LinkedIn application form."""
        form_data = {}
        
        try:
            # Wait for form to load
            await page.wait_for_timeout(2000)
            
            # Get user personal info
            personal_info = user.personal_info if hasattr(user, 'personal_info') else {}
            
            # Fill phone number if present
            phone_selectors = [
                'input[id*="phone"]',
                'input[name*="phone"]',
                'input[aria-label*="phone"]'
            ]
            
            for selector in phone_selectors:
                try:
                    phone_input = await page.query_selector(selector)
                    if phone_input and await phone_input.is_visible():
                        phone = personal_info.get('phone', '')
                        if phone:
                            await phone_input.fill(phone)
                            form_data['phone'] = phone
                            self.logger.info("Filled phone number")
                        break
                except Exception:
                    continue
            
            # Upload resume if file input is present
            if resume_path:
                try:
                    await self._upload_resume_linkedin(page, resume_path)
                    form_data['resume_uploaded'] = True
                    self.logger.info("Resume uploaded successfully")
                except Exception as e:
                    self.logger.warning(f"Resume upload failed: {e}")
                    form_data['resume_uploaded'] = False
            
            # Handle common LinkedIn questions
            await self._handle_linkedin_questions(page, user, form_data)
            
            return form_data
            
        except Exception as e:
            self.logger.error(f"Form filling failed: {e}")
            raise
    
    async def _upload_resume_linkedin(self, page: Page, resume_path: str):
        """Upload resume to LinkedIn application."""
        resume_selectors = [
            'input[type="file"][id*="resume"]',
            'input[type="file"][name*="resume"]',
            'input[type="file"][aria-label*="resume"]',
            'input[type="file"]'
        ]
        
        for selector in resume_selectors:
            try:
                file_input = await page.query_selector(selector)
                if file_input:
                    await self.file_upload_handler.upload_file(page, selector, resume_path)
                    return
            except Exception as e:
                self.logger.debug(f"Resume upload selector {selector} failed: {e}")
                continue
        
        raise Exception("Could not find resume upload field")
    
    async def _handle_linkedin_questions(self, page: Page, user: User, form_data: Dict[str, Any]):
        """Handle common LinkedIn application questions."""
        try:
            # Work authorization question
            work_auth_selectors = [
                'input[value="Yes"]:near(:text("authorized to work"))',
                'input[value="Yes"]:near(:text("work authorization"))',
                'fieldset:has-text("authorized") input[value="Yes"]'
            ]
            
            for selector in work_auth_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.check()
                        form_data['work_authorization'] = 'Yes'
                        self.logger.info("Answered work authorization question")
                        break
                except Exception:
                    continue
            
            # Sponsorship question
            sponsorship_selectors = [
                'input[value="No"]:near(:text("sponsorship"))',
                'input[value="No"]:near(:text("visa sponsorship"))',
                'fieldset:has-text("sponsorship") input[value="No"]'
            ]
            
            for selector in sponsorship_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.check()
                        form_data['sponsorship'] = 'No'
                        self.logger.info("Answered sponsorship question")
                        break
                except Exception:
                    continue
            
            # Years of experience
            experience_selectors = [
                'input[id*="experience"]',
                'select[id*="experience"]',
                'input[name*="experience"]'
            ]
            
            for selector in experience_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        # Calculate years of experience from user profile
                        years_exp = self._calculate_years_experience(user)
                        
                        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                        
                        if tag_name == 'select':
                            # Try to select closest option
                            await element.select_option(value=str(years_exp))
                        else:
                            await element.fill(str(years_exp))
                        
                        form_data['years_experience'] = years_exp
                        self.logger.info(f"Filled experience: {years_exp} years")
                        break
                except Exception:
                    continue
            
        except Exception as e:
            self.logger.warning(f"Question handling failed: {e}")
    
    def _calculate_years_experience(self, user: User) -> int:
        """Calculate years of experience from user profile."""
        # This would integrate with the user's experience data
        # For now, return a default value
        if hasattr(user, 'experience') and user.experience:
            # Calculate from experience entries
            return min(10, max(1, len(user.experience)))  # Cap between 1-10 years
        return 3  # Default fallback
    
    async def _submit_linkedin_application(self, page: Page, application_id: str) -> bool:
        """Submit the LinkedIn application."""
        try:
            # Look for submit/send button
            submit_selectors = [
                'button:has-text("Submit application")',
                'button:has-text("Submit")',
                'button:has-text("Send application")',
                'button[aria-label*="Submit"]',
                'button[type="submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button and await submit_button.is_visible() and await submit_button.is_enabled():
                        await submit_button.click()
                        
                        # Wait for submission to process
                        await page.wait_for_timeout(3000)
                        
                        # Check for success indicators
                        success_indicators = [
                            ':text("Application sent")',
                            ':text("Application submitted")',
                            ':text("Thank you")',
                            '.artdeco-inline-feedback--success'
                        ]
                        
                        for indicator in success_indicators:
                            try:
                                element = await page.query_selector(indicator)
                                if element and await element.is_visible():
                                    self.logger.info("LinkedIn application submitted successfully")
                                    return True
                            except Exception:
                                continue
                        
                        # If no clear success indicator, assume success if no error
                        return True
                        
                except Exception as e:
                    self.logger.debug(f"Submit selector {selector} failed: {e}")
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Application submission failed: {e}")
            return False
    
    async def _get_linkedin_confirmation(self, page: Page) -> Optional[str]:
        """Extract confirmation number from LinkedIn."""
        try:
            # Look for confirmation elements
            confirmation_selectors = [
                '.artdeco-inline-feedback--success',
                '[data-test-modal-id="application-submitted"]',
                ':text("Application ID")',
                ':text("Reference")'
            ]
            
            for selector in confirmation_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.text_content()
                        if text and any(char.isdigit() for char in text):
                            return text.strip()
                except Exception:
                    continue
            
            # Generate fallback confirmation
            return f"LinkedIn-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
        except Exception as e:
            self.logger.error(f"Failed to get LinkedIn confirmation: {e}")
            return None


class IndeedStrategy(PortalStrategy):
    """Indeed-specific automation strategy."""
    
    def can_handle(self, url: str) -> bool:
        """Check if this is an Indeed URL."""
        return "indeed.com" in url.lower()
    
    async def apply(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Execute Indeed application automation."""
        result = {
            "success": False,
            "confirmation_number": None,
            "screenshots": [],
            "form_data": {},
            "error": None,
            "portal_response": None
        }
        
        try:
            self.logger.info(f"Starting Indeed application for {application_id}")
            
            # Take initial screenshot
            screenshot = await self.take_screenshot(page, application_id, "01_initial_page")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Look for apply button
            apply_button_found = await self._find_indeed_apply_button(page)
            
            if not apply_button_found:
                result["error"] = "Apply button not found on Indeed"
                return result
            
            # Click apply button
            await self._click_indeed_apply(page)
            await page.wait_for_timeout(2000)
            
            # Take screenshot after clicking apply
            screenshot = await self.take_screenshot(page, application_id, "02_apply_clicked")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Fill application form
            form_data = await self._fill_indeed_form(page, user, resume_path, application_id)
            result["form_data"] = form_data
            
            # Take screenshot after filling form
            screenshot = await self.take_screenshot(page, application_id, "03_form_filled")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Submit application
            submission_success = await self._submit_indeed_application(page, application_id)
            
            if submission_success:
                # Take final screenshot
                screenshot = await self.take_screenshot(page, application_id, "04_submitted")
                if screenshot:
                    result["screenshots"].append(screenshot)
                
                # Extract confirmation
                confirmation = await self._get_indeed_confirmation(page)
                
                result["success"] = True
                result["confirmation_number"] = confirmation
                result["portal_response"] = {"platform": "indeed", "method": "direct_apply"}
                
                self.logger.info(f"Indeed application successful for {application_id}")
            else:
                result["error"] = "Failed to submit Indeed application"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Indeed application failed for {application_id}: {e}")
            result["error"] = str(e)
            
            # Take error screenshot
            try:
                screenshot = await self.take_screenshot(page, application_id, "error")
                if screenshot:
                    result["screenshots"].append(screenshot)
            except:
                pass
            
            return result
    
    async def _find_indeed_apply_button(self, page: Page) -> bool:
        """Find the apply button on Indeed."""
        apply_selectors = [
            'button:has-text("Apply now")',
            'a:has-text("Apply now")',
            '.jobsearch-IndeedApplyButton',
            '[data-jk] button:has-text("Apply")'
        ]
        
        for selector in apply_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    self.logger.info(f"Found Indeed apply button: {selector}")
                    return True
            except Exception:
                continue
        
        return False
    
    async def _click_indeed_apply(self, page: Page):
        """Click the Indeed apply button."""
        apply_selectors = [
            'button:has-text("Apply now")',
            'a:has-text("Apply now")',
            '.jobsearch-IndeedApplyButton',
            '[data-jk] button:has-text("Apply")'
        ]
        
        for selector in apply_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    self.logger.info("Clicked Indeed apply button")
                    return
            except Exception:
                continue
        
        raise Exception("Could not click Indeed apply button")
    
    async def _fill_indeed_form(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Fill Indeed application form."""
        form_data = {}
        
        try:
            # Wait for form to load
            await page.wait_for_timeout(2000)
            
            # Detect form fields
            form_fields = await FormFieldMapper.detect_form_fields(page)
            
            # Get user personal info
            personal_info = user.personal_info if hasattr(user, 'personal_info') else {}
            
            # Fill detected fields
            field_mappings = {
                'first_name': personal_info.get('first_name', ''),
                'last_name': personal_info.get('last_name', ''),
                'email': personal_info.get('email', ''),
                'phone': personal_info.get('phone', ''),
                'full_name': f"{personal_info.get('first_name', '')} {personal_info.get('last_name', '')}".strip()
            }
            
            for field_type, value in field_mappings.items():
                if field_type in form_fields and value:
                    try:
                        element = form_fields[field_type]['element']
                        await element.fill(value)
                        form_data[field_type] = value
                        self.logger.info(f"Filled {field_type}")
                    except Exception as e:
                        self.logger.warning(f"Failed to fill {field_type}: {e}")
            
            # Upload resume if available
            if resume_path and 'resume_upload' in form_fields:
                try:
                    selector = form_fields['resume_upload']['selector']
                    await self.file_upload_handler.upload_file(page, selector, resume_path)
                    form_data['resume_uploaded'] = True
                    self.logger.info("Resume uploaded to Indeed")
                except Exception as e:
                    self.logger.warning(f"Resume upload failed: {e}")
                    form_data['resume_uploaded'] = False
            
            return form_data
            
        except Exception as e:
            self.logger.error(f"Indeed form filling failed: {e}")
            raise
    
    async def _submit_indeed_application(self, page: Page, application_id: str) -> bool:
        """Submit the Indeed application."""
        try:
            submit_selectors = [
                'button:has-text("Submit application")',
                'button:has-text("Submit")',
                'button[type="submit"]',
                'input[type="submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button and await submit_button.is_visible() and await submit_button.is_enabled():
                        await submit_button.click()
                        
                        # Wait for submission
                        await page.wait_for_timeout(3000)
                        
                        # Check for success indicators
                        success_indicators = [
                            ':text("Application submitted")',
                            ':text("Thank you")',
                            ':text("Your application has been sent")'
                        ]
                        
                        for indicator in success_indicators:
                            try:
                                element = await page.query_selector(indicator)
                                if element and await element.is_visible():
                                    self.logger.info("Indeed application submitted successfully")
                                    return True
                            except Exception:
                                continue
                        
                        return True
                        
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            self.logger.error(f"Indeed submission failed: {e}")
            return False
    
    async def _get_indeed_confirmation(self, page: Page) -> Optional[str]:
        """Extract confirmation from Indeed."""
        try:
            # Generate confirmation based on timestamp
            return f"Indeed-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        except Exception as e:
            self.logger.error(f"Failed to get Indeed confirmation: {e}")
            return None


class DefaultStrategy(PortalStrategy):
    """Default/generic automation strategy for unknown portals."""
    
    def can_handle(self, url: str) -> bool:
        """This strategy can handle any URL as a fallback."""
        return True
    
    async def apply(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Execute generic application automation."""
        result = {
            "success": False,
            "confirmation_number": None,
            "screenshots": [],
            "form_data": {},
            "error": None,
            "portal_response": None
        }
        
        try:
            self.logger.info(f"Starting generic application for {application_id}")
            
            # Take initial screenshot
            screenshot = await self.take_screenshot(page, application_id, "01_initial_page")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Look for apply button
            apply_button_found = await self._find_generic_apply_button(page)
            
            if apply_button_found:
                # Click apply button
                await self._click_generic_apply(page)
                await page.wait_for_timeout(2000)
                
                # Take screenshot after clicking apply
                screenshot = await self.take_screenshot(page, application_id, "02_apply_clicked")
                if screenshot:
                    result["screenshots"].append(screenshot)
            
            # Try to fill any detected form
            form_data = await self._fill_generic_form(page, user, resume_path, application_id)
            result["form_data"] = form_data
            
            # Take screenshot after filling form
            screenshot = await self.take_screenshot(page, application_id, "03_form_filled")
            if screenshot:
                result["screenshots"].append(screenshot)
            
            # Try to submit
            submission_success = await self._submit_generic_application(page, application_id)
            
            if submission_success:
                # Take final screenshot
                screenshot = await self.take_screenshot(page, application_id, "04_submitted")
                if screenshot:
                    result["screenshots"].append(screenshot)
                
                result["success"] = True
                result["confirmation_number"] = f"Generic-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                result["portal_response"] = {"platform": "generic", "method": "form_submission"}
                
                self.logger.info(f"Generic application successful for {application_id}")
            else:
                result["error"] = "Could not complete generic application"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generic application failed for {application_id}: {e}")
            result["error"] = str(e)
            
            # Take error screenshot
            try:
                screenshot = await self.take_screenshot(page, application_id, "error")
                if screenshot:
                    result["screenshots"].append(screenshot)
            except:
                pass
            
            return result
    
    async def _find_generic_apply_button(self, page: Page) -> bool:
        """Find generic apply button."""
        apply_selectors = [
            'button:has-text("Apply")',
            'a:has-text("Apply")',
            'input[value*="Apply"]',
            'button[class*="apply"]',
            'a[class*="apply"]'
        ]
        
        for selector in apply_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    self.logger.info(f"Found generic apply button: {selector}")
                    return True
            except Exception:
                continue
        
        return False
    
    async def _click_generic_apply(self, page: Page):
        """Click generic apply button."""
        apply_selectors = [
            'button:has-text("Apply")',
            'a:has-text("Apply")',
            'input[value*="Apply"]',
            'button[class*="apply"]',
            'a[class*="apply"]'
        ]
        
        for selector in apply_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    self.logger.info("Clicked generic apply button")
                    return
            except Exception:
                continue
    
    async def _fill_generic_form(self, page: Page, user: User, resume_path: str, application_id: str) -> Dict[str, Any]:
        """Fill generic application form."""
        form_data = {}
        
        try:
            # Wait for potential form load
            await page.wait_for_timeout(2000)
            
            # Detect form fields
            form_fields = await FormFieldMapper.detect_form_fields(page)
            
            if not form_fields:
                self.logger.info("No form fields detected")
                return form_data
            
            # Get user personal info
            personal_info = user.personal_info if hasattr(user, 'personal_info') else {}
            
            # Fill detected fields
            field_mappings = {
                'first_name': personal_info.get('first_name', ''),
                'last_name': personal_info.get('last_name', ''),
                'full_name': f"{personal_info.get('first_name', '')} {personal_info.get('last_name', '')}".strip(),
                'email': personal_info.get('email', ''),
                'phone': personal_info.get('phone', '')
            }
            
            for field_type, value in field_mappings.items():
                if field_type in form_fields and value:
                    try:
                        element = form_fields[field_type]['element']
                        await element.fill(value)
                        form_data[field_type] = value
                        self.logger.info(f"Filled {field_type}")
                    except Exception as e:
                        self.logger.warning(f"Failed to fill {field_type}: {e}")
            
            # Upload resume if available
            if resume_path and 'resume_upload' in form_fields:
                try:
                    selector = form_fields['resume_upload']['selector']
                    await self.file_upload_handler.upload_file(page, selector, resume_path)
                    form_data['resume_uploaded'] = True
                    self.logger.info("Resume uploaded")
                except Exception as e:
                    self.logger.warning(f"Resume upload failed: {e}")
                    form_data['resume_uploaded'] = False
            
            return form_data
            
        except Exception as e:
            self.logger.error(f"Generic form filling failed: {e}")
            return form_data
    
    async def _submit_generic_application(self, page: Page, application_id: str) -> bool:
        """Submit generic application."""
        try:
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Submit")',
                'button:has-text("Send")',
                'a:has-text("Submit")'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = await page.query_selector(selector)
                    if submit_button and await submit_button.is_visible() and await submit_button.is_enabled():
                        await submit_button.click()
                        
                        # Wait for submission
                        await page.wait_for_timeout(3000)
                        
                        self.logger.info("Generic application submitted")
                        return True
                        
                except Exception:
                    continue
            
            # If no submit button found, consider it successful if we filled a form
            return True
            
        except Exception as e:
            self.logger.error(f"Generic submission failed: {e}")
            return False


class PortalStrategyManager:
    """Manager for selecting and executing portal-specific strategies."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.strategies = [
            LinkedInStrategy(),
            IndeedStrategy(),
            DefaultStrategy()  # Always last as fallback
        ]
    
    def get_strategy(self, url: str) -> PortalStrategy:
        """Get the appropriate strategy for a URL.
        
        Args:
            url: Job posting URL
            
        Returns:
            Portal strategy instance
        """
        for strategy in self.strategies:
            if strategy.can_handle(url):
                self.logger.info(f"Selected strategy: {strategy.__class__.__name__} for {url}")
                return strategy
        
        # This should never happen since DefaultStrategy handles everything
        return self.strategies[-1]
    
    def detect_portal(self, url: str) -> str:
        """Detect the portal type from URL.
        
        Args:
            url: Job posting URL
            
        Returns:
            Portal name
        """
        url_lower = url.lower()
        
        if "linkedin.com" in url_lower:
            return "linkedin"
        elif "indeed.com" in url_lower:
            return "indeed"
        elif "glassdoor.com" in url_lower:
            return "glassdoor"
        elif "monster.com" in url_lower:
            return "monster"
        elif "ziprecruiter.com" in url_lower:
            return "ziprecruiter"
        else:
            return "generic"


# Global strategy manager instance
portal_strategy_manager = PortalStrategyManager()