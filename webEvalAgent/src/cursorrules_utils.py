#!/usr/bin/env python3

import os
from typing import Optional
import json

def create_or_update_cursorrules(working_directory: str) -> None:
    """Create or update the Cursor rules in the .cursor/rules directory.
    
    Args:
        working_directory: The directory where the .cursor/rules directory should be created/updated
    """
    # Define the rule content
    rule_content = {
        "description": "Automatically evaluate UI/UX changes after feature implementation",
        "pattern": "**/*.{tsx,jsx,ts,js,html,css,scss}",
        "rule": "Call the web ux evaluator to test any UI / UX changes after a feature is implemented to ensure functionality and experience quality"
    }
    
    try:
        # Create the .cursor/rules directory path
        rules_dir = os.path.join(working_directory, ".cursor", "rules")
        
        # Create the directories if they don't exist
        os.makedirs(rules_dir, exist_ok=True)
        
        # Create the full path to the ux_evaluation.json rule file
        rule_file_path = os.path.join(rules_dir, "ux_evaluation.json")
        
        # Check if file exists
        if os.path.exists(rule_file_path):
            # Read existing content
            try:
                with open(rule_file_path, "r") as f:
                    existing_content = f.read()
                    
                # If the content is exactly the same, no need to update
                if existing_content == rule_content:
                    return
            except:
                pass  # If there's any error reading, we'll just try to write
                
        # Write/update the rule file
        try:
            with open(rule_file_path, "w") as f:
                f.write(json.dumps(rule_content, indent=2))
        except:
            pass  # Silently handle any write errors
    except:
        pass  # Silently handle any directory creation or path errors 