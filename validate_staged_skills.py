#!/usr/bin/env python3
"""
Comprehensive validation script for JSON files in staged-skills directory.

This script validates all JSON files against the EVAL_SCHEMA defined in scripts/load_skills.py
and checks for file references using the validate_file_references function.

Usage:
    python validate_staged_skills.py

The script will:
1. Import the EVAL_SCHEMA from load_skills.py
2. Find all JSON files in all subdirectories of staged-skills
3. Validate each JSON file against the schema
4. Check for file references using the validate_file_references function
5. Report detailed results: which files are valid, invalid, and what specific errors exist
6. Provide a summary at the end
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Add the scripts directory to the path to import EVAL_SCHEMA and validation functions
script_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(script_dir))

try:
    from load_skills import EVAL_SCHEMA, validate_eval_json, validate_eval_file_references
    import jsonschema
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure the scripts/load_skills.py file exists and contains the required functions.")
    sys.exit(1)


class ValidationResult:
    """Container for validation results"""
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.is_valid = False
        self.schema_valid = False
        self.file_refs_valid = False
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.file_ref_count = 0
        self.eval_data = None

    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)

    def mark_valid(self):
        """Mark as valid (both schema and file references)"""
        self.is_valid = True
        self.schema_valid = True
        self.file_refs_valid = True


class SkillValidator:
    """Comprehensive validator for staged skills JSON files"""
    
    def __init__(self, staged_skills_dir: Path):
        self.staged_skills_dir = staged_skills_dir
        self.results: Dict[str, ValidationResult] = {}
        self.total_files = 0
        self.valid_files = 0
        self.invalid_files = 0
        self.skill_directories: List[Path] = []

    def find_json_files(self) -> List[Path]:
        """Find all JSON files in all subdirectories of staged-skills"""
        json_files = []
        
        if not self.staged_skills_dir.exists():
            raise FileNotFoundError(f"Staged skills directory not found: {self.staged_skills_dir}")
        
        # Find all skill directories
        for item in self.staged_skills_dir.iterdir():
            if item.is_dir():
                self.skill_directories.append(item)
                # Find JSON files in each skill directory
                for json_file in item.glob("*.json"):
                    json_files.append(json_file)
        
        return sorted(json_files)

    def validate_json_syntax(self, file_path: Path) -> Tuple[bool, Any, str]:
        """Validate JSON syntax and return data if valid"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return True, data, ""
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON syntax: {e}"
            if hasattr(e, 'lineno'):
                error_msg += f" (line {e.lineno})"
            return False, None, error_msg
        except Exception as e:
            return False, None, f"Error reading file: {e}"

    def validate_schema(self, data: Any, file_path: Path) -> Tuple[bool, str]:
        """Validate data against EVAL_SCHEMA"""
        try:
            jsonschema.validate(data, EVAL_SCHEMA)
            return True, ""
        except jsonschema.ValidationError as e:
            error_msg = f"Schema validation error: {e.message}"
            if e.absolute_path:
                error_msg += f" (path: {' -> '.join(str(p) for p in e.absolute_path)})"
            if e.context and len(e.context) > 0:
                error_msg += f" (context: {e.context[0].message})"
            return False, error_msg
        except Exception as e:
            return False, f"Schema validation failed: {e}"

    def validate_file_references(self, data: Any, file_path: Path) -> Tuple[bool, str, int]:
        """Validate file references in the data"""
        try:
            validate_eval_file_references(data, str(file_path))
            # Count file references for reporting
            import re
            text = json.dumps(data)
            file_pattern = re.compile(r"\$\{file:([^}]+)\}")
            file_refs = file_pattern.findall(text)
            return True, "", len(file_refs)
        except Exception as e:
            # Clean up the error message to remove emojis for cleaner output
            error_msg = str(e).replace("🚨 RED ALARM: ", "").replace("❌ ", "").replace("💡 ", "")
            return False, error_msg, 0

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single JSON file comprehensively"""
        result = ValidationResult(file_path)
        
        # Step 1: Validate JSON syntax
        syntax_valid, data, syntax_error = self.validate_json_syntax(file_path)
        if not syntax_valid:
            result.add_error(f"JSON syntax error: {syntax_error}")
            return result
        
        result.eval_data = data
        
        # Step 2: Validate against schema
        schema_valid, schema_error = self.validate_schema(data, file_path)
        if schema_valid:
            result.schema_valid = True
        else:
            result.add_error(f"Schema validation failed: {schema_error}")
        
        # Step 3: Validate file references
        file_refs_valid, file_refs_error, file_ref_count = self.validate_file_references(data, file_path)
        result.file_ref_count = file_ref_count
        
        if file_refs_valid:
            result.file_refs_valid = True
        else:
            result.add_error(f"File reference validation failed: {file_refs_error}")
        
        # Step 4: Additional semantic validations
        self.validate_semantic_requirements(data, result)
        
        # Mark as valid if all checks pass
        if result.schema_valid and result.file_refs_valid and not result.errors:
            result.mark_valid()
        
        return result

    def validate_semantic_requirements(self, data: Any, result: ValidationResult):
        """Perform additional semantic validations beyond schema"""
        try:
            # Check required fields are not empty
            if "id" in data and not data["id"].strip():
                result.add_error("Field 'id' is empty")
            
            if "name" in data and not data["name"].strip():
                result.add_error("Field 'name' is empty")
            
            # Validate chain step IDs are unique
            if "chain" in data:
                step_ids = [step.get("id") for step in data["chain"]]
                if len(step_ids) != len(set(step_ids)):
                    result.add_error("Duplicate step IDs found in chain")
            
            # Validate intermediary IDs are unique (if present)
            if "intermediaries" in data:
                intermediary_ids = [inter.get("id") for inter in data["intermediaries"]]
                if len(intermediary_ids) != len(set(intermediary_ids)):
                    result.add_error("Duplicate intermediary IDs found")
            
            # Validate judge view references point to valid steps/intermediaries
            if "judge" in data and "view" in data["judge"]:
                chain_ids = set(step.get("id") for step in data.get("chain", []))
                intermediary_ids = set(inter.get("id") for inter in data.get("intermediaries", []))
                
                for view_key in ["A", "B"]:
                    if view_key in data["judge"]["view"]:
                        for view_item in data["judge"]["view"][view_key]:
                            if view_item.get("kind") == "step" and view_item.get("id") not in chain_ids:
                                result.add_error(f"Judge view {view_key} references unknown step ID: {view_item.get('id')}")
                            elif view_item.get("kind") == "intermediary" and view_item.get("id") not in intermediary_ids:
                                result.add_error(f"Judge view {view_key} references unknown intermediary ID: {view_item.get('id')}")
            
        except Exception as e:
            result.add_warning(f"Semantic validation error: {e}")

    def validate_all_files(self) -> None:
        """Validate all JSON files in the staged-skills directory"""
        print("🔍 Comprehensive Staged Skills Validation")
        print("=" * 50)
        print(f"📁 Directory: {self.staged_skills_dir}")
        
        # Find all JSON files
        try:
            json_files = self.find_json_files()
        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            return
        
        self.total_files = len(json_files)
        print(f"📊 Found {self.total_files} JSON files in {len(self.skill_directories)} skill directories")
        print()
        
        if self.total_files == 0:
            print("⚠️  No JSON files found to validate.")
            return
        
        # Validate each file
        for i, file_path in enumerate(json_files, 1):
            relative_path = file_path.relative_to(self.staged_skills_dir)
            print(f"[{i:3d}/{self.total_files}] Validating: {relative_path}")
            
            result = self.validate_file(file_path)
            self.results[str(relative_path)] = result
            
            if result.is_valid:
                self.valid_files += 1
                status = "✅ VALID"
                if result.file_ref_count > 0:
                    status += f" ({result.file_ref_count} file refs)"
            else:
                self.invalid_files += 1
                status = "❌ INVALID"
            
            print(f"    {status}")
            
            # Show errors immediately
            for error in result.errors:
                print(f"    💥 {error}")
            
            # Show warnings
            for warning in result.warnings:
                print(f"    ⚠️  {warning}")
            
            print()

    def print_detailed_results(self) -> None:
        """Print detailed validation results"""
        print("📋 DETAILED VALIDATION RESULTS")
        print("=" * 50)
        
        # Group results by skill directory
        by_skill = {}
        for file_path, result in self.results.items():
            skill_name = Path(file_path).parent.name
            if skill_name not in by_skill:
                by_skill[skill_name] = []
            by_skill[skill_name].append((file_path, result))
        
        # Print results by skill
        for skill_name in sorted(by_skill.keys()):
            skill_results = by_skill[skill_name]
            valid_count = sum(1 for _, result in skill_results if result.is_valid)
            total_count = len(skill_results)
            
            print(f"\n📂 {skill_name} ({valid_count}/{total_count} valid)")
            print("-" * 40)
            
            for file_path, result in sorted(skill_results):
                file_name = Path(file_path).name
                status = "✅" if result.is_valid else "❌"
                print(f"  {status} {file_name}")
                
                if not result.is_valid:
                    for error in result.errors:
                        print(f"      💥 {error}")
                
                if result.warnings:
                    for warning in result.warnings:
                        print(f"      ⚠️  {warning}")

    def print_summary(self) -> None:
        """Print validation summary"""
        print("\n" + "=" * 50)
        print("📊 VALIDATION SUMMARY")
        print("=" * 50)
        
        print(f"📁 Directory: {self.staged_skills_dir}")
        print(f"📋 Skill directories: {len(self.skill_directories)}")
        print(f"📄 Total files: {self.total_files}")
        print(f"✅ Valid files: {self.valid_files}")
        print(f"❌ Invalid files: {self.invalid_files}")
        
        if self.total_files > 0:
            success_rate = (self.valid_files / self.total_files) * 100
            print(f"📈 Success rate: {success_rate:.1f}%")
        
        # Schema vs file reference validation breakdown
        schema_valid_count = sum(1 for result in self.results.values() if result.schema_valid)
        file_refs_valid_count = sum(1 for result in self.results.values() if result.file_refs_valid)
        
        print(f"\n🔍 Validation Breakdown:")
        print(f"  📋 Schema validation: {schema_valid_count}/{self.total_files} passed")
        print(f"  📁 File reference validation: {file_refs_valid_count}/{self.total_files} passed")
        
        # File reference statistics
        total_file_refs = sum(result.file_ref_count for result in self.results.values())
        print(f"  🔗 Total file references found: {total_file_refs}")
        
        # Skill directory breakdown
        by_skill = {}
        for file_path, result in self.results.items():
            skill_name = Path(file_path).parent.name
            if skill_name not in by_skill:
                by_skill[skill_name] = {"valid": 0, "total": 0}
            by_skill[skill_name]["total"] += 1
            if result.is_valid:
                by_skill[skill_name]["valid"] += 1
        
        print(f"\n📂 Per-skill Summary:")
        for skill_name in sorted(by_skill.keys()):
            stats = by_skill[skill_name]
            rate = (stats["valid"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            status = "✅" if rate == 100 else "⚠️" if rate > 0 else "❌"
            print(f"  {status} {skill_name}: {stats['valid']}/{stats['total']} ({rate:.0f}%)")
        
        # Overall status
        print(f"\n🎯 Overall Status:")
        if self.invalid_files == 0:
            print("  🎉 ALL FILES VALID - Ready for production!")
        elif self.valid_files > 0:
            print(f"  ⚠️  MIXED RESULTS - {self.invalid_files} files need attention")
        else:
            print("  🚨 NO VALID FILES - Critical issues need resolution")


def main():
    """Main function to run the validation"""
    # Determine the staged-skills directory path
    script_path = Path(__file__).resolve()
    project_root = script_path.parent
    staged_skills_dir = project_root / "staged-skills"
    
    print(f"🚀 Starting validation for: {staged_skills_dir}")
    print()
    
    # Create validator and run validation
    validator = SkillValidator(staged_skills_dir)
    
    try:
        validator.validate_all_files()
        validator.print_detailed_results()
        validator.print_summary()
        
        # Exit with appropriate code
        if validator.invalid_files > 0:
            print(f"\n❌ Validation completed with {validator.invalid_files} errors.")
            sys.exit(1)
        else:
            print(f"\n✅ Validation completed successfully! All {validator.valid_files} files are valid.")
            sys.exit(0)
            
    except Exception as e:
        print(f"💥 Fatal error during validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()