from typing import Any, Dict, List, Optional
import structlog
from app.core.connectors.base import ApplicationConnector, ApplicationQuestion

logger = structlog.get_logger(__name__)

class LeverApplicationConnector(ApplicationConnector):
    def name(self) -> str:
        return "lever"

    def can_handle(self, url: str) -> bool:
        return "lever.co" in url

    async def open_application(self, url: str, page) -> None:
        logger.info("Opening Lever job page", url=url)
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        
        # If not already on the apply page, click the apply button
        if "/apply" not in page.url:
            await self._click_apply_now(page)

    async def _click_apply_now(self, page):
        selectors = [
            'a[data-qa="btn-apply-bottom"]',
            'a[data-qa="show-page-apply"]',
            'a:has-text("Apply for this job")',
            'a:has-text("Apply")',
            'button:has-text("Apply for this job")'
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
            logger.info("Apply button not found, assuming we are on the form page")
            
        try:
            await page.wait_for_selector('form', timeout=5000)
            await page.wait_for_load_state('networkidle')
        except Exception:
            logger.warning("Timeout waiting for application form.")

    async def inspect_form(self, page) -> List[ApplicationQuestion]:
        script = """
        () => {
            const fields = [];
            let container = document.querySelector('form') || document;
            
            container.querySelectorAll('input, textarea, select').forEach(el => {
                const type = el.type || el.tagName.toLowerCase();
                if (type === 'hidden' || type === 'submit' || type === 'button') return;
                
                let labelText = el.name || el.id;
                
                // Find associated label
                // Lever often puts inputs inside labels, or right after them in a .application-field
                const labelEl = document.querySelector(`label[for="${el.id}"]`) || 
                                el.closest('label') || 
                                el.closest('.application-field, .application-question')?.querySelector('.application-label, .application-question');
                                
                if (labelEl) {
                    // Clean label text
                    let clone = labelEl.cloneNode(true);
                    // Remove required indicators or sub-text if needed
                    const reqStar = clone.querySelector('.req, .application-label-req');
                    if (reqStar) clone.removeChild(reqStar);
                    labelText = clone.innerText.trim();
                }
                
                // If it's a radio or checkbox group, the question might be higher up
                if (type === 'radio' || type === 'checkbox') {
                     const groupLabel = el.closest('.application-field, .application-question')?.querySelector('.application-label, .application-question');
                     if (groupLabel) {
                         labelText = groupLabel.innerText.trim();
                     }
                }
                
                let currentValue = el.value || "";
                if ((type === 'radio' || type === 'checkbox') && !el.checked) {
                    currentValue = "";
                }
                
                let isPrefilled = currentValue.trim() !== "";
                
                let isRequired = el.required || el.hasAttribute('required') || el.closest('.application-field')?.querySelector('.application-label-req') !== null;
                
                fields.push({
                    id: el.name || el.id || labelText,
                    name: el.name,
                    label: labelText,
                    type: type,
                    required: isRequired,
                    current_value: currentValue,
                    prefilled: isPrefilled
                });
            });
            return fields;
        }
        """
        raw_fields = await page.evaluate(script)
        
        # Deduplicate radios (we just want one Question per group, but for MVP we'll treat them as text-like matching if needed)
        # Actually, let's keep them and the engine will skip or try to fill.
        questions = []
        seen_names = set()
        for rf in raw_fields:
            qid = rf["name"] or rf["id"]
            if not qid: continue
            
            if rf["type"] in ['radio', 'checkbox'] and qid in seen_names:
                # Append option or skip. For now just skip dupes.
                continue
                
            seen_names.add(qid)
            
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
        script = """
        () => {
            const successIndicators = document.querySelectorAll('.resume-upload-success, .resume-upload-label-success, [data-qa="resume-upload-success"]');
            if (successIndicators.length > 0 && Array.from(successIndicators).some(el => el.style.display !== 'none')) {
                return true;
            }
            
            const removeButtons = Array.from(document.querySelectorAll('a, button'));
            if (removeButtons.some(b => b.innerText.includes('Remove resume') || b.innerText.includes('Remove CV'))) {
                return true;
            }
            return false;
        }
        """
        return await page.evaluate(script)

    async def fill_field(self, page, question_id: str, value: str) -> None:
        selectors = [
            f'input[name="{question_id}"]',
            f'textarea[name="{question_id}"]',
            f'select[name="{question_id}"]'
        ]
        
        filled = False
        for sel in selectors:
            elements = await page.locator(sel).all()
            if elements:
                try:
                    el_type = await elements[0].evaluate('el => el.tagName.toLowerCase()')
                    if el_type == 'select':
                        await elements[0].select_option(label=value)
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
