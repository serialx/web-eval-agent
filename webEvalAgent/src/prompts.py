#!/usr/bin/env python3

def get_ux_evaluation_prompt(url: str, task: str) -> str:
    """
    Generate a prompt for UI/UX evaluation.
    
    Args:
        url: The URL of the web application to evaluate
        task: The specific UX/UI aspect to test
        
    Returns:
        str: The formatted evaluation prompt
    """
    return f"""
### Prompt for UI Evaluation Agent - Web Application Testing

**Objective:**
Visit the target web application at the URL provided and evaluate the following UI component or feature based on the task description. Your goal is to determine whether the component is **functionally broken**, and/or if the **user experience (UX)** can be improved. If the component is broken, prioritize providing a detailed explanation of what's broken and **terminate the session early** to return this feedback as quickly as possible.

---

### Parameters:
- **URL:** {url}
- **Component Evaluation Task:** {task}

---

### Step 1: Navigate to the Website
- Open the application using the provided URL: {url}
- Wait for the page to load fully before interacting.

---

### Step 2: Read and Understand the Evaluation Task
- Carefully review the task: {task}
- Determine what part of the UI you should be focusing on.
- If you are unsure where the component is located, try using semantic cues from the task or page layout to locate it.

---

### Step 3: Evaluate for UI Bugs
- Interact with the component as a user would, following the guidance from the task.
- Check for signs of being broken, including:
  - Non-functioning buttons or input fields
  - Broken styling or layout issues (misaligned text, overlapping elements, etc.)
  - Console or network errors
  - Any interaction that leads to unexpected results

**If a bug is detected:**
- Stop further navigation immediately.
- Record the following:
  - A clear description of the bug
  - Steps to reproduce it
  - A screenshot if possible
  - Any relevant browser console output (if accessible)
- End the session and return your findings.

---

### Step 4: Evaluate for UX Improvements
If no bugs are found, assess the overall usability and user experience:
- Is the component easy to use and understand?
- Are labels, buttons, and affordances clear and intuitive?
- Is anything confusing or unintuitive about the layout or flow?
- Are there accessibility issues (e.g., low contrast, missing alt text, keyboard navigation issues)?

If improvements are needed:
- Describe the issue clearly.
- Suggest specific, actionable recommendations for improvement.

---

### Step 5: Output Summary
- If a **UI bug was found**, return:
  - **Type of bug**
  - **Steps to reproduce**
  - **Screenshot or error log** (if possible)
  - **End the session early**

- If **no bugs**, return:
  - **Summary of UX evaluation**
  - **List of suggested improvements** (if any)
  - **Confirmation that the component is functioning as expected**

**Important:** Your goal is to be fast and accurate. If something is clearly broken, do not continue testing—report the issue and stop.
"""
