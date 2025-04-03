## Operative WebAgentQA 
[operative.sh](https://www.operative.sh)'s MCP Server is an llm tool for coding agents to debug themselves. Allowing autonomous execution and debugging of code in your code editor for web apps. 

This tool augments your Code IDE experience (Cline, Cursor) to have a complete experience: 
- Navigate your webapp using BrowserUse (**we made BrowserUse 2x faster**!) 
- collect network requests/responses
- collect console log errors
To then be able to debug your application so you don't have to 


## Quick Start Cursor Installation (macOS/Linux) 
1. Get an api key [operative.sh](https://www.operative.sh) 
2. ```curl -LsSO https://operative.sh/webagentqa/install.sh | sh install.sh```
3. Now in Cursor Agent Mode, you can let our code agent debug your webapp for you with the `web_app_ux_evaluator` tool!
