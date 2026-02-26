"""
Shared scroll constants and utilities for WebDriver backends.

This module provides scroll-related constants and helper functions
used by both Selenium and Playwright backends.
"""

from typing import Tuple

# Relative distance percentages for viewport/container-based scrolling
RELATIVE_DISTANCE_PERCENTAGES = {
    'Small': 0.30,   # 30% of viewport/container height
    'Medium': 0.60,  # 60% of viewport/container height
    'Large': 0.90,   # 90% of viewport/container height
}

# Fixed distance in pixels for absolute scrolling
FIXED_DISTANCE_PIXELS = {
    'Small': 100,
    'Medium': 300,
    'Large': 500,
}


def compute_scroll_delta(direction: str, amount: int) -> Tuple[int, int]:
    """
    Compute (delta_x, delta_y) from direction and amount.

    Args:
        direction: Scroll direction - 'Up', 'Down', 'Left', 'Right' (case-insensitive)
        amount: Scroll amount in pixels

    Returns:
        Tuple of (delta_x, delta_y) for scrolling
    """
    direction = direction.capitalize()
    if direction == 'Down':
        return (0, amount)
    elif direction == 'Up':
        return (0, -amount)
    elif direction == 'Right':
        return (amount, 0)
    elif direction == 'Left':
        return (-amount, 0)
    return (0, 0)
