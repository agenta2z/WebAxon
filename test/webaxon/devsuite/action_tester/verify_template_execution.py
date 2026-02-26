"""
Quick verification that the template can be loaded and parsed correctly.
This ensures the template is valid and ready for use.
"""
import sys
from pathlib import Path

# Add paths for imports
project_root = Path(__file__).parent.parent.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from webaxon.automation.schema import load_sequence_from_string

# Import the template function directly from the file
sys.path.insert(0, str(project_root / "src" / "webaxon" / "devsuite" / "agent_debugger_nextgen" / "action_tester"))
from models import get_default_sequence_template


def main():
    print("Verifying default template can be loaded and parsed...\n")
    
    # Get the template
    template = get_default_sequence_template()
    
    print("Template JSON:")
    print("=" * 70)
    print(template)
    print("=" * 70)
    print()
    
    # Parse it
    try:
        sequence = load_sequence_from_string(template)
        print("✅ Template parsed successfully!")
        print()
        print(f"Sequence ID: {sequence.id}")
        print(f"Version: {sequence.version}")
        print(f"Description: {sequence.description}")
        print(f"Number of actions: {len(sequence.actions)}")
        print()
        
        print("Actions:")
        for i, action in enumerate(sequence.actions, 1):
            strategy = action.target.strategy if action.target else "N/A"
            target_value = action.target.value if action.target else "N/A"
            print(f"  {i}. {action.id}")
            print(f"     Type: {action.type}")
            print(f"     Strategy: {strategy}")
            print(f"     Target: {target_value}")
            if action.args:
                print(f"     Args: {action.args}")
            print()
        
        # Verify all strategies are present
        strategies = set()
        for action in sequence.actions:
            if action.target:
                strategies.add(action.target.strategy)
        
        required = {"id", "__id__", "xpath", "css", "literal"}
        if strategies == required:
            print("✅ All 5 target strategies are present!")
            print(f"   Strategies: {sorted(strategies)}")
        else:
            print(f"⚠️  Missing strategies: {required - strategies}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to parse template: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
