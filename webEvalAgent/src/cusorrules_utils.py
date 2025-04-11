#!/usr/bin/env python3

import os
from typing import Optional

def create_or_update_cusorrules(working_directory: str) -> None:
    """Create or update the .cusorrules file in the specified directory.
    
    Args:
        working_directory: The directory where the .cusorrules file should be created/updated
    """
    rule_content = "- Call the web ux evaluator to test any UI / UX changes after a feature is implemented to ensure functionality and experience quality"
    
    # Create the full path to the .cusorrules file
    cusorrules_path = os.path.join(working_directory, ".cusorrules")
    
    # Check if file exists
    if os.path.exists(cusorrules_path):
        # Read existing content
        with open(cusorrules_path, "r") as f:
            content = f.read()
        
        # Check if the rule is already present
        if rule_content not in content:
            # Append rule on a new line
            with open(cusorrules_path, "a") as f:
                # Add a newline if the file doesn't end with one
                if content and not content.endswith("\n"):
                    f.write("\n")
                f.write(rule_content + "\n")
                return
            
        # If we're here, the rule already exists in the file
        return
    else:
        # Create a new file with the rule
        with open(cusorrules_path, "w") as f:
            f.write(rule_content + "\n")
            return 