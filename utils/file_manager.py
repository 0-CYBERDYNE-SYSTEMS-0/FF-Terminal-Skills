import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Union, TYPE_CHECKING, Any
from pathlib import Path

from config import Config
from utils.skill_bundle import normalize_skill_content, detect_referenced_files, ensure_bundle_structure, build_tree

# Use TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from pipeline import PipelineState


class EnhancedFileManager:
    """Enhanced file manager with secure, sandboxed access"""

    def __init__(self):
        # Convert relative paths to absolute paths
        self.allowed_read_paths = [
            os.path.abspath(path) for path in Config.ALLOWED_READ_PATHS
        ]
        self.allowed_write_paths = [
            os.path.abspath(path) for path in Config.ALLOWED_WRITE_PATHS
        ]
        self.max_file_size = Config.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
        self.access_log = []

    def _validate_path(self, path: str, operation: str = 'read') -> str:
        """Validate that path is within allowed directories"""
        abs_path = os.path.abspath(path)

        if operation == 'read':
            for allowed in self.allowed_read_paths:
                if abs_path.startswith(allowed):
                    return abs_path
        elif operation == 'write':
            for allowed in self.allowed_write_paths:
                if abs_path.startswith(allowed):
                    return abs_path

        raise ValueError(f"Path {path} not allowed for {operation} operation")

    def _log_access(self, operation: str, path: str, success: bool = True):
        """Log file access for security auditing"""
        self.access_log.append({
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'path': path,
            'success': success
        })

        # Keep log size manageable (last 1000 entries)
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]

    def read_file(self, path: str, encoding: str = 'utf-8') -> str:
        """Read file content with security validation"""
        try:
            validated_path = self._validate_path(path, 'read')

            if not os.path.exists(validated_path):
                raise FileNotFoundError(f"File not found: {path}")

            if os.path.getsize(validated_path) > self.max_file_size:
                raise ValueError(f"File too large: {path}")

            with open(validated_path, 'r', encoding=encoding) as f:
                content = f.read()

            self._log_access('read', path, True)
            return content

        except Exception as e:
            self._log_access('read', path, False)
            raise e

    def write_file(self, path: str, content: str, encoding: str = 'utf-8') -> bool:
        """Write content to file with security validation"""
        try:
            validated_path = self._validate_path(path, 'write')

            # Ensure directory exists
            os.makedirs(os.path.dirname(validated_path), exist_ok=True)

            # Check content size
            if len(content.encode(encoding)) > self.max_file_size:
                raise ValueError(f"Content too large for: {path}")

            with open(validated_path, 'w', encoding=encoding) as f:
                f.write(content)

            self._log_access('write', path, True)
            return True

        except Exception as e:
            self._log_access('write', path, False)
            raise e

    def list_files(self, directory: str, pattern: str = "*") -> List[str]:
        """List files in directory with security validation"""
        validated_path = self._validate_path(directory, 'read')

        if not os.path.exists(validated_path):
            return []

        from glob import glob
        search_pattern = os.path.join(validated_path, pattern)
        files = glob(search_pattern, recursive=True)

        # Return relative paths
        base_path = os.path.commonpath([validated_path] + files)
        return [os.path.relpath(f, base_path) for f in files if os.path.isfile(f)]

    def get_file_info(self, path: str) -> Optional[Dict]:
        """Get file metadata"""
        try:
            validated_path = self._validate_path(path, 'read')

            if not os.path.exists(validated_path):
                return None

            stat = os.stat(validated_path)
            return {
                'path': path,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'is_file': os.path.isfile(validated_path),
                'is_dir': os.path.isdir(validated_path)
            }
        except:
            return None

    def copy_file(self, src: str, dst: str) -> bool:
        """Copy file with security validation"""
        try:
            src_path = self._validate_path(src, 'read')
            dst_path = self._validate_path(dst, 'write')

            shutil.copy2(src_path, dst_path)
            self._log_access('copy', f"{src} -> {dst}", True)
            return True
        except Exception as e:
            self._log_access('copy', f"{src} -> {dst}", False)
            raise e

    def delete_file(self, path: str) -> bool:
        """Delete file with security validation"""
        try:
            validated_path = self._validate_path(path, 'write')

            if not os.path.exists(validated_path):
                return False

            os.remove(validated_path)
            self._log_access('delete', path, True)
            return True
        except Exception as e:
            self._log_access('delete', path, False)
            raise e

    def find_similar_templates(self, query: str, max_results: int = 5) -> List[Dict]:
        """Find templates similar to query"""
        templates = []
        skills_dir = os.path.abspath(Config.SKILLS_OUTPUT_DIR)

        if not os.path.exists(skills_dir):
            return templates

        # Search through all timestamped directories
        for item in os.listdir(skills_dir):
            item_path = os.path.join(skills_dir, item)
            if os.path.isdir(item_path):
                metadata_file = os.path.join(item_path, 'metadata.json')
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)

                        # Simple similarity check (can be enhanced)
                        if any(word.lower() in metadata.get('query', '').lower()
                               for word in query.split() if len(word) > 2):
                            templates.append({
                                'timestamp': item,
                                'query': metadata.get('query', ''),
                                'template_file': os.path.join(item_path, 'skill.md')
                            })

                            if len(templates) >= max_results:
                                break
                    except:
                        continue

        return templates

    def get_examples_by_domain(self, domain: str) -> List[Dict]:
        """Get example files by domain/keyword"""
        examples = []
        examples_dir = 'examples'

        if not os.path.exists(examples_dir):
            return examples

        for file_path in self.list_files(examples_dir, f"**/*{domain}*.md"):
            content = self.read_file(os.path.join(examples_dir, file_path))
            examples.append({
                'path': file_path,
                'content': content,
                'title': os.path.basename(file_path).replace('.md', '').replace('_', ' ').title()
            })

        return examples


