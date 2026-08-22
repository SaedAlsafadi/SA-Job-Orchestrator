from typing import Any, Dict, List, Optional
import structlog
from app.core.connectors.base import ApplicationConnector, ApplicationQuestion

logger = structlog.get_logger(__name__)

class WorkableApplicationConnector(ApplicationConnector):
    def name(self) -> str:
        return "workable"

    def can_handle(self, url: str) -> bool:
        return "workable.com" in url

    async def open_application(self, url: str, page) -> None:
        logger.info("Opening workable job page", url=url)
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        
        # Click Apply Now
        await self._click_apply_now(page)

    async def _click_apply_now(self, page):
        # Look for the apply button resiliently
        selectors = [
            'button[data-ui="apply-button"]',
            'a[data-ui="apply-button"]',
            'button:has-text("Apply for this job")',
            'button:has-text("Apply Now")',
            'a:has-text("Apply for this job")',
            'a:has-text("Apply Now")'
        ]
        
        clicked = False
        for sel in selectors:
            elements = await page.locator(sel).all()
            for el in elements:
                if await el.is_visible():
                    logger.info(f"Found apply button via selector: {sel}")
                    await el.click(force=True)
                    clicked = True
                    break
            if clicked: break
            
        if not clicked:
            logger.info("Apply button not found, perhaps we are already on an application page")
            
        # Wait for the panel/form to be visible
        try:
            # wait for form or dialog
            await page.wait_for_selector('form, [role="dialog"], [data-ui="application-form"]', timeout=5000)
        except Exception:
            logger.warning("Timeout waiting for application panel to open. Assuming it might already be open.")

    async def inspect_form(self, page) -> List[ApplicationQuestion]:
        # Inject JS to find all form fields (inputs, textareas, selects) inside the panel
        script = r"""
        () => {
            const fields = [];
            // Look for the main application container first
            let container = document.querySelector('form') || document.querySelector('[role="dialog"]') || document;
            
            container.querySelectorAll('input, textarea, select').forEach(el => {
                const type = el.type || el.tagName.toLowerCase();
                if (type === 'hidden' || type === 'submit' || type === 'button') return;
                
                // Find associated label
                let labelText = '';
                
                // 1. Direct label
                const labelEl = document.querySelector(`label[for="${el.id}"]`);
                if (labelEl) labelText = labelEl.innerText.trim();
                
                // 2. Nested label
                if (!labelText) {
                    const closestLabel = el.closest('label');
                    if (closestLabel) {
                        // For radios/checkboxes, the actual question is usually in a preceding tag or a fieldset legend
                        if (type === 'radio' || type === 'checkbox') {
                            const fieldset = el.closest('fieldset');
                            if (fieldset) {
                                const legend = fieldset.querySelector('legend');
                                if (legend) labelText = legend.innerText.trim() + " - " + closestLabel.innerText.trim();
                            } else {
                                // Try finding a strong or h3 tag in previous siblings or parent's previous siblings
                                let parent = closestLabel.parentElement;
                                while (parent && parent !== container) {
                                    if (parent.previousElementSibling) {
                                        const text = parent.previousElementSibling.innerText;
                                        if (text && text.length > 5) {
                                            labelText = text.trim() + " - " + closestLabel.innerText.trim();
                                            break;
                                        }
                                    }
                                    parent = parent.parentElement;
                                }
                            }
                            if (!labelText) labelText = closestLabel.innerText.trim();
                        } else {
                            // Extract text from the label excluding the input's own value
                            const clone = closestLabel.cloneNode(true);
                            const inputs = clone.querySelectorAll('input, select, textarea');
                            inputs.forEach(i => i.remove());
                            labelText = clone.innerText.trim();
                        }
                    }
                }
                
                // 3. Aria / Placeholder / Name
                if (!labelText) labelText = el.getAttribute('aria-label') || '';
                if (!labelText) labelText = el.placeholder || '';
                if (!labelText) labelText = el.name || el.id || '';
                
                // Clean up label text
                labelText = labelText.replace(/\n/g, ' ').replace(/\*/g, '').trim();
                
                let currentValue = el.value || "";
                if ((type === 'radio' || type === 'checkbox') && !el.checked) {
                    currentValue = ""; // Not selected
                }
                let isPrefilled = currentValue.trim() !== "";
                
                // Deduplicate radios with the same name, we don't want 5 questions for 1 radio group
                if ((type === 'radio' || type === 'checkbox') && el.name) {
                    const existing = fields.find(f => f.name === el.name);
                    if (existing) {
                        existing.options = existing.options || [];
                        existing.options.push(el.value || labelText);
                        if (el.checked) existing.current_value = el.value;
                        return; // Skip adding a new field
                    }
                }
                
                fields.push({
                    id: el.name || el.id || labelText,
                    name: el.name,
                    label: labelText,
                    type: type,
                    required: el.required || el.getAttribute('aria-required') === 'true',
                    current_value: currentValue,
                    prefilled: isPrefilled,
                    options: (type === 'radio' || type === 'checkbox') ? [el.value || labelText] : []
                });
            });
            return fields;
        }
        """
        raw_fields = await page.evaluate(script)
        questions = []
        for rf in raw_fields:
            qid = rf["id"]
            if not qid: continue
            questions.append(ApplicationQuestion(
                question_id=qid,
                label=rf["label"],
                input_type=rf["type"],
                required=rf["required"],
                current_value=rf["current_value"],
                prefilled=rf["prefilled"]
            ))
            
        return questions

    async def detect_cv_presence(self, page) -> bool:
        """Detect if the platform already has a CV loaded/prefilled."""
        # Simple heuristic: Look for a file input that has a filename adjacent to it, or a specific Workable CV badge
        script = r"""
        () => {
            // Some platforms show a span with the filename or a remove button when a CV is pre-populated
            const removeButtons = document.querySelectorAll('button[aria-label*="remove resume"], button[aria-label*="Remove resume"]');
            if (removeButtons.length > 0) return true;
            return false;
        }
        """
        return await page.evaluate(script)

    async def fill_field(self, page, question_id: str, value: str) -> None:
        selectors = [
            f'input[name="{question_id}"]',
            f'textarea[name="{question_id}"]',
            f'[data-ui="{question_id}"]',
            f'input[id="{question_id}"]',
            f'textarea[id="{question_id}"]'
        ]
        
        filled = False
        for sel in selectors:
            elements = await page.locator(sel).all()
            if elements:
                try:
                    await elements[0].fill(value)
                    filled = True
                    break
                except Exception:
                    pass
                    
        if not filled:
            logger.warning("Could not fill field with resilient selectors", question_id=question_id)
            raise ValueError(f"Could not fill field: {question_id}")

    async def upload_resume(self, page, file_path: str) -> None:
        selectors = [
            'input[type="file"][data-ui="resume"]',
            'input[type="file"][name="resume"]',
            'input[type="file"]'
        ]
        uploaded = False
        for sel in selectors:
            elements = await page.locator(sel).all()
            if elements:
                try:
                    await elements[0].set_input_files(file_path)
                    uploaded = True
                    break
                except Exception:
                    pass
        if not uploaded:
            logger.warning("Could not upload resume")

    async def answer_question(self, page, question: ApplicationQuestion) -> None:
        if question.answer and not question.requires_human:
            try:
                await self.fill_field(page, question.question_id, question.answer)
            except ValueError:
                question.requires_human = True

    async def capture_state(self, page) -> Dict[str, Any]:
        return {"url": page.url}

    async def submit(self, page) -> None:
        logger.info("Submitting Workable application")
        selectors = [
            'button[data-ui="submit-button"]',
            'button:has-text("Submit application")',
            'button[type="submit"]'
        ]
        
        clicked = False
        for sel in selectors:
            elements = await page.locator(sel).all()
            for el in elements:
                if await el.is_visible():
                    await el.click(force=True)
                    clicked = True
                    break
            if clicked: break
            
        if not clicked:
            raise ValueError("Could not confidently identify submit control on Workable.")

    async def capture_confirmation(self, page) -> str:
        logger.info("Verifying submission confirmation")
        # Wait for either a success message or a redirect
        try:
            # Check for generic success messages often seen in Workable modal/page
            await page.wait_for_selector(
                'text="Application submitted" , text="Success" , [data-ui="success-message"]', 
                timeout=10000
            )
            return "Confirmation verified"
        except Exception:
            # If the modal closes or URL changes, we might also consider it submitted
            raise ValueError("Could not verify submission confirmation.")
