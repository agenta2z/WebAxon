"""
Data models for Action Tester.

Defines the core data structures for managing tests with multi-test architecture.
Each test corresponds to one browser tab in a single global WebDriver instance.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# Path to the default sequence template JSON file
DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "default_sequence_template.json"


def get_default_sequence_template() -> str:
    """
    Get default action sequence template from JSON file.

    Returns:
        JSON string demonstrating all target strategies (ID, __ID__, XPATH, CSS, LITERAL).
        Users can modify the target selectors and text as needed.

        For composite actions like input_and_submit, use space-separated element IDs
        in the target field (e.g., "input-elem submit-btn").
    """
    try:
        with open(DEFAULT_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            # Load and re-dump to ensure consistent formatting
            data = json.load(f)
            return json.dumps(data, indent=2)
    except Exception as e:
        # Fallback to minimal template if file not found
        print(f"Warning: Could not load default template from {DEFAULT_TEMPLATE_PATH}: {e}")
        return '{"version": "1.0", "id": "fallback", "actions": []}'


@dataclass
class Test:
    """
    Represents a test with browser tab and state.
    Each test has its own browser tab, JSON editor content, and execution results.
    """
    test_id: str
    test_name: str
    tab_handle: str  # WebDriver window handle
    json_content: str = field(default_factory=get_default_sequence_template)
    execution_results: List[Dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def update_content(self, json_content: str) -> None:
        """Update JSON editor content."""
        self.json_content = json_content
        
    def set_results(self, results: List[Dict]) -> None:
        """Set execution results."""
        self.execution_results = results
        
    def clear_results(self) -> None:
        """Clear execution results."""
        self.execution_results = []


@dataclass
class TestInfo:
    """Test information for UI display."""
    test_id: str
    test_name: str
    is_active: bool
    created_at: datetime


@dataclass
class BrowserStatus:
    """Browser status information for UI display."""
    active: bool
    status_indicator: str  # '🟢 Active' or '🔴 Not Active'
    window_count: int
    window_count_text: str  # 'N tab(s) open'
    active_window: str  # 'Tab N - "Title"' or 'None'
    current_url: str  # URL or '—'
    page_title: str  # Title or '—'


@dataclass
class SequenceValidationResult:
    """Result of JSON sequence validation."""
    valid: bool
    sequence_id: Optional[str] = None
    action_count: Optional[int] = None
    error: Optional[str] = None


@dataclass
class ActionStepResult:
    """Result of a single action step execution."""
    action_id: str
    action_type: str
    success: bool
    value: Any = None
    error: Optional[str] = None


@dataclass
class ElementIDResult:
    """Result of element ID assignment."""
    success: bool
    elements_tagged: Optional[int] = None
    error: Optional[str] = None
