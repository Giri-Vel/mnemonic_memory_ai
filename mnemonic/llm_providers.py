"""
LLM Provider abstraction for session management.

Supports pluggable LLM backends (Gemini, Claude, OpenAI, Ollama, etc.)
with unified interface for session operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def check_continuity(
        self,
        previous_context: str,
        new_memory: str,
        timeout: float = 5.0
    ) -> bool:
        """
        Check if new memory continues the previous conversation.
        
        Args:
            previous_context: Summary or recent memories from last session
            new_memory: New memory to check
            timeout: Maximum time to wait for response (seconds)
        
        Returns:
            True if memories are contextually continuous, False otherwise
        """
        pass
    
    @abstractmethod
    def generate_summary(
        self,
        memories: List[str],
        topic: Optional[str] = None
    ) -> str:
        """
        Generate a natural language summary of memories.
        
        Args:
            memories: List of memory texts
            topic: Optional topic hint for summary
        
        Returns:
            Natural language summary
        """
        pass
    
    @abstractmethod
    def suggest_topic(self, memories: List[str]) -> str:
        """
        Suggest a topic for a session based on memories.
        
        Args:
            memories: List of memory texts
        
        Returns:
            Suggested topic (short phrase)
        """
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY env var or pass api_key parameter."
            )
        
        # Lazy import to avoid dependency if not using Gemini
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai.configure(api_key=self.api_key)
            
            # Use Gemini 1.5 Flash for fast, cheap operations
            self.model = self.genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')
            logger.info("Gemini provider initialized (model: gemini-2.5-flash-preview-09-2025)")
            
        except ImportError:
            raise ImportError(
                "google-generativeai not installed. "
                "Install with: pip install google-generativeai"
            )
    
    def check_continuity(
        self,
        previous_context: str,
        new_memory: str,
        timeout: float = 5.0
    ) -> bool:
        """
        Check if new memory continues the previous conversation.
        
        Uses a simple YES/NO prompt for fast response.
        Falls back to False (new session) on errors.
        """
        prompt = f"""You are analyzing conversation continuity for a memory system.

PREVIOUS CONVERSATION CONTEXT:
{previous_context}

NEW MEMORY:
{new_memory}

QUESTION: Does this new memory continue the same conversation topic as the previous context?

Consider:
- Are they about the same project, problem, or topic?
- Is there clear topical continuity?
- Would a human naturally group these together?

Answer with ONLY one word: YES or NO

YOUR ANSWER:"""
        
        try:
            # Configure for fast response
            generation_config = {
                "temperature": 0.1,  # Low temperature for consistent yes/no
                "max_output_tokens": 10,  # We only need one word
            }

            # Add safety settings to prevent blocking
            safety_settings = {
                self.genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: self.genai.types.HarmBlockThreshold.BLOCK_NONE,
                self.genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: self.genai.types.HarmBlockThreshold.BLOCK_NONE,
                self.genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: self.genai.types.HarmBlockThreshold.BLOCK_NONE,
                self.genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: self.genai.types.HarmBlockThreshold.BLOCK_NONE,
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings,
                request_options={"timeout": timeout}
            )
            
            # response = self.model.generate_content(
            #     prompt,
            #     generation_config=generation_config,
            #     request_options={"timeout": timeout}
            # )
            
            # Check if response was blocked by safety filters
            if not response.candidates or not response.candidates[0].content.parts:
                logger.warning(f"Response blocked (finish_reason={response.candidates[0].finish_reason if response.candidates else 'unknown'}), defaulting to NO")
                return False
            
            answer = response.text.strip().upper()
            
            # Parse response
            if "YES" in answer:
                logger.debug("Continuity check: YES (extending session)")
                return True
            elif "NO" in answer:
                logger.debug("Continuity check: NO (new session)")
                return False
            else:
                logger.warning(f"Unexpected continuity response: {answer}, defaulting to NO")
                return False
            
        except Exception as e:
            logger.error(f"Continuity check failed: {e}, defaulting to new session")
            return False
    
    def generate_summary(
        self,
        memories: List[str],
        topic: Optional[str] = None
    ) -> str:
        """
        Generate a natural language summary of memories.
        
        Creates a concise summary that captures key points and flow.
        """
        memories_text = "\n".join(f"- {mem}" for mem in memories)
        
        topic_hint = f"Topic: {topic}\n\n" if topic else ""
        
        prompt = f"""You are summarizing a conversation session for a personal memory system.

{topic_hint}MEMORIES IN THIS SESSION:
{memories_text}

Generate a concise 2-3 sentence summary that:
1. Captures the main topic/theme
2. Notes key points or outcomes
3. Uses natural language (as if explaining to a friend)

Keep it under 100 words. Write in past tense.

SUMMARY:"""
        
        try:
            generation_config = {
                "temperature": 0.3,  # Slight creativity for natural language
                "max_output_tokens": 150,
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            summary = response.text.strip()
            logger.debug(f"Generated summary: {summary[:50]}...")
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Fallback: basic concatenation
            return f"Session with {len(memories)} memories" + (f" about {topic}" if topic else "")
    
    def suggest_topic(self, memories: List[str]) -> str:
        """
        Suggest a topic for a session based on memories.
        
        Returns a short phrase (3-5 words) describing the session.
        """
        # Use first few memories for topic detection
        sample = memories[:5]
        memories_text = "\n".join(f"- {mem}" for mem in sample)
        
        prompt = f"""Based on these memories, suggest a short topic title (3-5 words maximum):

{memories_text}

Return ONLY the topic phrase, nothing else.

