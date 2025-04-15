# 🚀 Operative.sh WebEvalAgent MCP Server

> *Let the code fix itself, you've got better things to do.*

![ezgif-30319083e68077](https://github.com/user-attachments/assets/2ea8dce2-5dc1-448d-91aa-51bfabcd3511)



## 🔥 Supercharge Your Debugging

[operative.sh](https://www.operative.sh)'s MCP Server unleashes LLM-powered agents to autonomously execute and debug web apps directly in your code editor.

## ⚡ Features

This weapon in your development arsenal transforms your Code IDE experience (Cline, Cursor):

- 🌐 **Navigate your webapp** using BrowserUse (**now 2x FASTER when using our backend!**)
- 📊 **Capture network traffic** - all requests/responses at your fingertips
- 🚨 **Collect console errors** - nothing escapes detection
- 🤖 **Autonomous debugging** - the Cursor agent calls the web QA agent mcp server to test if the code it wrote works as epected end-to-end.

## 🏁 Quick Start (macOS/Linux)


1. Run the installer
```bash
# Feel welcome to inspect the installer script like so:
# curl -LSf https://operative.sh/install.sh | less -N
# Download, install, and remove the installer script
curl -LSf https://operative.sh/install.sh -o install.sh && bash install.sh && rm install.sh
```
2. Unleash the agent in Cursor Agent Mode with web_app_ux_evaluator (verify tool refreshed or restart Cursor)
3. If any issues, see Issues section below
4. 

## 🛠️ Manual JSON Installation 
1. Run `uvx --from git+https://github.com/Operative-Sh/web-eval-agent.git webEvalAgent` with no api key first since Cursor doesn't wait for our deps to download!
2. `npm install -g playwright`
3. On startup, kill and then update your relevent MCP JSON: 

```json
"web-eval-agent": {
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/Operative-Sh/web-eval-agent.git",
    "webEvalAgent"
  ],
  "env": {
    "OPERATIVE_API_KEY": "YOUR_API_KEY"
  }
}
```

## 🛠️ Manual Windows Installation (Cline) 
```bash
# 1. Get your API key at operative.sh
# 2. Install uv (curl -LsSf https://astral.sh/uv/install.sh | sh)
# 3. uvx --from git+https://github.com/Operative-Sh/web-eval-agent.git playwright install
# 4. Unleash the agent in Cline with web_app_ux_evaluator (may have to restart Cline) 
```
## 🚨 Issues 
- Initial tool calls Playwright issues, fix pushed 4/14, `npm install -g playwright` playwright issues on tool call. 
- Any issues feel free to open an Issue on this repo! 

---

Built with <3 @ [operative.sh](https://www.operative.sh)
