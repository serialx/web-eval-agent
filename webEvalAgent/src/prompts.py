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
    return f"""VISIT: {url} AND YOUR MAIN GOAL IS: {task}
"""
