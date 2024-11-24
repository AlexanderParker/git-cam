from colorama import init, Fore, Back, Style

# Initialize colorama for cross-platform color support
init()

class CLIFormatter:
    """Helper class for consistent CLI formatting"""
    
    @staticmethod
    def header(text):
        """Format section headers"""
        return f"\n{Fore.CYAN}{Style.BRIGHT}=== {text} ==={Style.RESET_ALL}\n"
    
    @staticmethod
    def success(text):
        """Format success messages"""
        return f"{Fore.GREEN}{Style.BRIGHT}✓ {text}{Style.RESET_ALL}"
    
    @staticmethod
    def error(text):
        """Format error messages"""
        return f"{Fore.RED}{Style.BRIGHT}✗ {text}{Style.RESET_ALL}"
    
    @staticmethod
    def warning(text):
        """Format warning messages"""
        return f"{Fore.YELLOW}{Style.BRIGHT}⚠ {text}{Style.RESET_ALL}"
    
    @staticmethod
    def input_prompt(text):
        """Format input prompts"""
        return f"{Fore.BLUE}{Style.BRIGHT}> {text}{Style.RESET_ALL}"
    
    @staticmethod
    def separator():
        """Return a separator line"""
        return f"{Fore.BLUE}{Style.DIM}{'─' * 80}{Style.RESET_ALL}"
    
    @staticmethod
    def diff_header():
        """Return a diff section header"""
        return f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT} DIFF {Style.RESET_ALL}"
    
    @staticmethod
    def review_header():
        """Return a review section header"""
        return f"{Back.GREEN}{Fore.WHITE}{Style.BRIGHT} REVIEW {Style.RESET_ALL}"
    
    @staticmethod
    def message_header():
        """Return a message section header"""
        return f"{Back.MAGENTA}{Fore.WHITE}{Style.BRIGHT} COMMIT MESSAGE {Style.RESET_ALL}"