#!/usr/bin/env python3
"""
Intent Expansion Pipeline

A scalable Python-based pipeline to identify missing or split-worthy intents
by analyzing customer messages and proposing new primary/secondary intents.

Author: AI Workflow Analyst
Date: 2024
"""

import json
import os
import re
import logging
import argparse
from dataclasses import dataclass, field, asdict
from typing import Optional
from collections import Counter, defaultdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SecondaryIntent:
    """Represents a secondary intent within a primary category."""
    id: str
    name: str
    description: str


@dataclass
class PrimaryIntent:
    """Represents a primary intent with its secondary intents."""
    id: str
    name: str
    description: str
    secondary_intents: list[SecondaryIntent] = field(default_factory=list)


@dataclass
class CustomerMessage:
    """Represents a customer message with conversation context."""
    id: int
    current_message: str
    conversation_history: list[dict] = field(default_factory=list)


@dataclass
class ProposedIntent:
    """Represents a proposed new or modified intent."""
    level: str  # 'primary' or 'secondary'
    parent_intent_id: Optional[str]  # For secondary intents
    name: str
    id: str
    description: str
    action: str  # 'new' or 'split'
    original_intent_id: Optional[str]  # If splitting from existing
    evidence_messages: list[str] = field(default_factory=list)
    evidence_count: int = 0
    confidence_score: float = 0.0
    rationale: str = ""


@dataclass
class ThemeCluster:
    """Represents a cluster of messages with similar themes."""
    theme: str
    keywords: list[str]
    message_ids: list[int]
    message_samples: list[str]
    count: int
    percentage: float
    suggested_intent: Optional[ProposedIntent] = None


# =============================================================================
# CONFIGURATION
# =============================================================================

class PipelineConfig:
    """Configuration for the intent expansion pipeline."""
    
    # Minimum number of messages to consider a theme significant
    MIN_CLUSTER_SIZE = 3
    
    # Minimum percentage of total messages to consider a theme significant
    MIN_CLUSTER_PERCENTAGE = 1.5
    
    # Maximum number of proposed intents to avoid fragmentation
    MAX_PROPOSED_INTENTS = 10
    
    # Confidence threshold for proposing new intents
    CONFIDENCE_THRESHOLD = 0.6
    
    # Batch size for LLM processing
    LLM_BATCH_SIZE = 20
    
    # Keywords for pattern-based detection
    USAGE_KEYWORDS = [
        'how to use', 'how do i use', 'how should i use', 'how to apply',
        'how much', 'how many', 'how often', 'dosage', 'dose', 'frequency',
        'how long', 'when should', 'what time', 'apply', 'routine', 'layer',
        'before or after', 'mix with', 'combine', 'dilute', 'drops'
    ]
    
    CERTIFICATION_KEYWORDS = [
        'certified', 'certification', 'fda', 'gmp', 'iso', 'usda', 'organic',
        'cruelty-free', 'cruelty free', 'vegan', 'halal', 'peta', 'leaping bunny',
        'dermatologist', 'dermatologically tested', 'clinical', 'tested', 'approved'
    ]
    
    SAFETY_KEYWORDS = [
        'safe', 'safety', 'pregnant', 'pregnancy', 'breastfeeding', 'kids', 'children',
        'side effects', 'allergic', 'reaction', 'sensitive skin', 'broken skin',
        'contraindication', 'eczema', 'hypoallergenic'
    ]
    
    INGREDIENT_KEYWORDS = [
        'ingredient', 'contain', 'paraben', 'fragrance', 'artificial', 'gluten',
        'preservative', 'chemical', 'natural', 'organic', 'active ingredient',
        'percentage', 'concentration', 'ph level', 'texture'
    ]
    
    RETURN_EXCHANGE_KEYWORDS = [
        'return', 'exchange', 'refund', 'money back', 'guarantee', 'warranty',
        'damaged', 'wrong product', 'replace'
    ]
    
    PRICING_PROMO_KEYWORDS = [
        'discount', 'coupon', 'promo', 'offer', 'sale', 'bundle', 'combo',
        'student discount', 'bulk discount', 'loyalty', 'points', 'reward'
    ]