TOPIC:"""
        
        try:
            generation_config = {
                "temperature": 0.2,
                "max_output_tokens": 20,
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            topic = response.text.strip()
            logger.debug(f"Suggested topic: {topic}")
            return topic
            
        except Exception as e:
            logger.error(f"Topic suggestion failed: {e}")
            return "General conversation"

class ClaudeProvider(LLMProvider):
    """Anthropic Claude LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude provider.
        
        Args:
            api_key: Claude API key (defaults to CLAUDE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "Claude API key required. Set CLAUDE_API_KEY env var or pass api_key parameter."
            )
        
        # Lazy import to avoid dependency if not using Claude
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = "claude-haiku-4-5-20251001"  # Fast and cheap
            logger.info(f"Claude provider initialized (model: {self.model})")
            
        except ImportError:
            raise ImportError(
                "anthropic not installed. "
                "Install with: pip install anthropic"
            )
    
    def check_continuity(
        self,
        previous_context: str,
        new_memory: str,
        timeout: float = 5.0
    ) -> bool:
        """
        Check if new memory continues the previous conversation.
        
        Uses a simple YES/NO prompt for fast response.
        Falls back to False (new session) on errors.
        """
        prompt = f"""You are analyzing conversation continuity for a memory system.

PREVIOUS CONVERSATION CONTEXT:
{previous_context}

NEW MEMORY:
{new_memory}

QUESTION: Does this new memory continue the same conversation topic as the previous context?

Consider:
- Are they about the same project, problem, or topic?
- Is there clear topical continuity?
- Would a human naturally group these together?

Answer with ONLY one word: YES or NO"""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=10,
                temperature=0.1,
                timeout=timeout,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            answer = response.content[0].text.strip().upper()
            
            # Parse response
            if "YES" in answer:
                logger.debug("Continuity check: YES (extending session)")
                return True
            elif "NO" in answer:
                logger.debug("Continuity check: NO (new session)")
                return False
            else:
                logger.warning(f"Unexpected continuity response: {answer}, defaulting to NO")
                return False
            
        except Exception as e:
            logger.error(f"Continuity check failed: {e}, defaulting to new session")
            return False
    
    def generate_summary(
        self,
        memories: List[str],
        topic: Optional[str] = None
    ) -> str:
        """
        Generate a natural language summary of memories.
        
        Creates a concise summary that captures key points and flow.
        """
        memories_text = "\n".join(f"- {mem}" for mem in memories)
        
        topic_hint = f"Topic: {topic}\n\n" if topic else ""
        
        prompt = f"""You are summarizing a conversation session for a personal memory system.

{topic_hint}MEMORIES IN THIS SESSION:
{memories_text}

Generate a concise 2-3 sentence summary that:
1. Captures the main topic/theme
2. Notes key points or outcomes
3. Uses natural language (as if explaining to a friend)

Keep it under 100 words. Write in past tense."""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,
                temperature=0.3,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            summary = response.content[0].text.strip()
            logger.debug(f"Generated summary: {summary[:50]}...")
            return summary
            
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Fallback: basic concatenation
            return f"Session with {len(memories)} memories" + (f" about {topic}" if topic else "")
    
    def suggest_topic(self, memories: List[str]) -> str:
        """
        Suggest a topic for a session based on memories.
        
        Returns a short phrase (3-5 words) describing the session.
        """
        # Use first few memories for topic detection
        sample = memories[:5]
        memories_text = "\n".join(f"- {mem}" for mem in sample)
        
        prompt = f"""Based on these memories, suggest a short topic title (3-5 words maximum):

{memories_text}

Return ONLY the topic phrase, nothing else."""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=20,
                temperature=0.2,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            topic = response.content[0].text.strip()
            logger.debug(f"Suggested topic: {topic}")
            return topic
            
        except Exception as e:
            logger.error(f"Topic suggestion failed: {e}")
            return "General conversation"

class DummyProvider(LLMProvider):
    """
    Dummy LLM provider for testing (no API calls).
    
    Always returns predictable responses.
    """
    
    def __init__(self, always_continue: bool = False):
        """
        Initialize dummy provider.
        
        Args:
            always_continue: If True, always says YES to continuity
        """
        self.always_continue = always_continue
        logger.info(f"Dummy provider initialized (always_continue={always_continue})")
    
    def check_continuity(
        self,
        previous_context: str,
        new_memory: str,
        timeout: float = 5.0
    ) -> bool:
        """Always returns configured continuity response."""
        return self.always_continue
    
    def generate_summary(
        self,
        memories: List[str],
        topic: Optional[str] = None
    ) -> str:
        """Returns simple concatenated summary."""
        topic_part = f"{topic}: " if topic else ""
        return f"{topic_part}Session with {len(memories)} memories"
    
    def suggest_topic(self, memories: List[str]) -> str:
        """Returns generic topic."""
        return "Test conversation"


def get_provider(
    provider_name: str = "gemini",
    api_key: Optional[str] = None,
    **kwargs
) -> LLMProvider:
    """
    Factory function to get LLM provider.
    
    Args:
        provider_name: Name of provider ("gemini", "dummy", etc.)
        api_key: API key for the provider
        **kwargs: Additional provider-specific arguments
    
    Returns:
        Initialized LLM provider
    
    Raises:
        ValueError: If provider not found
    """
    providers = {
        "gemini": GeminiProvider,
        "claude": ClaudeProvider,
        "dummy": DummyProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    
    if not provider_class:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Available: {', '.join(providers.keys())}"
        )
    
    # Pass api_key only to providers that need it
    if provider_name.lower() in ["gemini", "claude"]:
        return provider_class(api_key=api_key)
    else:
        return provider_class(**kwargs)