#!/bin/bash

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Spinner animation characters
spin=('-' '\\' '|' '/')

# Function to show spinner
show_spinner() {
    local pid=$1
    local delay=0.1
    local spinstr='|/-\'
    while [ "$(ps a | awk '{print $1}' | grep $pid)" ]; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
}

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}${BOLD}=== $1 ===${NC}\n"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

# Function to print info messages
print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Function to validate API key format and check with server
validate_api_key() {
    local api_key=$1

    # Check with server
    print_info "Validating API key with Operative servers..."
    local response
    response=$(curl -s -H "x-operative-api-key: $api_key" \
                  "https://operative-backend.onrender.com/api/validate-key")
    
    # Check if curl request was successful
    if [ $? -ne 0 ]; then
        print_error "Could not connect to validation server. Please check your internet connection."
    fi

    # Parse response using jq
    if echo "$response" | jq -e '.valid' > /dev/null; then
        return 0
    else
        local error_message
        error_message=$(echo "$response" | jq -r '.message')
        echo -e "${RED}✗ $error_message${NC}" >&2
        return 1
    fi
}

# Define paths
MCP_FILE="$HOME/.cursor/mcp.json"
TEMP_DIR="$HOME/.cursor/web-agent-qa"

# Print welcome message with ASCII art
cat << "EOF"                                                    
                                    $$$$                                    
                                 $$$    $$$                                 
                              $$$          $$$                              
                           $$$     $$$$$$     $$$                           
                        $$$     $$$  $$  $$$     $$$c                       
                    c$$$     $$$     $$     $$$     $$$$                    
                   $$$$      $$$x    $$     $$$      $$$$                   
                   $$  $$$      >$$$ $$ ;$$$      $$$  $$                   
                   $$     $$$       $$$$8      $$$     $$                   
                   $$        $$$            $$$        $$                   
                   $$   $$$     $$$$     $$$     $$$   $$                   
                   $$   $  $$$     I$$$$$     $$$  $   $$                   
                   $$   $     $$$    $$    $$$     $   $$                   
                   $$   $     $$$$   $$   $$$$     $   $$                   
                   $$   $  $$$   $   $$   $   $$$  $   $$                   
                   $$   $$$      $   $$   $      $$$   $$                   
                   $$     $$$    $   $$   $    $$$     $$                   
                    $$$      $$$ $   $$   $ $$$      $$$                    
                       $$$      $$   $$   $$      $$$                       
                          $$$        $$        $$$                          
                             $$$     $$     $$$                             
                                $$$  $$  $$$                                
                                   $$$$$$                                   
EOF

echo -e "\n${BOLD}🚀 Welcome to the Operative WebAgentQA Installer${NC}"
echo -e "This script will set up everything you need to get started.\n"

# Create necessary directories
print_header "Setting up directories"
mkdir -p "$HOME/.cursor" "$TEMP_DIR"
print_success "Created necessary directories"

# Check for required dependencies
print_header "Checking dependencies"

# Check for Git
if ! command -v git &> /dev/null; then
    print_error "Git is not installed. Please install Git first:
    ${YELLOW}• macOS:${NC} brew install git
    ${YELLOW}• Linux:${NC} sudo apt-get install git"
fi
print_success "Git is installed"

# Check and install UV
if ! command -v uv &> /dev/null; then
    print_info "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh &
    show_spinner $!
    print_success "UV installed successfully"
else
    print_success "UV is already installed"
fi

# Check and install jq
if ! command -v jq &> /dev/null; then
    print_info "Installing jq..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq &
        show_spinner $!
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y jq &
        show_spinner $!
    fi
    print_success "jq installed successfully"
else
    print_success "jq is already installed"
fi

# Clone/update repository
print_header "Setting up repository"
echo -e "Cloning repository to ${BOLD}$TEMP_DIR${NC}..."
if git clone https://github.com/Operative-Sh/web-agent-qa.git "$TEMP_DIR" 2>/dev/null || (cd "$TEMP_DIR" && git pull); then
    print_success "Repository updated successfully"
else
    print_error "Failed to clone/update repository"
fi

# Configure MCP server
print_header "Configuring MCP server"

# Create initial MCP configuration if needed
if [ ! -f "$MCP_FILE" ]; then
    echo '{
  "mcpServers": {}
}' > "$MCP_FILE"
    print_success "Created new MCP configuration file"
fi

# Prompt for API key (updated with better error handling)
print_header "API Key Configuration"
echo -e "An Operative.sh API key is required for this installation."
echo -e "If you don't have one, please visit ${BOLD}https://operative.sh${NC} to get your key.\n"

API_KEY=""
while true; do
    read -p "Please enter your Operative.sh API key: " API_KEY
    if [ -z "$API_KEY" ]; then
        echo -e "${RED}✗ API key cannot be empty${NC}"
        continue
    fi
    
    # Server validation
    if validate_api_key "$API_KEY"; then
        print_success "API key validated successfully"
        break
    else
        echo -e "${YELLOW}Would you like to try again? (y/n)${NC}"
        read -r response
        if [[ "$response" =~ ^[Nn] ]]; then
            print_error "Installation cancelled - valid API key required"
        fi
    fi
done

# Define server configuration (updated with user's API key)
NEW_SERVER='{
  "command": "uv",
  "args": [
    "run",
    "--directory",
    "'$TEMP_DIR'",
    "mcp_server.py"
  ],
  "env": {
    "OPERATIVE_API_KEY": "'$API_KEY'"
  }
}'

# Validate and update configuration
if echo "$NEW_SERVER" | jq '.' > /dev/null; then
    jq --arg name "web-agent-qa" \
       --argjson config "$NEW_SERVER" \
       '.mcpServers[$name] = $config' \
       "$MCP_FILE" > "$MCP_FILE.tmp" && mv "$MCP_FILE.tmp" "$MCP_FILE"
    print_success "MCP server configuration updated successfully"
else
    print_error "Invalid JSON configuration"
fi

# Installation complete
print_header "Installation Complete! 🎉"
echo -e "Your Operative WebAgentQA environment has been set up successfully."
echo -e "Repository location: ${BOLD}$TEMP_DIR${NC}"
echo -e "\nThank you for installing! 🙏\n"
echo -e "Built with ❤️ by Operative.sh"
