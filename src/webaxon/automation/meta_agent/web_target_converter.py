"""
Web-specific Target Converter for the Meta Agent Workflow pipeline.

Converts ``__id__`` targets from agent traces into stable CSS/XPath/aria
selectors using HTML snapshots and BeautifulSoup.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agent_foundation.automation.meta_agent.models import TraceStep
from agent_foundation.automation.meta_agent.target_converter import (
    TargetConverterBase,
    TargetSpec,
    TargetSpecWithFallback,
)

# ---------------------------------------------------------------------------
# Optional BeautifulSoup import — fall back to regex when unavailable.
# ---------------------------------------------------------------------------

try:
    from bs4 import BeautifulSoup, Tag  # type: ignore[import-untyped]

    _HAS_BS4 = True
except ImportError:  # pragma: no cover
    _HAS_BS4 = False


# ---------------------------------------------------------------------------
# Regex helpers (used when bs4 is not available)
# ---------------------------------------------------------------------------

_ATTR_RE = re.compile(r'''([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')''')
_TAG_RE = re.compile(r"<(\w+)\s")


def _parse_attrs(element_html: str) -> Dict[str, str]:
    """Extract attribute dict from an element's opening tag via regex."""
    attrs: Dict[str, str] = {}
    for m in _ATTR_RE.finditer(element_html):
        attrs[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
    return attrs


def _parse_tag_name(element_html: str) -> Optional[str]:
    """Extract the tag name from an element's opening tag."""
    m = _TAG_RE.match(element_html.strip())
    return m.group(1) if m else None


def _extract_text_content(element_html: str) -> Optional[str]:
    """Extract visible text content from element HTML (regex-based)."""
    # Strip all tags and collapse whitespace
    text = re.sub(r"<[^>]+>", "", element_html).strip()
    text = re.sub(r"\s+", " ", text)
    return text if text else None


# ---------------------------------------------------------------------------
# WebTargetConverter
# ---------------------------------------------------------------------------


class WebTargetConverter(TargetConverterBase):
    """
    Converts ``__id__`` targets from agent traces into stable selectors.

    Uses HTML snapshots captured during trace collection to locate elements
    by ``__id__`` and generate alternative stable selectors.
    """

    # Selector stability priority (highest to lowest).
    STRATEGY_PRIORITY: List[str] = [
        "data-qa",
        "data-testid",
        "id",
        "aria",
        "xpath-text",
        "xpath-class",
        "css",
        "agent",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, trace_action: TraceStep) -> TargetSpecWithFallback:
        """
        Convert a ``__id__`` target to stable selectors.

        Uses *html_before* (preferred) or *html_after* as fallback to
        locate the element and generate selectors.  If neither snapshot
        is available, returns a single agent-based fallback strategy.
        """
        target = trace_action.target
        framework_id = self._extract_framework_id(target)

        if framework_id is None:
            # Not a __id__ target — return agent fallback
            return self._agent_fallback(trace_action)

        html = trace_action.html_before or trace_action.html_after
        if html is None:
            return self._agent_fallback(trace_action)

        element_html = self._find_element_by_id(html, framework_id)
        if element_html is None:
            return self._agent_fallback(trace_action)

        # Try each strategy in priority order, validate uniqueness.
        strategies: List[TargetSpec] = []
        strategy_methods = {
            "data-qa": self._try_data_attributes,
            "data-testid": self._try_data_attributes,
            "id": self._try_native_id,
            "aria": self._try_aria_selector,
            "xpath-text": self._try_xpath_with_text,
            "xpath-class": self._try_xpath_with_class,
            "css": self._try_css_selector,
        }

        seen_strategies: set[str] = set()
        for strategy_name in self.STRATEGY_PRIORITY:
            if strategy_name == "agent":
                continue  # handled as final fallback
            if strategy_name in seen_strategies:
                continue

            method = strategy_methods.get(strategy_name)
            if method is None:
                continue

            # _try_data_attributes may return either data-qa or data-testid
            specs = method(element_html)
            if specs is None:
                seen_strategies.add(strategy_name)
                continue

            # method may return a single spec or we call it once for both
            # data-qa and data-testid
            if not isinstance(specs, list):
                specs = [specs]

            for spec in specs:
                if spec.strategy in seen_strategies:
                    continue
                if self._validate_uniqueness(spec, html):
                    strategies.append(spec)
                seen_strategies.add(spec.strategy)

        if not strategies:
            return self._agent_fallback(trace_action)

        return TargetSpecWithFallback(strategies=strategies)

    # ------------------------------------------------------------------
    # Element location
    # ------------------------------------------------------------------

    def _find_element_by_id(
        self, html: str, framework_id: str
    ) -> Optional[str]:
        """
        Find element HTML by ``__id__`` attribute in the page source.

        Returns the element's outer HTML string, or *None* if not found.
        """
        if _HAS_BS4:
            soup = BeautifulSoup(html, "html.parser")
            el = soup.find(attrs={"__id__": framework_id})
            if el is not None and isinstance(el, Tag):
                return str(el)
            return None

        # Regex fallback
        pattern = re.compile(
            rf'<(\w+)\s[^>]*__id__\s*=\s*["\']'
            + re.escape(framework_id)
            + r"""['"][^>]*>"""
        )
        m = pattern.search(html)
        if m is None:
            return None
        # Return from match start to the corresponding closing tag
        tag_name = m.group(1)
        start = m.start()
        # Simple approach: find the closing tag
        close_tag = f"</{tag_name}>"
        close_idx = html.find(close_tag, m.end())
        if close_idx == -1:
            # Self-closing or no close tag — return the opening tag
            return m.group(0)
        return html[start : close_idx + len(close_tag)]

    # ------------------------------------------------------------------
    # Strategy generators
    # ------------------------------------------------------------------

    def _try_data_attributes(
        self, element_html: str
    ) -> Optional[List[TargetSpec]]:
        """Try ``data-qa`` and ``data-testid`` attributes."""
        attrs = self._get_attrs(element_html)
        results: List[TargetSpec] = []

        dqa = attrs.get("data-qa")
        if dqa:
            results.append(TargetSpec(strategy="data-qa", value=f'[data-qa="{dqa}"]'))

        dtid = attrs.get("data-testid")
        if dtid:
            results.append(
                TargetSpec(strategy="data-testid", value=f'[data-testid="{dtid}"]')
            )

        return results if results else None

    def _try_native_id(self, element_html: str) -> Optional[TargetSpec]:
        """Try native HTML ``id`` attribute."""
        attrs = self._get_attrs(element_html)
        html_id = attrs.get("id")
        if html_id:
            return TargetSpec(strategy="id", value=f"#{html_id}")
        return None

    def _try_aria_selector(self, element_html: str) -> Optional[TargetSpec]:
        """Try ``aria-label`` + role combination."""
        attrs = self._get_attrs(element_html)
        aria_label = attrs.get("aria-label")
        if not aria_label:
            return None

        role = attrs.get("role")
        tag = _parse_tag_name(element_html) or "*"

        if role:
            xpath = f'//{tag}[@role="{role}" and @aria-label="{aria_label}"]'
        else:
            xpath = f'//{tag}[@aria-label="{aria_label}"]'

        return TargetSpec(strategy="aria", value=xpath)

    def _try_xpath_with_text(self, element_html: str) -> Optional[TargetSpec]:
        """Generate XPath using text content."""
        text = _extract_text_content(element_html)
        if not text:
            return None

        tag = _parse_tag_name(element_html) or "*"

        # Use contains() for robustness against whitespace differences
        if len(text) > 50:
            text = text[:50]

        xpath = f'//{tag}[contains(text(), "{text}")]'
        return TargetSpec(strategy="xpath-text", value=xpath)

    def _try_xpath_with_class(self, element_html: str) -> Optional[TargetSpec]:
        """Generate XPath using class attribute."""
        attrs = self._get_attrs(element_html)
        css_class = attrs.get("class")
        if not css_class:
            return None

        tag = _parse_tag_name(element_html) or "*"
        # Use contains for class matching (handles multi-class elements)
        primary_class = css_class.split()[0]
        xpath = f'//{tag}[contains(@class, "{primary_class}")]'
        return TargetSpec(strategy="xpath-class", value=xpath)

    def _try_css_selector(self, element_html: str) -> Optional[TargetSpec]:
        """Generate CSS selector from tag + class combination."""
        tag = _parse_tag_name(element_html)
        if not tag:
            return None

        attrs = self._get_attrs(element_html)
        css_class = attrs.get("class")

        if css_class:
            # Use the first class for a concise selector
            primary_class = css_class.split()[0]
            selector = f"{tag}.{primary_class}"
        else:
            # Tag-only selector (less specific)
            selector = tag

        return TargetSpec(strategy="css", value=selector)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_uniqueness(self, spec: TargetSpec, html: str) -> bool:
        """
        Verify the selector matches exactly one element in the HTML.

        Returns *True* if exactly one match, *False* otherwise.
        """
        if _HAS_BS4:
            return self._validate_uniqueness_bs4(spec, html)
        return self._validate_uniqueness_regex(spec, html)

    def _validate_uniqueness_bs4(self, spec: TargetSpec, html: str) -> bool:
        """Validate uniqueness using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")

        if spec.strategy in ("data-qa", "data-testid"):
            # CSS attribute selector
            matches = soup.select(spec.value)
        elif spec.strategy == "id":
            # #id selector
            html_id = spec.value.lstrip("#")
            matches = soup.find_all(id=html_id)
        elif spec.strategy == "css":
            try:
                matches = soup.select(spec.value)
            except Exception:
                return False
        elif spec.strategy in ("aria", "xpath-text", "xpath-class"):
            # XPath-based — use regex counting as bs4 doesn't support xpath
            return self._validate_uniqueness_regex(spec, html)
        else:
            return False

        return len(matches) == 1

    def _validate_uniqueness_regex(self, spec: TargetSpec, html: str) -> bool:
        """Validate uniqueness using regex (fallback for xpath and non-bs4)."""
        value = spec.value

        if spec.strategy in ("data-qa", "data-testid"):
            # Extract attribute name and value from [attr="val"]
            m = re.match(r'\[([\w-]+)="([^"]+)"\]', value)
            if not m:
                return False
            attr_name, attr_val = m.group(1), m.group(2)
            pattern = re.compile(
                rf'{re.escape(attr_name)}\s*=\s*["\']'
                + re.escape(attr_val)
                + r"""['"]"""
            )
            return len(pattern.findall(html)) == 1

        if spec.strategy == "id":
            html_id = value.lstrip("#")
            pattern = re.compile(
                r'''id\s*=\s*["']''' + re.escape(html_id) + r"""['"]"""
            )
            return len(pattern.findall(html)) == 1

        if spec.strategy == "aria":
            # Extract aria-label from xpath
            m = re.search(r'@aria-label="([^"]+)"', value)
            if not m:
                return False
            label = m.group(1)
            pattern = re.compile(
                r'''aria-label\s*=\s*["']''' + re.escape(label) + r"""['"]"""
            )
            return len(pattern.findall(html)) == 1

        if spec.strategy == "xpath-text":
            # Extract text from contains(text(), "...")
            m = re.search(r'contains\(text\(\),\s*"([^"]+)"\)', value)
            if not m:
                return False
            text = m.group(1)
            # Count elements containing this text (approximate)
            # Look for text between > and <
            pattern = re.compile(r">" + re.escape(text))
            return len(pattern.findall(html)) == 1

        if spec.strategy == "xpath-class":
            # Extract class from contains(@class, "...")
            m = re.search(r'contains\(@class,\s*"([^"]+)"\)', value)
            if not m:
                return False
            cls = m.group(1)
            pattern = re.compile(
                r'''class\s*=\s*["'][^"']*''' + re.escape(cls) + r"""[^"']*['"]"""
            )
            return len(pattern.findall(html)) == 1

        if spec.strategy == "css":
            # Simple tag.class counting
            parts = value.split(".")
            tag = parts[0] if parts else ""
            cls = parts[1] if len(parts) > 1 else ""
            if cls:
                pattern = re.compile(
                    rf"<{re.escape(tag)}\s[^>]*class\s*=\s*"
                    + r"""["'][^"']*"""
                    + re.escape(cls)
                    + r"""[^"']*['"]"""
                )
            else:
                pattern = re.compile(rf"<{re.escape(tag)}[\s>]")
            return len(pattern.findall(html)) == 1

        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_attrs(self, element_html: str) -> Dict[str, str]:
        """Get attributes from element HTML (bs4 or regex)."""
        if _HAS_BS4:
            soup = BeautifulSoup(element_html, "html.parser")
            el = soup.find()
            if el and isinstance(el, Tag):
                return {k: (v if isinstance(v, str) else " ".join(v)) for k, v in el.attrs.items()}
            return {}
        return _parse_attrs(element_html)

    @staticmethod
    def _extract_framework_id(target: Any) -> Optional[str]:
        """
        Extract the ``__id__`` value from a target specification.

        Handles string targets like ``"__id__=elem_42"`` and dict targets
        with a ``strategy`` of ``"__id__"``.
        """
        if target is None:
            return None

        if isinstance(target, str):
            # "elem_42" or "__id__=elem_42"
            if target.startswith("__id__="):
                return target[len("__id__="):]
            return None

        if isinstance(target, dict):
            if target.get("strategy") == "__id__":
                return target.get("value")
            return None

        # Dataclass-like with strategy/value attributes
        strategy = getattr(target, "strategy", None)
        if strategy == "__id__":
            return getattr(target, "value", None)

        return None

    def _agent_fallback(self, trace_action: TraceStep) -> TargetSpecWithFallback:
        """Create an agent-based fallback targeting strategy."""
        description = trace_action.reasoning or str(trace_action.target) or "element"
        return TargetSpecWithFallback(
            strategies=[TargetSpec(strategy="agent", value=description)]
        )