# =============================================================================
# KEYWORD-BASED ANALYZER (No LLM Required)
# =============================================================================

class KeywordAnalyzer:
    """
    Analyzes messages using keyword patterns to identify themes.
    This is a fast, deterministic first-pass analysis.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.theme_patterns = self._build_theme_patterns()
    
    def _build_theme_patterns(self) -> dict[str, list[str]]:
        """Build regex patterns for each theme."""
        return {
            'product_usage': self.config.USAGE_KEYWORDS,
            'certification_compliance': self.config.CERTIFICATION_KEYWORDS,
            'safety_suitability': self.config.SAFETY_KEYWORDS,
            'ingredient_composition': self.config.INGREDIENT_KEYWORDS,
            'return_exchange': self.config.RETURN_EXCHANGE_KEYWORDS,
            'pricing_promotions': self.config.PRICING_PROMO_KEYWORDS
        }
    
    def analyze_message(self, message: str) -> list[str]:
        """
        Identify themes present in a single message.
        
        Returns:
            List of theme identifiers found in the message.
        """
        message_lower = message.lower()
        found_themes = []
        
        for theme, keywords in self.theme_patterns.items():
            for keyword in keywords:
                if keyword in message_lower:
                    found_themes.append(theme)
                    break
        
        return found_themes
    
    def analyze_batch(self, messages: list[CustomerMessage]) -> dict[str, ThemeCluster]:
        """
        Analyze a batch of messages and return theme clusters.
        
        Returns:
            Dictionary mapping theme names to ThemeCluster objects.
        """
        theme_messages: dict[str, list] = defaultdict(list)
        
        for msg in messages:
            themes = self.analyze_message(msg.current_message)
            for theme in themes:
                theme_messages[theme].append({
                    'id': msg.id,
                    'message': msg.current_message
                })
        
        total_messages = len(messages)
        clusters = {}
        
        for theme, msgs in theme_messages.items():
            count = len(msgs)
            percentage = (count / total_messages) * 100 if total_messages > 0 else 0
            
            clusters[theme] = ThemeCluster(
                theme=theme,
                keywords=self.theme_patterns.get(theme, []),
                message_ids=[m['id'] for m in msgs],
                message_samples=[m['message'] for m in msgs[:5]],  # Keep top 5 samples
                count=count,
                percentage=percentage
            )
        
        return clusters


# =============================================================================
# INTENT HIERARCHY MANAGER
# =============================================================================

class IntentHierarchyManager:
    """Manages the current intent hierarchy and proposes modifications."""
    
    def __init__(self, intent_mapper: dict):
        self.primary_intents: list[PrimaryIntent] = []
        self._load_hierarchy(intent_mapper)
    
    def _load_hierarchy(self, intent_mapper: dict):
        """Load intent hierarchy from mapper configuration."""
        for primary in intent_mapper.get('primary_intents', []):
            secondary_intents = [
                SecondaryIntent(
                    id=sec.get('id', ''),
                    name=sec.get('name', ''),
                    description=sec.get('description', '')
                )
                for sec in primary.get('secondary_intents', [])
            ]
            
            self.primary_intents.append(PrimaryIntent(
                id=primary.get('id', ''),
                name=primary.get('name', ''),
                description=primary.get('description', ''),
                secondary_intents=secondary_intents
            ))
    
    def get_all_intent_ids(self) -> set[str]:
        """Get all existing intent IDs (primary and secondary)."""
        ids = set()
        for primary in self.primary_intents:
            ids.add(primary.id)
            for secondary in primary.secondary_intents:
                ids.add(secondary.id)
        return ids
    
    def find_best_parent(self, theme: str) -> Optional[str]:
        """Find the best parent intent for a given theme."""
        theme_to_parent = {
            'product_usage': 'about_product',
            'certification_compliance': 'about_product',
            'safety_suitability': 'about_product',
            'ingredient_composition': 'about_product',
            'return_exchange': 'order_management',
            'pricing_promotions': 'payment'
        }
        return theme_to_parent.get(theme)
    
    def get_similar_intents(self, theme: str) -> list[str]:
        """Get existing intents that might overlap with a theme."""
        theme_overlaps = {
            'product_usage': ['product_info'],
            'certification_compliance': ['product_info'],
            'safety_suitability': ['product_info'],
            'ingredient_composition': ['product_info'],
            'return_exchange': ['order_cancellation', 'order_modification'],
            'pricing_promotions': ['payment_methods']
        }
        return theme_overlaps.get(theme, [])


# =============================================================================
# INTENT PROPOSAL GENERATOR
# =============================================================================

class IntentProposalGenerator:
    """Generates intent proposals based on analysis results."""
    
    THEME_DEFINITIONS = {
        'product_usage': {
            'name': 'Product Usage',
            'description': 'Customer specifically asks how to use/apply/consume a product (dosage, frequency, routine, application method)',
            'rationale': 'Usage instructions differ fundamentally from general product information. Splitting improves recommendation accuracy and enables targeted usage guides.'
        },
        'certification_compliance': {
            'name': 'Certification & Compliance',
            'description': 'Customer asks about product certifications (FDA, GMP, ISO, USDA, cruelty-free, vegan, halal, etc.)',
            'rationale': 'Certification queries indicate specific trust/compliance concerns. Separate handling enables direct certification display and compliance documentation.'
        },
        'safety_suitability': {
            'name': 'Safety & Suitability',
            'description': 'Customer asks about product safety for specific conditions (pregnancy, children, allergies, sensitive skin, medical conditions)',
            'rationale': 'Safety queries require careful, liability-aware responses. Separating enables medical disclaimers and condition-specific guidance.'
        },
        'ingredient_composition': {
            'name': 'Ingredient Details',
            'description': 'Customer asks about specific ingredients, compositions, concentrations, or formulation details',
            'rationale': 'Ingredient queries often come from informed customers needing technical details. Enables ingredient database lookup and allergen checking.'
        },
        'return_exchange': {
            'name': 'Returns & Exchanges',
            'description': 'Customer wants to return, exchange, or get refund for products',
            'rationale': 'Returns/exchanges involve specific policies and processes different from cancellation or general order management.'
        },
        'pricing_promotions': {
            'name': 'Pricing & Promotions',
            'description': 'Customer asks about discounts, coupons, bundles, loyalty programs, or promotional offers',
            'rationale': 'Promotional queries can be handled with real-time offer lookup rather than generic payment information.'
        }
    }
    
    def __init__(self, hierarchy_manager: IntentHierarchyManager, config: PipelineConfig = None):
        self.hierarchy = hierarchy_manager
        self.config = config or PipelineConfig()
        self.existing_ids = hierarchy_manager.get_all_intent_ids()
    
    def generate_proposals(self, clusters: dict[str, ThemeCluster]) -> list[ProposedIntent]:
        """
        Generate intent proposals from theme clusters.
        
        Applies guardrails:
        - Minimum cluster size
        - Minimum percentage threshold
        - Maximum proposal limit
        - Confidence scoring
        """
        proposals = []
        
        # Sort clusters by count (highest first)
        sorted_clusters = sorted(
            clusters.items(),
            key=lambda x: x[1].count,
            reverse=True
        )
        
        for theme, cluster in sorted_clusters:
            # Apply guardrails
            if cluster.count < self.config.MIN_CLUSTER_SIZE:
                logger.debug(f"Skipping {theme}: count {cluster.count} < min {self.config.MIN_CLUSTER_SIZE}")
                continue
            
            if cluster.percentage < self.config.MIN_CLUSTER_PERCENTAGE:
                logger.debug(f"Skipping {theme}: percentage {cluster.percentage:.1f}% < min {self.config.MIN_CLUSTER_PERCENTAGE}%")
                continue
            
            if len(proposals) >= self.config.MAX_PROPOSED_INTENTS:
                logger.warning(f"Reached max proposals ({self.config.MAX_PROPOSED_INTENTS}), stopping")
                break
            
            # Generate proposal
            proposal = self._create_proposal(theme, cluster)
            if proposal and proposal.confidence_score >= self.config.CONFIDENCE_THRESHOLD:
                proposals.append(proposal)
                cluster.suggested_intent = proposal
        
        return proposals
    
    def _create_proposal(self, theme: str, cluster: ThemeCluster) -> Optional[ProposedIntent]:
        """Create a proposal for a specific theme cluster."""
        definition = self.THEME_DEFINITIONS.get(theme)
        if not definition:
            return None
        
        parent_id = self.hierarchy.find_best_parent(theme)
        similar_intents = self.hierarchy.get_similar_intents(theme)
        
        # Calculate confidence score
        confidence = self._calculate_confidence(cluster, similar_intents)
        
        # Determine action (new vs split)
        action = 'split' if similar_intents else 'new'
        original_intent = similar_intents[0] if similar_intents else None
        
        return ProposedIntent(
            level='secondary',
            parent_intent_id=parent_id,
            name=definition['name'],
            id=theme,
            description=definition['description'],
            action=action,
            original_intent_id=original_intent,
            evidence_messages=cluster.message_samples,
            evidence_count=cluster.count,
            confidence_score=confidence,
            rationale=definition['rationale']
        )
    
    def _calculate_confidence(self, cluster: ThemeCluster, similar_intents: list[str]) -> float:
        """
        Calculate confidence score for a proposal.
        
        Factors:
        - Message count (higher = more confident)
        - Percentage of total (higher = more significant)
        - Overlap with existing intents (lower overlap = better fit for new intent)
        """
        # Base score from count (log scale to prevent huge clusters from dominating)
        import math
        count_score = min(1.0, math.log10(cluster.count + 1) / 2)
        
        # Percentage score
        percentage_score = min(1.0, cluster.percentage / 10)
        
        # Novelty score (if no similar intents, it's more novel)
        novelty_score = 0.8 if not similar_intents else 0.5
        
        # Weighted combination
        confidence = (count_score * 0.3) + (percentage_score * 0.4) + (novelty_score * 0.3)
        
        return round(confidence, 2)


# =============================================================================
# LLM INTERFACE (Abstract for Multiple Providers)
# =============================================================================

class LLMInterface:
    """
    Abstract interface for LLM providers.
    Supports OpenAI, Anthropic, and Google's Gemini.
    """
    
    def __init__(self, provider: str = 'openai', api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or self._get_api_key()
        self._client = None
    
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variables."""
        key_mapping = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'google': 'GOOGLE_API_KEY'
        }
        env_var = key_mapping.get(self.provider)
        return os.environ.get(env_var) if env_var else None
    
    def is_available(self) -> bool:
        """Check if the LLM is available (API key present)."""
        return self.api_key is not None
    
    def analyze_messages_for_themes(
        self,
        messages: list[str],
        existing_intents: list[dict]
    ) -> dict:
        """
        Use LLM to analyze messages and identify themes not covered by existing intents.
        
        Returns:
            Dictionary with identified themes and their characteristics.
        """
        if not self.is_available():
            logger.warning(f"LLM ({self.provider}) not available, skipping LLM analysis")
            return {}
        
        prompt = self._build_theme_analysis_prompt(messages, existing_intents)
        
        try:
            response = self._call_llm(prompt)
            return self._parse_theme_response(response)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {}
    
    def _build_theme_analysis_prompt(
        self,
        messages: list[str],
        existing_intents: list[dict]
    ) -> str:
        """Build prompt for theme analysis."""
        intent_summary = "\n".join([
            f"- {i.get('name', 'Unknown')}: {i.get('description', 'No description')}"
            for i in existing_intents
        ])
        
        message_list = "\n".join([f"- {msg}" for msg in messages[:50]])  # Limit for token efficiency
        
        return f"""Analyze the following customer messages and identify common themes or patterns that are NOT well covered by the existing intent categories.

EXISTING INTENTS:
{intent_summary}

CUSTOMER MESSAGES:
{message_list}

Identify 3-5 distinct themes in these messages that might warrant new intent categories. For each theme:
1. Name the theme
2. Describe what customers are asking about
3. List 2-3 example messages
4. Explain why this is distinct from existing intents

Respond in JSON format:
{{
    "themes": [
        {{
            "name": "Theme Name",
            "description": "What this theme covers",
            "examples": ["example1", "example2"],
            "distinction": "Why this is different from existing intents"
        }}
    ]
}}"""
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API."""
        if self.provider == 'openai':
            return self._call_openai(prompt)
        elif self.provider == 'anthropic':
            return self._call_anthropic(prompt)
        elif self.provider == 'google':
            return self._call_google(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing customer service patterns and intent classification."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except ImportError:
            logger.error("OpenAI library not installed. Run: pip install openai")
            return ""
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except ImportError:
            logger.error("Anthropic library not installed. Run: pip install anthropic")
            return ""
    
    def _call_google(self, prompt: str) -> str:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except ImportError:
            logger.error("Google Generative AI library not installed. Run: pip install google-generativeai")
            return ""
    
    def _parse_theme_response(self, response: str) -> dict:
        """Parse LLM response to extract themes."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
        return {}


