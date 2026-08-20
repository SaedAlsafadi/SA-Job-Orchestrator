from typing import Any, Dict, List, Optional
import structlog
from app.core.connectors.base import ApplicationConnector, ApplicationQuestion

logger = structlog.get_logger(__name__)

class GreenhouseApplicationConnector(ApplicationConnector):
    def name(self) -> str:
        return "greenhouse"

    def can_handle(self, url: str) -> bool:
        return "greenhouse.io" in url

    async def open_application(self, url: str, page) -> None:
        logger.info("Opening Greenhouse job page", url=url)
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        
        # Click Apply Now (often just scrolls to the bottom on Greenhouse, or navigates to a form page)
        await self._click_apply_now(page)

    async def _click_apply_now(self, page):
        selectors = [
            'a#apply_button',
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
                    await el.click()
                    clicked = True
                    break
            if clicked: break
            
        if not clicked:
            logger.info("Apply button not found, assuming we are on the form page or it is already visible")
            
        # Wait for the form to be visible (Greenhouse forms usually have id "application_form")
        try:
            await page.wait_for_selector('form#application_form, form', timeout=5000)
        except Exception:
            logger.warning("Timeout waiting for application form. It might be heavily customized or broken.")

    async def inspect_form(self, page) -> List[ApplicationQuestion]:
        # Inject JS to find all form fields (inputs, textareas, selects)
        script = """
        () => {
            const fields = [];
            let container = document.querySelector('form#application_form') || document.querySelector('form') || document;
            
            container.querySelectorAll('input, textarea, select').forEach(el => {
                const type = el.type || el.tagName.toLowerCase();
                if (type === 'hidden' || type === 'submit' || type === 'button') return;
                
                // Find associated label
                let labelText = el.name || el.id;
                
                // Greenhouse usually puts labels wrapping the input, or right before it in a div
                const labelEl = document.querySelector(`label[for="${el.id}"]`) || el.closest('label') || el.closest('.field')?.querySelector('label');
                if (labelEl) {
                    // Remove asterisks from required fields
                    labelText = labelEl.innerText.replace('*', '').trim();
                } else {
                    const ariaLabel = el.getAttribute('aria-label');
                    if (ariaLabel) labelText = ariaLabel;
                }
                
                let currentValue = el.value || "";
                let isPrefilled = currentValue.trim() !== "";
                
                fields.push({
                    id: el.name || el.id || labelText,
                    name: el.name,
                    label: labelText,
                    type: type,
                    required: el.required || el.getAttribute('aria-required') === 'true',
                    current_value: currentValue,
                    prefilled: isPrefilled
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
        # Greenhouse often relies on standard file input unless user is logged in
        # We check for a file input with a value, or a "Remove" button
        script = """
        () => {
            // Check for buttons with specific aria labels or data attributes
            const removeButtons = document.querySelectorAll('button[aria-label*="remove resume"], button[aria-label*="Remove resume"], [data-cv-present="true"]');
            if (removeButtons.length > 0) return true;
            
            // Check for anchors containing the text 'Remove resume'
            const links = Array.from(document.querySelectorAll('a'));
            if (links.some(a => a.innerText.includes('Remove resume'))) return true;
            
            return false;
        }
        """
        return await page.evaluate(script)

    async def fill_field(self, page, question_id: str, value: str) -> None:
        selectors = [
            f'input[name="{question_id}"]',
            f'textarea[name="{question_id}"]',
            f'select[name="{question_id}"]',
            f'input[id="{question_id}"]',
            f'textarea[id="{question_id}"]',
            f'select[id="{question_id}"]'
        ]
        
        filled = False
        for sel in selectors:
            elements = await page.locator(sel).all()
            if elements:
                try:
                    # Select behaves differently from fill
                    el_type = await elements[0].evaluate('el => el.tagName.toLowerCase()')
                    if el_type == 'select':
                        await elements[0].select_option(label=value) # Simplification, in reality we might need to find exact option
                    else:
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
            'input[type="file"][name="resume"]',
            'input[type="file"][id="resume"]',
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
        raise NotImplementedError("Submission is disabled for MVP")

    async def capture_confirmation(self, page) -> str:
        return "Not submitted"
