import os
import json
import zipfile
from io import BytesIO
from datetime import datetime

from config import Config
from utils.file_manager import FileManager


class ExportManager:
    """Manages export functionality for templates and pipeline runs"""

    @staticmethod
    def create_skill_export(timestamp: str) -> BytesIO:
        """
        Create a zip file containing only SKILL.md
        Returns BytesIO object containing the zip data
        """
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, timestamp)
            metadata = FileManager.load_pipeline_state(timestamp) or {}
            skill_name = metadata.get('skill_name')

            if skill_name:
                skill_file = os.path.join(run_dir, skill_name, "SKILL.md")
            else:
                skill_file = os.path.join(run_dir, "skill.md")

            if os.path.exists(skill_file):
                zip_file.write(skill_file, "SKILL.md")

        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def create_bundle_export(timestamp: str) -> BytesIO:
        """
        Create a zip file containing the skill bundle directory
        Returns BytesIO object containing the zip data
        """
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, timestamp)
            metadata = FileManager.load_pipeline_state(timestamp) or {}
            skill_name = metadata.get('skill_name')
            if not skill_name:
                skill_name = "skill"

            bundle_dir = os.path.join(run_dir, skill_name)
            if os.path.exists(bundle_dir):
                for root, _, files in os.walk(bundle_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, run_dir)
                        zip_file.write(file_path, arc_path)
            else:
                # Legacy fallback: include root-level files for older runs
                for file in ("skill.md", "metadata.json"):
                    file_path = os.path.join(run_dir, file)
                    if os.path.exists(file_path):
                        zip_file.write(file_path, file)

        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def create_full_export(timestamp: str) -> BytesIO:
        """
        Create a zip file containing all iterations and files
        Returns BytesIO object containing the zip data
        """
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, timestamp)

            # Add all files from the run directory
            for root, dirs, files in os.walk(run_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate relative path from run_dir
                    arc_path = os.path.relpath(file_path, run_dir)
                    zip_file.write(file_path, arc_path)

            # Add export info
            export_info = {
                'exported_at': datetime.now().isoformat(),
                'export_type': 'full',
                'pipeline_run': timestamp,
                'total_files': len([f for _, _, files in os.walk(run_dir) for f in files])
            }
            zip_file.writestr("export_info.json", json.dumps(export_info, indent=2))

        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def create_multi_export(timestamps: list) -> BytesIO:
        """
        Create a zip file containing multiple pipeline runs
        Returns BytesIO object containing the zip data
        """
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Create index
            index = {
                'exports': [],
                'created_at': datetime.now().isoformat(),
                'total_runs': len(timestamps)
            }

            for i, timestamp in enumerate(timestamps, 1):
                run_dir = os.path.join(Config.SKILLS_OUTPUT_DIR, timestamp)

                # Add main skill file with indexed name
                skill_file = os.path.join(run_dir, "skill.md")
                if os.path.exists(skill_file):
                    zip_file.write(skill_file, f"{timestamp}_skill.md")

                # Add metadata
                metadata_file = os.path.join(run_dir, "metadata.json")
                if os.path.exists(metadata_file):
                    zip_file.write(metadata_file, f"{timestamp}_metadata.json")

                # Load metadata for index
                metadata = FileManager.load_pipeline_state(timestamp)
                if metadata:
                    index['exports'].append({
                        'timestamp': timestamp,
                        'query': metadata.get('query', ''),
                        'iteration_count': metadata.get('iteration_count', 0),
                        'created_at': metadata.get('created_at', '')
                    })

            # Add index file
            zip_file.writestr("index.json", json.dumps(index, indent=2))

            # Add README
            readme_content = ExportManager._create_multi_export_readme(timestamps)
            zip_file.writestr("README.md", readme_content)

        zip_buffer.seek(0)
        return zip_buffer

    @staticmethod
    def _create_full_export_readme(timestamp: str) -> str:
        """Create README content for full export"""
        metadata = FileManager.load_pipeline_state(timestamp)
        query = metadata.get('query', 'Unknown') if metadata else 'Unknown'
        iterations = metadata.get('iteration_count', 0) if metadata else 0

        return f"""# AI Skills Development Pipeline - Full Export

## Overview
This archive contains the complete output from a pipeline run, including all iterations and intermediate results.

## Details
- **Original Query**: {query}
- **Generated**: {timestamp}
- **Total Iterations**: {iterations}
- **Exported**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Directory Structure
```
/
├── skill.md              # Final generated skill template
├── metadata.json         # Pipeline metadata and configuration
├── iteration_1/          # First iteration outputs
│   ├── research.md       # Research results
│   ├── analysis.md       # Analysis results
│   ├── template.md       # Generated template
│   └── instruction.txt   # Next instruction (if any)
├── iteration_2/          # Second iteration (if applicable)
└── ...                   # Additional iterations
```

## Usage
1. Start with `skill.md` for the final template
2. Review iterations in the `iteration_*` directories to understand the refinement process
3. Check `metadata.json` for configuration and history

## Generated By
AI Skills Development Pipeline
Models Used:
- Research: {Config.RESEARCH_MODEL}
- Analysis: {Config.ANALYSIS_MODEL}
- Template: {Config.TEMPLATE_MODEL}
"""

    @staticmethod
    def _create_multi_export_readme(timestamps: list) -> str:
        """Create README content for multi-export"""
        return f"""# AI Skills Development Pipeline - Multiple Export

## Overview
This archive contains multiple skill templates generated by the AI Skills Development Pipeline.

## Details
- **Number of Templates**: {len(timestamps)}
- **Exported**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Files
Each template includes:
- `{timestamp}_skill.md` - The generated skill template
- `{timestamp}_metadata.json` - Pipeline metadata

See `index.json` for a complete listing of all templates with their queries and metadata.

## Usage
1. Check `index.json` for an overview of all templates
2. Review individual templates based on your needs
3. Each template is independent and can be used separately

## Generated By
AI Skills Development Pipeline
Models Used:
- Research: {Config.RESEARCH_MODEL}
- Analysis: {Config.ANALYSIS_MODEL}
- Template: {Config.TEMPLATE_MODEL}
"""
