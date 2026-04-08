import requests
import json
import re
import asyncio
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from config import Config
from utils.web_search_manager import WebSearchManager, SearchResult
from utils.file_manager import EnhancedFileManager


class PipelineState:
    """Manages the state of a pipeline run"""

    def __init__(self, query: str, session_id: Optional[str] = None,
                 timestamp: Optional[str] = None):
        self.query = query
        self.session_id = session_id
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.iteration_count = 0
        self.research_output = ""
        self.analysis_output = ""
        self.template_output = ""
        self.new_instruction = ""
        self.history = []
        self.skill_name = ""
        self.bundle_tree = ""
        self.bundle_root = ""

    def to_dict(self) -> Dict:
        """Convert state to dictionary for storage"""
        return {
            'query': self.query,
            'session_id': self.session_id,
            'timestamp': self.timestamp,
            'iteration_count': self.iteration_count,
            'research_output': self.research_output,
            'analysis_output': self.analysis_output,
            'template_output': self.template_output,
            'new_instruction': self.new_instruction,
            'history': self.history,
            'skill_name': self.skill_name,
            'bundle_tree': self.bundle_tree,
            'bundle_root': self.bundle_root
        }


class AIPipeline:
    """Main AI pipeline for generating skill templates"""

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }
        # Initialize enhanced components
        if Config.WEB_SEARCH_ENABLED:
            self.web_search = WebSearchManager()
        else:
            self.web_search = None
        self.file_manager = EnhancedFileManager()

    def _log(self, logger: Optional[Callable[[str], None]], message: str) -> None:
        if logger:
            logger(message)

    def extract_and_log_thoughts(self, logger: Optional[Callable[[str], None]],
                                 response: str,
                                 stage: str) -> str:
        """
        Extract thought sections from AI response and log them separately.
        Returns the cleaned response without thoughts.

        Keeps reasoning concise by extracting brief bullet points.
        """
        thoughts = []
        clean_response = response

        # Look for "THINKING ALOUD" sections
        if "**THINKING ALOUD**" in response:
            # Extract the thinking section
            thought_match = re.search(
                r'\*\*THINKING ALOUD\*\*(.*?)(?=\n\n|$|Then provide)',
                response,
                re.DOTALL
            )

            if thought_match:
                thought_section = thought_match.group(1).strip()

                # Split into individual lines and log each as a concise thought
                lines = thought_section.split('\n')
                for line in lines:
                    line = line.strip()

                    # Extract bullet points or numbered items
                    bullet_match = re.match(r'^[\-\*\•\d+\.]+\s*\*\*(.+?)\*\*:?\s*(.+)', line)
                    if bullet_match:
                        category = bullet_match.group(1).strip()
                        thought = bullet_match.group(2).strip() if len(bullet_match.groups()) > 1 else ""

                        # Combine into a concise log message
                        if thought:
                            concise_thought = f"{category}: {thought[:150]}"  # Keep it brief
                            if len(thought) > 150:
                                concise_thought += "..."
                            thoughts.append(concise_thought)
                            self._log(logger, f"💭 {concise_thought}")

                # Remove the thinking section from response
                clean_response = re.sub(
                    r'\*\*THINKING ALOUD\*\*.*?(?=\n\n|$|Then provide)',
                    '',
                    response,
                    flags=re.DOTALL
                )

        return clean_response.strip()

    def call_model(self, model: str, messages: List[Dict],
                   max_tokens: int = None, temperature: float = None,
                   logger: Optional[Callable[[str], None]] = None) -> str:
        """Make API call to OpenRouter with fallback models"""

        # List of models to try in order
        models_to_try = [model]

        # Add fallback models if primary is ANALYSIS or TEMPLATE model
        if model == Config.ANALYSIS_MODEL or model == Config.TEMPLATE_MODEL:
            models_to_try.extend(Config.FALLBACK_RESEARCH_MODELS)

        last_error = None

        for model_to_use in models_to_try:
            payload = {
                "model": model_to_use,
                "messages": messages,
                "max_tokens": max_tokens or Config.MAX_TOKENS_RESEARCH,
                "temperature": temperature or Config.DEFAULT_TEMPERATURE
            }

            try:
                self._log(logger, f"🔄 Connecting to {model_to_use}...")
                self._log(logger, f"⏱️ Processing request (max {max_tokens or Config.MAX_TOKENS_RESEARCH} tokens)...")
                response = requests.post(
                    Config.OPENROUTER_API_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=120  # 2 minute timeout
                )

                if response.status_code == 200:
                    self._log(logger, f"✅ {model_to_use} response received successfully!")
                    return response.json()['choices'][0]['message']['content']
                else:
                    error_msg = f"⚠️ API error for {model_to_use}: {response.status_code} - {response.text}"
                    self._log(logger, error_msg)
                    print(error_msg)
                    last_error = Exception(error_msg)
                    continue

            except requests.exceptions.RequestException as e:
                error_msg = f"⚠️ Connection issue with {model_to_use}: {str(e)}"
                self._log(logger, error_msg)
                print(error_msg)
                last_error = Exception(error_msg)
                continue

        # If all models failed, raise the last error
        raise last_error or Exception("All models failed to respond")

    def run_research(self, query: str,
                     logger: Optional[Callable[[str], None]] = None) -> str:
        """Stage 1: Enhanced Domain Research with Web Search"""

        self._log(logger, "🔍 Beginning comprehensive research on your query...")
        self._log(logger, f"📝 Analyzing query: \"{query}\"")

        # Gather web search results if enabled
        web_context = ""
        search_sources = []
        if self.web_search:
            try:
                self._log(logger, "🌐 Searching the web for latest insights and trends...")
                # Run web search
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._log(logger, "📡 Querying search APIs for relevant information...")
                search_results = loop.run_until_complete(
                    self.web_search.search(query, max_results=5)
                )
                loop.close()

                if search_results:
                    self._log(logger, f"✅ Found {len(search_results)} relevant resources!")
                    # Format search results for prompt
                    web_context = "\n\n## Recent Web Search Results:\n"
                    for i, result in enumerate(search_results[:3], 1):
                        self._log(logger, f"📄 Processing source {i}: {result.title}")
                        web_context += f"\n{i}. **{result.title}**\n"
                        if result.snippet:
                            web_context += f"   {result.snippet}\n"
                        if result.url:
                            web_context += f"   Source: {result.url}\n"
                        search_sources.append(f"{result.title} ({result.source})")

            except Exception as e:
                self._log(logger, f"⚠️ Web search encountered issues: {str(e)}")
                self._log(logger, "📚 Continuing with knowledge base research...")
                print(f"Web search failed: {str(e)}")
                # Continue without web search if it fails

        # Gather relevant examples from file system
        example_context = ""
        try:
            self._log(logger, "🗂️ Searching knowledge base for relevant examples...")
            # Try to find examples based on query keywords
            domain_keywords = query.split()[:3]  # Use first 3 keywords
            self._log(logger, f"🔑 Looking for examples related to: {', '.join(domain_keywords)}")
            for keyword in domain_keywords:
                examples = self.file_manager.get_examples_by_domain(keyword)
                if examples:
                    self._log(logger, f"💡 Found {len(examples)} examples for '{keyword}' domain")
                    example_context += f"\n\n## Relevant Examples for {keyword}:\n"
                    for example in examples[:2]:
                        example_context += f"- {example['title']}\n"
                        example_context += f"  {example['content'][:200]}...\n"
                    break  # Use first keyword that finds examples
        except Exception as e:
            self._log(logger, f"⚠️ Issue loading examples: {str(e)}")
            print(f"Failed to load examples: {str(e)}")

            # Build enhanced prompt
        self._log(logger, "🧠 Preparing comprehensive research prompt...")
        self._log(logger, "📋 Structuring research requirements...")

        # Add reasoning instruction - keep it concise
        reasoning_instruction = """
**THINKING ALOUD (brief, 2-3 sentences each):**
- Query Focus: What aspects will I prioritize?
- Search Strategy: What am I looking for specifically?
- Key Patterns: What connections am I noticing?
- Research Direction: What gaps should I address?

Then provide your detailed research.
"""

        prompt = (
            f"Conduct comprehensive domain research on: {query}\n"
            f"{web_context}"
            f"{example_context}\n\n"
            f"{reasoning_instruction}\n\n"
            "Provide a detailed summary covering:\n"
            "1. Key concepts and terminology\n"
            "2. Important methodologies and frameworks\n"
            "3. Essential tools and technologies\n"
            "4. Real-world applications and use cases\n"
            "5. Current trends and future directions\n"
            "6. Critical challenges and limitations\n"
            "7. Reference sources and further reading\n\n"
            "Format with clear headings and bullet points."
            "If web search results were provided, incorporate and cite that information."
        )

        messages = [{"role": "user", "content": prompt}]
        self._log(logger, f"🤖 Engaging {Config.RESEARCH_MODEL} for deep research analysis...")
        raw_response = self.call_model(
            Config.RESEARCH_MODEL,
            messages,
            max_tokens=Config.MAX_TOKENS_RESEARCH,
            logger=logger
        )
        # Extract and log thoughts separately, return cleaned response
        return self.extract_and_log_thoughts(logger, raw_response, "research")

    def run_analysis(self, research_output: str, previous_analysis: str = "",
                     logger: Optional[Callable[[str], None]] = None) -> Tuple[str, str]:
        """Stage 2: Deep Analysis"""

        self._log(logger, "🔬 Beginning deep analysis of research findings...")
        self._log(logger, "📊 Identifying patterns and extracting key insights...")
        context = f"\nPrevious Analysis: {previous_analysis}" if previous_analysis else ""

        # Add reasoning instruction - keep it concise
        reasoning_instruction = """
**THINKING ALOUD (brief, 2-3 sentences each):**
- Key Findings: What are the main takeaways from research?
- Pattern Recognition: What connections or trends am I seeing?
- Gaps Identified: What's missing or needs more depth?
- Skill Direction: What should the skill focus on based on this?

Then provide your detailed analysis.
"""

        prompt = (
            f"Analyze the following research output:\n\n{research_output}{context}\n\n"
            f"{reasoning_instruction}\n\n"
            "Provide a thorough analysis:\n\n"
            "1. **Issues**: Identify any problems, gaps, or inconsistencies in the research\n"
            "2. **Shortcomings**: Point out limitations, missing information, or weak areas\n"
            "3. **Enhancements**: Suggest specific improvements and additional research directions\n"
            "4. **New Research Instruction**: If needed, provide a specific instruction for further research to address gaps\n\n"
            "Format your response clearly with these four sections."
        )

        messages = [
            {"role": "system", "content": "You are a critical thinking AI analyst specializing in deep, structured analysis."},
            {"role": "user", "content": prompt}
        ]

        raw_analysis = self.call_model(
            Config.ANALYSIS_MODEL,
            messages,
            max_tokens=Config.MAX_TOKENS_ANALYSIS,
            temperature=Config.ANALYSIS_TEMPERATURE,
            logger=logger
        )

        # Extract and log thoughts separately
        analysis = self.extract_and_log_thoughts(logger, raw_analysis, "analysis")

        # Extract new instruction if present
        new_instruction = ""
        if "New Research Instruction:" in analysis:
            match = re.search(r'New Research Instruction:(.*?)(?=\n\n|\Z)', analysis, re.DOTALL)
            if match:
                new_instruction = match.group(1).strip()

        return analysis, new_instruction

    def run_template_generation(self, research_output: str, analysis_output: str,
                                logger: Optional[Callable[[str], None]] = None) -> str:
        """Stage 3: Enhanced Template Generation with File References"""

        self._log(logger, "🛠️ Crafting your AI skill template...")
        self._log(logger, "🔗 Analyzing existing skills for best practices...")
        # Find similar templates for reference
        template_references = ""
        try:
            # Extract keywords from research for finding similar templates
            keywords = re.findall(r'\b\w+\b', research_output)[:10]
            self._log(logger, f"🔍 Searching for similar skills using {len(keywords)} keywords...")
            similar_templates = self.file_manager.find_similar_templates(
                ' '.join(keywords), max_results=3
            )

            if similar_templates:
                self._log(logger, f"💡 Found {len(similar_templates)} reference templates for guidance...")
                template_references = "\n\n## Reference Templates:\n"
                for template in similar_templates:
                    template_references += f"\n**Similar Skill: {template['query']}**\n"
                    try:
                        content = self.file_manager.read_file(template['template_file'])
                        # Extract key patterns from similar template
                        if '```yaml' in content:
                            yaml_section = content.split('```yaml')[1].split('```')[0]
                            template_references += f"  Metadata structure:\n  ```yaml\n{yaml_section[:200]}...\n```\n"
                    except:
                        template_references += "  (Template content unavailable)\n"
            else:
                self._log(logger, "📝 Creating unique skill from scratch...")
        except Exception as e:
            self._log(logger, f"⚠️ Issue accessing reference templates: {str(e)}")
            self._log(logger, "🚀 Proceeding with custom skill creation...")
            print(f"Failed to load similar templates: {str(e)}")

        # Build enhanced prompt with references
        self._log(logger, "📝 Building comprehensive template specification...")
        self._log(logger, "🎨 Designing skill structure and implementation guidelines...")

        # Add reasoning instruction - keep it concise
        reasoning_instruction = """
**THINKING ALOUD (brief, 2-3 sentences each):**
- Skill Type: What category best fits this capability?
- Structure: How should I organize the instructions for clarity?
- Examples: What scenarios best demonstrate this skill?
- Implementation: What technical details are most important?

Then provide the complete skill template.
"""

        prompt = (
            f"Based on the following research and analysis, create an advanced Anthropic-style Agent Skills template:\n\n"
            f"RESEARCH:\n{research_output}\n\n"
            f"ANALYSIS:\n{analysis_output}\n"
            f"{template_references}\n\n"
            f"{reasoning_instruction}\n\n"
            "Create a comprehensive skill template with:\n\n"
            "1. **YAML Front Matter** with metadata:\n"
            "   - name: Skill name (clear and descriptive)\n"
            "   - description: Clear description of what the skill does\n"
            "   - author: AI Skills Pipeline\n"
            "   - version: 1.0.0\n"
            "   - category: Appropriate category (e.g., 'utility', 'analysis', 'creative')\n"
            "   - tags: 3-5 relevant tags\n\n"
            "2. **Skill Description**:\n"
            "   - What the skill does\n"
            "   - When to use it\n"
            "   - Key features\n\n"
            "3. **Instructions**:\n"
            "   - Clear usage guidelines\n"
            "   - Input/output specifications\n"
            "   - Example prompts\n\n"
            "4. **Implementation Notes** (if applicable):\n"
            "   - Technical requirements\n"
            "   - Dependencies\n"
            "   - Configuration\n\n"
            "5. **Examples**:\n"
            "   - Use cases\n"
            "   - Sample interactions\n\n"
            "If reference templates are provided above, use their structure and patterns as inspiration, "
            "but create an original template tailored to the specific research and analysis provided.\n\n"
            "Format as a complete skill.md file with proper markdown formatting."
        )

        messages = [{"role": "user", "content": prompt}]
        self._log(logger, f"✨ Engaging {Config.TEMPLATE_MODEL} to craft your skill...")
        raw_template = self.call_model(
            Config.TEMPLATE_MODEL,
            messages,
            max_tokens=Config.MAX_TOKENS_TEMPLATE,
            logger=logger
        )
        # Extract and log thoughts separately, return cleaned response
        return self.extract_and_log_thoughts(logger, raw_template, "template")

    def run_refinement(self, state: PipelineState, context_prompt: str,
                      logger: Optional[Callable[[str], None]] = None,
                      stage_callback: Optional[Callable[[str], None]] = None) -> PipelineState:
        """Run a refinement iteration based on user chat message"""

        # Stage 1: Determine if additional research is needed
        if stage_callback:
            stage_callback("research")

        self._log(logger, "🔍 Determining if additional research is needed...")

        # Use AI to decide if new research is needed
        research_decision_prompt = f"""
Based on the user's refinement request, do we need additional research?

User Request: {context_prompt}

Respond with either:
- "NEW_RESEARCH: [specific research topic]"
- "SUFFICIENT: [explanation why existing research is enough]"

Keep your response brief and focused.
"""

        research_decision = self.call_model(
            Config.TEMPLATE_MODEL,
            [{"role": "user", "content": research_decision_prompt}],
            max_tokens=200,
            logger=logger
        )

        if "NEW_RESEARCH:" in research_decision:
            topic = research_decision.split("NEW_RESEARCH:")[1].strip()
            self._log(logger, f"🌐 Additional research needed: {topic[:60]}...")
            # Run additional research
            new_research = self.run_research(topic, logger=logger)
            state.research_output += f"\n\n## Additional Research:\n{new_research}"

        # Stage 2: Analysis
        if stage_callback:
            stage_callback("analysis")

        self._log(logger, "🔬 Analyzing refinement requirements...")

        analysis_prompt = f"""
Analyze what changes are needed for this refinement request:

{context_prompt}

Provide:
1. Specific changes required (brief bullet points)
2. How to modify the template structure
3. What sections need updates
4. New examples or content needed

Keep your analysis concise and actionable.
"""

        analysis = self.call_model(
            Config.TEMPLATE_MODEL,
            [{"role": "user", "content": analysis_prompt}],
            max_tokens=1000,
            logger=logger
        )

        state.analysis_output += f"\n\n## Refinement Analysis:\n{analysis}"

        # Stage 3: Template Update
        if stage_callback:
            stage_callback("template")

        self._log(logger, "🛠️ Regenerating skill with requested changes...")

        template_prompt = f"""
Update the following skill template based on the refinement request:

Current Template:
{state.template_output}

Refinement Request:
{context_prompt}

Analysis of Changes:
{analysis}

Provide the complete updated template. Think through your design decisions briefly.
"""

        new_template = self.call_model(
            Config.TEMPLATE_MODEL,
            [{"role": "user", "content": template_prompt}],
            max_tokens=Config.MAX_TOKENS_TEMPLATE,
            logger=logger
        )

        state.template_output = new_template
        state.iteration_count += 1

        return state

    def run_pipeline(self, query: str, logger: Optional[Callable[[str], None]] = None,
                     session_id: Optional[str] = None,
                     timestamp: Optional[str] = None,
                     stage_callback: Optional[Callable[[str], None]] = None) -> PipelineState:
        """Run the complete pipeline"""

        state = PipelineState(query, session_id=session_id, timestamp=timestamp)

        # Stage 1: Research
        if stage_callback:
            stage_callback("research")
        state.research_output = self.run_research(query, logger=logger)

        # Stage 2: Analysis
        if stage_callback:
            stage_callback("analysis")
        state.analysis_output, state.new_instruction = self.run_analysis(
            state.research_output,
            logger=logger
        )

        # Stage 3: Template Generation
        if stage_callback:
            stage_callback("template")
        state.template_output = self.run_template_generation(
            state.research_output,
            state.analysis_output,
            logger=logger
        )

        state.iteration_count = 1

        # Save initial state to history
        state.history.append({
            'iteration': 1,
            'research': state.research_output,
            'analysis': state.analysis_output,
            'template': state.template_output,
            'instruction': state.new_instruction
        })

        return state

    def run_iteration(self, state: PipelineState,
                      logger: Optional[Callable[[str], None]] = None,
                      stage_callback: Optional[Callable[[str], None]] = None) -> PipelineState:
        """Run an iteration of the pipeline"""

        if state.iteration_count >= Config.MAX_ITERATIONS:
            raise Exception(f"Maximum iterations ({Config.MAX_ITERATIONS}) reached")

        if not state.new_instruction:
            raise Exception("No new instruction available for iteration")

        # Use the new instruction as query
        new_query = state.new_instruction

        # Run research with new instruction
        if stage_callback:
            stage_callback("research")
        new_research = self.run_research(new_query, logger=logger)

        # Run analysis with previous analysis as context
        if stage_callback:
            stage_callback("analysis")
        new_analysis, new_instruction = self.run_analysis(
            new_research,
            state.analysis_output,
            logger=logger
        )

        # Generate new template
        if stage_callback:
            stage_callback("template")
        new_template = self.run_template_generation(
            new_research,
            new_analysis,
            logger=logger
        )

        # Update state
        state.iteration_count += 1
        state.research_output = new_research
        state.analysis_output = new_analysis
        state.template_output = new_template
        state.new_instruction = new_instruction

        # Save to history
        state.history.append({
            'iteration': state.iteration_count,
            'research': new_research,
            'analysis': new_analysis,
            'template': new_template,
            'instruction': new_instruction
        })

        return state