class FileManager:
    """Original FileManager for backward compatibility"""

    @staticmethod
    def ensure_output_dir():
        """Ensure the skills output directory exists"""
        if not os.path.exists(Config.SKILLS_OUTPUT_DIR):
            os.makedirs(Config.SKILLS_OUTPUT_DIR)

    @staticmethod
    def save_pipeline_state(state: Any) -> str:
        """
        Save pipeline state to files
        Returns the directory path where files were saved
        """
        FileManager.ensure_output_dir()

        # Create directory for this run
        run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, state.timestamp)
        os.makedirs(run_dir, exist_ok=True)

        # Normalize skill content and determine bundle name
        normalized_content, skill_name, warnings = normalize_skill_content(
            state.template_output,
            state.query
        )
        state.template_output = normalized_content
        state.skill_name = skill_name

        bundle_dir = os.path.join(run_dir, skill_name)
        os.makedirs(bundle_dir, exist_ok=True)
        state.bundle_root = bundle_dir

        # Save skill template into bundle
        skill_file = os.path.join(bundle_dir, "SKILL.md")
        with open(skill_file, 'w', encoding='utf-8') as f:
            f.write(state.template_output)

        # Keep legacy copy for older tooling
        legacy_skill_file = os.path.join(run_dir, "skill.md")
        with open(legacy_skill_file, 'w', encoding='utf-8') as f:
            f.write(state.template_output)

        referenced_files = detect_referenced_files(state.template_output)
        created_assets = ensure_bundle_structure(bundle_dir, referenced_files)

        bundle_tree = build_tree(bundle_dir, skill_name)
        state.bundle_tree = bundle_tree

        # Save metadata
        metadata = {
            'query': state.query,
            'timestamp': state.timestamp,
            'iteration_count': state.iteration_count,
            'created_at': datetime.now().isoformat(),
            'skill_name': skill_name,
            'bundle_dir': skill_name,
            'bundle_tree': bundle_tree,
            'bundle_assets': created_assets,
            'bundle_warnings': warnings,
            'models_used': {
                'research': Config.RESEARCH_MODEL,
                'analysis': Config.ANALYSIS_MODEL,
                'template': Config.TEMPLATE_MODEL
            },
            'final_instruction': state.new_instruction,
            'history': state.history
        }

        metadata_file = os.path.join(run_dir, "metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # Save individual iteration files
        for i, iteration in enumerate(state.history, 1):
            iter_dir = os.path.join(run_dir, f"iteration_{i}")
            os.makedirs(iter_dir, exist_ok=True)

            # Save research
            with open(os.path.join(iter_dir, "research.md"), 'w', encoding='utf-8') as f:
                f.write(iteration['research'])

            # Save analysis
            with open(os.path.join(iter_dir, "analysis.md"), 'w', encoding='utf-8') as f:
                f.write(iteration['analysis'])

            # Save template
            with open(os.path.join(iter_dir, "template.md"), 'w', encoding='utf-8') as f:
                f.write(iteration['template'])

            # Save instruction
            if iteration.get('instruction'):
                with open(os.path.join(iter_dir, "instruction.txt"), 'w', encoding='utf-8') as f:
                    f.write(iteration['instruction'])

        return run_dir

    @staticmethod
    def load_pipeline_state(timestamp: str) -> Optional[Dict]:
        """Load pipeline metadata for a given timestamp"""
        metadata_file = os.path.join(
            Config.SKILLS_OUTPUT_DIR,
            timestamp,
            "metadata.json"
        )

        if not os.path.exists(metadata_file):
            return None

        with open(metadata_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def load_skill_template(timestamp: str) -> Optional[str]:
        """Load the skill template for a given timestamp"""
        metadata = FileManager.load_pipeline_state(timestamp)
        if metadata and metadata.get('skill_name'):
            skill_file = os.path.join(
                Config.SKILLS_OUTPUT_DIR,
                timestamp,
                metadata['skill_name'],
                "SKILL.md"
            )
            if os.path.exists(skill_file):
                with open(skill_file, 'r', encoding='utf-8') as f:
                    return f.read()

        legacy_file = os.path.join(
            Config.SKILLS_OUTPUT_DIR,
            timestamp,
            "skill.md"
        )
        if os.path.exists(legacy_file):
            with open(legacy_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    @staticmethod
    def save_edited_template(timestamp: str, content: str) -> bool:
        """Save an edited template"""
        metadata = FileManager.load_pipeline_state(timestamp) or {}
        normalized_content, skill_name, warnings = normalize_skill_content(
            content,
            metadata.get('query', 'skill')
        )

        run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, timestamp)
        bundle_dir = os.path.join(run_dir, skill_name)

        if metadata.get('skill_name') and metadata['skill_name'] != skill_name:
            old_dir = os.path.join(run_dir, metadata['skill_name'])
            if os.path.exists(old_dir):
                os.rename(old_dir, bundle_dir)

        os.makedirs(bundle_dir, exist_ok=True)

        skill_file = os.path.join(bundle_dir, "SKILL.md")

        try:
            with open(skill_file, 'w', encoding='utf-8') as f:
                f.write(normalized_content)

            legacy_skill_file = os.path.join(run_dir, "skill.md")
            with open(legacy_skill_file, 'w', encoding='utf-8') as f:
                f.write(normalized_content)

            referenced_files = detect_referenced_files(normalized_content)
            created_assets = ensure_bundle_structure(bundle_dir, referenced_files)
            bundle_tree = build_tree(bundle_dir, skill_name)

            metadata.update({
                'skill_name': skill_name,
                'bundle_dir': skill_name,
                'bundle_tree': bundle_tree,
                'bundle_assets': created_assets,
                'bundle_warnings': warnings
            })

            metadata_file = os.path.join(run_dir, "metadata.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False

    @staticmethod
    def list_all_runs() -> List[Dict]:
        """List all pipeline runs with basic info"""
        FileManager.ensure_output_dir()

        runs = []
        if not os.path.exists(Config.SKILLS_OUTPUT_DIR):
            return runs

        for item in os.listdir(Config.SKILLS_OUTPUT_DIR):
            item_path = os.path.join(Config.SKILLS_OUTPUT_DIR, item)
            if os.path.isdir(item_path):
                metadata_file = os.path.join(item_path, "metadata.json")
                if os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        runs.append({
                            'timestamp': item,
                            'query': metadata.get('query', ''),
                            'iteration_count': metadata.get('iteration_count', 0),
                            'created_at': metadata.get('created_at', '')
                        })
                    except:
                        continue

        # Sort by timestamp (newest first)
        runs.sort(key=lambda x: x['timestamp'], reverse=True)
        return runs

    @staticmethod
    def delete_run(timestamp: str) -> bool:
        """Delete a pipeline run directory"""
        import shutil
        run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, timestamp)

        if not os.path.exists(run_dir):
            return False

        try:
            shutil.rmtree(run_dir)
            return True
        except:
            return False
