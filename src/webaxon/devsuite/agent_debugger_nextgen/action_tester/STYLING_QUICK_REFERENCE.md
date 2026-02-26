# Action Tester Styling - Quick Reference

## CSS Classes Available

### Component Classes
- `.section-header` - Section headers with hover effect
- `.active-test-indicator` - Active test with glow animation
- `.test-list-container` - Test list container
- `.loading-spinner` - Spinning loader for async operations
- `.success-message` - Success feedback with green theme
- `.error-message` - Error feedback with red theme

### Usage Examples

#### Adding a Loading Spinner

```python
from webaxon.devsuite.agent_debugger_nextgen.ui.components.action_tester_tab import create_loading_spinner

# In your component
html.Div([
    html.Span("Processing..."),
    create_loading_spinner()
])
```

#### Success Message
```python
html.Div(
    "Operation completed successfully!",
    className='success-message'
)
```

#### Error Message
```python
html.Div(
    "Operation failed: Invalid input",
    className='error-message'
)
```

## Color Palette

### Primary Colors
- **Green (Success)**: `#19C37D` (hover: `#15A869`)
- **Red (Error/Close)**: `#FF6B6B` (hover: `#E85555`)
- **Blue (Info)**: `#4A9EFF` (hover: `#3A8EEF`)
- **Gray (Secondary)**: `#8E8EA0` (hover: `#7E7E90`)

### Background Colors
- **Dark Panel**: `#40414F`
- **Darker Panel**: `#2C2D3A`
- **Darkest**: `#1A1B26`
- **Text Primary**: `#ECECF1`
- **Text Secondary**: `#8E8EA0`

### Border Colors
- **Default**: `#565869`
- **Active**: `#19C37D`

## Animation Timings

- **Fast**: 0.1s (active states)
- **Normal**: 0.2s (hover effects, transitions)
- **Slow**: 0.3s (fade-in, slide-in)
- **Pulse**: 1.5s (loading states)
- **Glow**: 2s (active indicator)
- **Spin**: 0.8s (loading spinner)

## Responsive Breakpoints

- **Desktop**: > 1200px (60%/40% split)
- **Tablet**: 900px - 1200px (55%/45% split)
- **Mobile**: < 900px (100% stacked)

## Button States

### Default
```css
padding: 8px 16px
border-radius: 4px
font-size: 12px
font-weight: 500
```

### Hover
```css
transform: translateY(-1px)
box-shadow: 0 2px 8px rgba(color, 0.3)
transition: all 0.2s ease
```

### Active
```css
transform: translateY(0px)
transition: all 0.1s ease
```

### Disabled
```css
opacity: 0.5
cursor: not-allowed
```

## Scrollbar Styling

### Track
```css
background: #2C2D3A
border-radius: 4px
width: 8px
```

### Thumb
```css
background: #565869
border-radius: 4px
```

### Thumb Hover
```css
background: #6E6E81
```

## Common Patterns

### Section Container
```python
html.Div(
    children=[
        html.Div("Section Title", className='section-header'),
        html.Div("Content here...")
    ],
    style={
        'padding': '16px',
        'backgroundColor': '#40414F',
        'borderRadius': '6px',
        'marginBottom': '16px'
    }
)
```

### Interactive Button
```python
html.Button(
    'Action',
    id='my-button',
    style={
        'padding': '8px 16px',
        'backgroundColor': '#19C37D',
        'color': '#FFFFFF',
        'border': 'none',
        'borderRadius': '4px',
        'cursor': 'pointer',
        'fontSize': '12px',
        'fontWeight': '500'
    }
)
```

### Status Indicator
```python
html.Div(
    '🟢 Active',
    style={
        'fontSize': '12px',
        'color': '#8E8EA0',
        'fontFamily': 'monospace',
        'padding': '8px',
        'backgroundColor': 'rgba(0, 0, 0, 0.2)',
        'borderRadius': '4px'
    }
)
```

## Tips

1. **Use Existing Classes**: Leverage the CSS classes for consistent styling
2. **Match Colors**: Use the color palette for consistency
3. **Smooth Transitions**: Add `transition: all 0.2s ease` for interactive elements
4. **GPU Acceleration**: Use `transform` and `opacity` for animations
5. **Responsive**: Test at different screen sizes
6. **Accessibility**: Ensure disabled states are clear
7. **Loading States**: Use loading spinner for async operations
8. **Feedback**: Use success/error message classes for user feedback

## File Locations

- **CSS File**: `agent_debugger_nextgen/assets/action_tester_styles.css`
- **Component File**: `agent_debugger_nextgen/ui/components/action_tester_tab.py`
- **Documentation**: `agent_debugger_nextgen/action_tester/STYLING_*.md`

## Testing

Run visual test:
```bash
python WebAgent/test/devsuite/action_tester/test_styling_visual.py
```

## Support

For questions or issues with styling:
1. Check `STYLING_IMPLEMENTATION.md` for detailed documentation
2. Review `action_tester_styles.css` for available styles
3. Run visual test to verify styling works
