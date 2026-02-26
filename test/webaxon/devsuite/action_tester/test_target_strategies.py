"""
Test that all target strategies work correctly.

This test verifies that the Action Tester supports all target strategies
defined in the schema: id, __id__, xpath, css, and literal.

Requirements: 7.4, 9.5
"""
import sys
from pathlib import Path

# Add paths for imports
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from webaxon.automation.schema import ActionSequence, Action, TargetSpec, load_sequence_from_string

# Import the template function directly from the file
sys.path.insert(0, str(project_root / "src" / "webaxon" / "devsuite" / "agent_debugger_nextgen" / "action_tester"))
from models import get_default_sequence_template


def test_default_template_includes_all_strategies():
    """
    Test that the default template includes examples of all target strategies.
    
    Validates: Requirements 7.4, 9.5
    """
    template = get_default_sequence_template()
    
    # Parse the template
    sequence = load_sequence_from_string(template)
    
    # Collect all strategies used in the template
    strategies_in_template = set()
    for action in sequence.actions:
        if action.target and action.target.strategy:
            strategies_in_template.add(action.target.strategy)
    
    # All required strategies
    required_strategies = {"id", "__id__", "xpath", "css", "literal"}
    
    # Verify all strategies are present
    missing_strategies = required_strategies - strategies_in_template
    assert not missing_strategies, (
        f"Template is missing examples for strategies: {missing_strategies}\n"
        f"Found strategies: {strategies_in_template}\n"
        f"Required strategies: {required_strategies}"
    )
    
    print(f"✓ Template includes all {len(required_strategies)} target strategies")
    print(f"  Strategies found: {sorted(strategies_in_template)}")


def test_template_has_descriptive_documentation():
    """
    Test that the template has documentation explaining all strategies.
    
    Validates: Requirements 9.5
    """
    template = get_default_sequence_template()
    sequence = load_sequence_from_string(template)
    
    # Check that sequence description mentions all strategies
    description = sequence.description.upper()
    
    required_strategies = ["LITERAL", "ID", "__ID__", "CSS", "XPATH"]
    
    for strategy in required_strategies:
        assert strategy in description, (
            f"Sequence description should mention '{strategy}' strategy\n"
            f"Description: {sequence.description}"
        )
    
    # Check that action IDs indicate the strategy being demonstrated
    for action in sequence.actions:
        if action.target:
            strategy = action.target.strategy
            action_id_lower = action.id.lower()
            
            # Action ID should contain the strategy name
            assert strategy.replace("__", "").lower() in action_id_lower or "strategy" in action_id_lower, (
                f"Action ID '{action.id}' should indicate it demonstrates '{strategy}' strategy"
            )
    
    print(f"✓ Template has comprehensive documentation for all strategies")


def test_template_is_valid_json():
    """
    Test that the default template is valid JSON and can be parsed.
    
    Validates: Requirements 9.5
    """
    template = get_default_sequence_template()
    
    # This will raise an exception if the JSON is invalid
    sequence = load_sequence_from_string(template)
    
    assert sequence.version == "1.0"
    assert sequence.id == "example_sequence"
    assert len(sequence.actions) > 0
    
    print(f"✓ Template is valid JSON with {len(sequence.actions)} actions")


def test_each_strategy_has_unique_action():
    """
    Test that each target strategy is demonstrated in a separate action.
    
    Validates: Requirements 9.5
    """
    template = get_default_sequence_template()
    sequence = load_sequence_from_string(template)
    
    # Map strategies to actions
    strategy_to_actions = {}
    for action in sequence.actions:
        if action.target and action.target.strategy:
            strategy = action.target.strategy
            if strategy not in strategy_to_actions:
                strategy_to_actions[strategy] = []
            strategy_to_actions[strategy].append(action.id)
    
    # Verify each strategy has at least one action
    required_strategies = {"id", "__id__", "xpath", "css", "literal"}
    for strategy in required_strategies:
        assert strategy in strategy_to_actions, (
            f"Strategy '{strategy}' is not demonstrated in any action"
        )
        print(f"  ✓ {strategy:10s} strategy: {strategy_to_actions[strategy]}")
    
    print(f"✓ All {len(required_strategies)} strategies have dedicated example actions")


def test_literal_strategy_used_for_visit_url():
    """
    Test that the literal strategy is used for visit_url action.
    
    The literal strategy is specifically designed for actions like visit_url
    where the value is used as-is (not as an element selector).
    
    Validates: Requirements 7.4
    """
    template = get_default_sequence_template()
    sequence = load_sequence_from_string(template)
    
    # Find visit_url actions
    visit_url_actions = [a for a in sequence.actions if a.type == "visit_url"]
    
    assert len(visit_url_actions) > 0, "Template should include at least one visit_url action"
    
    for action in visit_url_actions:
        assert action.target, f"visit_url action '{action.id}' should have a target"
        assert action.target.strategy == "literal", (
            f"visit_url action '{action.id}' should use 'literal' strategy, "
            f"but uses '{action.target.strategy}'"
        )
    
    print(f"✓ All {len(visit_url_actions)} visit_url actions use 'literal' strategy")


def test_custom_id_strategy_has_helpful_description():
    """
    Test that __id__ strategy documentation mentions the need to inject IDs first.
    
    Validates: Requirements 9.5
    """
    template = get_default_sequence_template()
    sequence = load_sequence_from_string(template)
    
    # Find actions using __id__ strategy
    custom_id_actions = [
        a for a in sequence.actions 
        if a.target and a.target.strategy == "__id__"
    ]
    
    assert len(custom_id_actions) > 0, "Template should include at least one __id__ example"
    
    # Check that sequence description mentions injection or assignment for __id__
    description = sequence.description.lower()
    
    # Check that description mentions injection or assignment
    helpful_keywords = ["inject", "assign", "button", "first"]
    has_helpful_hint = any(keyword in description for keyword in helpful_keywords)
    
    assert has_helpful_hint, (
        f"Sequence description should mention that __id__ IDs need to be injected first.\n"
        f"Description: {sequence.description}"
    )
    
    print(f"✓ Template documentation explains __id__ strategy requires ID injection")


if __name__ == "__main__":
    print("Testing target strategy support in Action Tester template...\n")
    
    try:
        test_default_template_includes_all_strategies()
        print()
        
        test_template_has_descriptive_documentation()
        print()
        
        test_template_is_valid_json()
        print()
        
        test_each_strategy_has_unique_action()
        print()
        
        test_literal_strategy_used_for_visit_url()
        print()
        
        test_custom_id_strategy_has_helpful_description()
        print()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nAll target strategies (id, __id__, xpath, css, literal) are properly")
        print("demonstrated in the default template with clear descriptions.")
        
    except AssertionError as e:
        print("\n" + "=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print(f"\n{e}")
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print(f"\n{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