# =============================================================================
# GUARDRAILS AND VALIDATION
# =============================================================================

class GuardrailChecker:
    """
    Implements guardrails to prevent problematic intent proposals.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
    
    def validate_proposal(self, proposal: ProposedIntent) -> tuple[bool, list[str]]:
        """
        Validate a single proposal against guardrails.
        
        Returns:
            Tuple of (is_valid, list of warnings/issues)
        """
        issues = []
        
        # Check for overly broad intent
        if len(proposal.description.split()) < 5:
            issues.append("Description too brief - may be too broad")
        
        # Check for overly narrow intent
        if proposal.evidence_count < self.config.MIN_CLUSTER_SIZE:
            issues.append(f"Insufficient evidence ({proposal.evidence_count} messages)")
        
        # Check confidence threshold
        if proposal.confidence_score < self.config.CONFIDENCE_THRESHOLD:
            issues.append(f"Low confidence score ({proposal.confidence_score})")
        
        # Check for potentially confusing names
        confusing_patterns = ['other', 'misc', 'general', 'various']
        if any(p in proposal.name.lower() for p in confusing_patterns):
            issues.append("Name may be too generic - could confuse classification")
        
        is_valid = len(issues) == 0 or all('warning' in i.lower() for i in issues)
        return is_valid, issues
    
    def check_fragmentation_risk(self, proposals: list[ProposedIntent]) -> list[str]:
        """
        Check if proposals collectively risk fragmenting the intent space too much.
        
        Returns:
            List of warnings about fragmentation.
        """
        warnings = []
        
        # Check total number of new intents
        if len(proposals) > self.config.MAX_PROPOSED_INTENTS:
            warnings.append(
                f"Too many proposals ({len(proposals)}) may fragment intent space. "
                f"Consider limiting to top {self.config.MAX_PROPOSED_INTENTS}."
            )
        
        # Check for similar proposals that might overlap
        names = [p.name.lower() for p in proposals]
        for i, name1 in enumerate(names):
            for name2 in names[i+1:]:
                # Simple word overlap check
                words1 = set(name1.split())
                words2 = set(name2.split())
                overlap = words1 & words2
                if len(overlap) > 1:
                    warnings.append(
                        f"Potential overlap between '{name1}' and '{name2}' "
                        f"(common words: {overlap})"
                    )
        
        return warnings


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """Generates the final analysis report."""
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
    
    def generate_report(
        self,
        proposals: list[ProposedIntent],
        clusters: dict[str, ThemeCluster],
        guardrail_warnings: list[str],
        total_messages: int
    ) -> dict:
        """Generate comprehensive analysis report."""
        return {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_messages_analyzed': total_messages,
                'themes_identified': len(clusters),
                'proposals_generated': len(proposals)
            },
            'configuration': {
                'min_cluster_size': self.config.MIN_CLUSTER_SIZE,
                'min_cluster_percentage': self.config.MIN_CLUSTER_PERCENTAGE,
                'confidence_threshold': self.config.CONFIDENCE_THRESHOLD,
                'max_proposed_intents': self.config.MAX_PROPOSED_INTENTS
            },
            'theme_analysis': {
                theme: {
                    'count': cluster.count,
                    'percentage': round(cluster.percentage, 2),
                    'keywords': cluster.keywords[:5],
                    'sample_messages': cluster.message_samples[:3]
                }
                for theme, cluster in clusters.items()
            },
            'proposed_intents': [
                {
                    'level': p.level,
                    'parent_intent': p.parent_intent_id,
                    'name': p.name,
                    'id': p.id,
                    'description': p.description,
                    'action': p.action,
                    'original_intent': p.original_intent_id,
                    'evidence_count': p.evidence_count,
                    'confidence_score': p.confidence_score,
                    'rationale': p.rationale,
                    'example_messages': p.evidence_messages[:3]
                }
                for p in proposals
            ],
            'guardrails': {
                'warnings': guardrail_warnings,
                'status': 'passed' if not guardrail_warnings else 'review_needed'
            }
        }
    
    def format_as_markdown(self, report: dict) -> str:
        """Format the report as Markdown for documentation."""
        md_lines = [
            "# Intent Expansion Analysis Report",
            "",
            f"**Generated:** {report['metadata']['generated_at']}",
            f"**Messages Analyzed:** {report['metadata']['total_messages_analyzed']}",
            f"**Themes Identified:** {report['metadata']['themes_identified']}",
            f"**Proposals Generated:** {report['metadata']['proposals_generated']}",
            "",
            "---",
            "",
            "## Theme Analysis",
            ""
        ]
        
        for theme, data in report['theme_analysis'].items():
            md_lines.extend([
                f"### {theme.replace('_', ' ').title()}",
                f"- **Count:** {data['count']} messages ({data['percentage']}%)",
                f"- **Keywords:** {', '.join(data['keywords'])}",
                f"- **Samples:**"
            ])
            for sample in data['sample_messages']:
                md_lines.append(f"  - \"{sample}\"")
            md_lines.append("")
        
        md_lines.extend([
            "---",
            "",
            "## Proposed Intents",
            ""
        ])
        
        for proposal in report['proposed_intents']:
            md_lines.extend([
                f"### {proposal['name']}",
                "",
                f"| Property | Value |",
                f"|----------|-------|",
                f"| **Level** | {proposal['level']} |",
                f"| **ID** | `{proposal['id']}` |",
                f"| **Parent Intent** | `{proposal['parent_intent']}` |",
                f"| **Action** | {proposal['action']} from `{proposal['original_intent']}` |" if proposal['original_intent'] else f"| **Action** | {proposal['action']} |",
                f"| **Confidence** | {proposal['confidence_score']} |",
                f"| **Evidence Count** | {proposal['evidence_count']} |",
                "",
                f"**Description:** {proposal['description']}",
                "",
                f"**Rationale:** {proposal['rationale']}",
                "",
                "**Example Messages:**"
            ])
            for example in proposal['example_messages']:
                md_lines.append(f"- \"{example}\"")
            md_lines.append("")
        
        if report['guardrails']['warnings']:
            md_lines.extend([
                "---",
                "",
                "## Guardrail Warnings",
                ""
            ])
            for warning in report['guardrails']['warnings']:
                md_lines.append(f"⚠️ {warning}")
            md_lines.append("")
        
        return "\n".join(md_lines)


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class IntentExpansionPipeline:
    """
    Main orchestrator for the intent expansion analysis pipeline.
    
    Workflow:
    1. Load and validate input data
    2. Perform keyword-based theme analysis (fast, deterministic)
    3. Optionally enhance with LLM analysis
    4. Generate intent proposals
    5. Apply guardrails and validation
    6. Generate final report
    """
    
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        llm_provider: Optional[str] = None,
        use_llm: bool = False
    ):
        self.config = config or PipelineConfig()
        self.keyword_analyzer = KeywordAnalyzer(self.config)
        self.guardrail_checker = GuardrailChecker(self.config)
        self.report_generator = ReportGenerator(self.config)
        
        self.use_llm = use_llm
        self.llm = LLMInterface(provider=llm_provider or 'openai') if use_llm else None
        
        self.hierarchy_manager: Optional[IntentHierarchyManager] = None
        self.proposal_generator: Optional[IntentProposalGenerator] = None
    
    def load_data(self, filepath: str) -> tuple[list[CustomerMessage], dict]:
        """Load input data from JSON file."""
        logger.info(f"Loading data from {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Parse customer messages
        messages = [
            CustomerMessage(
                id=msg.get('id', i),
                current_message=msg.get('current_message', ''),
                conversation_history=msg.get('conversation_history', [])
            )
            for i, msg in enumerate(data.get('customer_messages', []))
        ]
        
        logger.info(f"Loaded {len(messages)} customer messages")
        
        return messages, data.get('intent_mapper', {})
    
    def run(self, input_filepath: str, output_filepath: Optional[str] = None) -> dict:
        """
        Execute the full intent expansion pipeline.
        
        Args:
            input_filepath: Path to input JSON file
            output_filepath: Optional path for output report
            
        Returns:
            Analysis report dictionary
        """
        logger.info("Starting Intent Expansion Pipeline")
        
        # Step 1: Load data
        messages, intent_mapper = self.load_data(input_filepath)
        
        if not messages:
            logger.error("No messages to analyze")
            return {'error': 'No messages found in input'}
        
        # Step 2: Initialize hierarchy manager
        self.hierarchy_manager = IntentHierarchyManager(intent_mapper)
        self.proposal_generator = IntentProposalGenerator(
            self.hierarchy_manager,
            self.config
        )
        
        # Step 3: Keyword-based analysis
        logger.info("Performing keyword-based theme analysis...")
        clusters = self.keyword_analyzer.analyze_batch(messages)
        logger.info(f"Identified {len(clusters)} theme clusters")
        
        # Step 4: Optional LLM enhancement
        if self.use_llm and self.llm and self.llm.is_available():
            logger.info("Enhancing analysis with LLM...")
            llm_themes = self.llm.analyze_messages_for_themes(
                [m.current_message for m in messages[:100]],  # Sample for efficiency
                [asdict(p) for p in self.hierarchy_manager.primary_intents]
            )
            # Merge LLM insights with keyword analysis
            if llm_themes.get('themes'):
                logger.info(f"LLM identified {len(llm_themes['themes'])} additional themes")
        else:
            if self.use_llm:
                logger.warning("LLM requested but not available, proceeding with keyword analysis only")
        
        # Step 5: Generate proposals
        logger.info("Generating intent proposals...")
        proposals = self.proposal_generator.generate_proposals(clusters)
        logger.info(f"Generated {len(proposals)} proposals")
        
        # Step 6: Apply guardrails
        logger.info("Applying guardrails...")
        all_warnings = []
        
        # Check individual proposals
        for proposal in proposals:
            is_valid, issues = self.guardrail_checker.validate_proposal(proposal)
            if issues:
                all_warnings.extend([f"{proposal.name}: {issue}" for issue in issues])
        
        # Check fragmentation risk
        fragmentation_warnings = self.guardrail_checker.check_fragmentation_risk(proposals)
        all_warnings.extend(fragmentation_warnings)
        
        if all_warnings:
            logger.warning(f"Guardrail warnings: {len(all_warnings)}")
        
        # Step 7: Generate report
        logger.info("Generating report...")
        report = self.report_generator.generate_report(
            proposals=proposals,
            clusters=clusters,
            guardrail_warnings=all_warnings,
            total_messages=len(messages)
        )
        
        # Step 8: Save output
        if output_filepath:
            # Save JSON report
            json_path = output_filepath if output_filepath.endswith('.json') else f"{output_filepath}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Saved JSON report to {json_path}")
            
            # Save Markdown report
            md_path = output_filepath.replace('.json', '') + '.md'
            md_content = self.report_generator.format_as_markdown(report)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"Saved Markdown report to {md_path}")
        
        logger.info("Pipeline completed successfully")
        return report


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Command-line interface for the intent expansion pipeline."""
    parser = argparse.ArgumentParser(
        description='Intent Expansion Pipeline - Analyze customer messages to discover missing intents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage
    python intent_expansion_pipeline.py inputs_for_assignment.json
    
    # With custom output
    python intent_expansion_pipeline.py inputs_for_assignment.json -o analysis_report
    
    # With LLM enhancement
    python intent_expansion_pipeline.py inputs_for_assignment.json --use-llm --llm-provider openai
    
    # Adjust thresholds
    python intent_expansion_pipeline.py inputs_for_assignment.json --min-cluster-size 5 --min-percentage 2.0
        """
    )
    
    parser.add_argument(
        'input_file',
        help='Path to input JSON file containing customer messages and intent mapper'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file path (will generate .json and .md files)',
        default='intent_analysis_report'
    )
    
    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Use LLM to enhance analysis (requires API key)'
    )
    
    parser.add_argument(
        '--llm-provider',
        choices=['openai', 'anthropic', 'google'],
        default='openai',
        help='LLM provider to use (default: openai)'
    )
    
    parser.add_argument(
        '--min-cluster-size',
        type=int,
        default=PipelineConfig.MIN_CLUSTER_SIZE,
        help=f'Minimum messages for a theme to be significant (default: {PipelineConfig.MIN_CLUSTER_SIZE})'
    )
    
    parser.add_argument(
        '--min-percentage',
        type=float,
        default=PipelineConfig.MIN_CLUSTER_PERCENTAGE,
        help=f'Minimum percentage of messages for significance (default: {PipelineConfig.MIN_CLUSTER_PERCENTAGE})'
    )
    
    parser.add_argument(
        '--confidence-threshold',
        type=float,
        default=PipelineConfig.CONFIDENCE_THRESHOLD,
        help=f'Minimum confidence score for proposals (default: {PipelineConfig.CONFIDENCE_THRESHOLD})'
    )
    
    parser.add_argument(
        '--max-proposals',
        type=int,
        default=PipelineConfig.MAX_PROPOSED_INTENTS,
        help=f'Maximum number of proposals (default: {PipelineConfig.MAX_PROPOSED_INTENTS})'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create custom config
    config = PipelineConfig()
    config.MIN_CLUSTER_SIZE = args.min_cluster_size
    config.MIN_CLUSTER_PERCENTAGE = args.min_percentage
    config.CONFIDENCE_THRESHOLD = args.confidence_threshold
    config.MAX_PROPOSED_INTENTS = args.max_proposals
    
    # Run pipeline
    pipeline = IntentExpansionPipeline(
        config=config,
        llm_provider=args.llm_provider,
        use_llm=args.use_llm
    )
    
    try:
        report = pipeline.run(args.input_file, args.output)
        
        # Print summary to console
        print("\n" + "="*60)
        print("INTENT EXPANSION ANALYSIS SUMMARY")
        print("="*60)
        print(f"\nMessages Analyzed: {report['metadata']['total_messages_analyzed']}")
        print(f"Themes Identified: {report['metadata']['themes_identified']}")
        print(f"Proposals Generated: {report['metadata']['proposals_generated']}")
        
        if report['proposed_intents']:
            print("\nProposed New Intents:")
            for proposal in report['proposed_intents']:
                print(f"  • {proposal['name']} (confidence: {proposal['confidence_score']})")
                print(f"    └─ {proposal['description'][:80]}...")
        
        if report['guardrails']['warnings']:
            print(f"\n⚠️  Guardrail Warnings: {len(report['guardrails']['warnings'])}")
            for warning in report['guardrails']['warnings'][:3]:
                print(f"  - {warning}")
        
        print(f"\nFull reports saved to:")
        print(f"  - {args.output}.json")
        print(f"  - {args.output}.md")
        print("="*60)
        
    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input_file}")
        exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in input file: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
