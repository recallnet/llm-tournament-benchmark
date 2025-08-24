#!/usr/bin/env python3
"""
Generate benchmarks.json with leaderboard data from tournament results and skill ratings.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


class BenchmarkGenerator:
    """Generates benchmark leaderboard data from AFBench results."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        
    def load_data_files(self) -> Dict[str, Any]:
        """Load all required data files."""
        data = {}
        
        files = {
            "skill_ratings": "skill_ratings.json",
            "tournament_summaries": "tournament_summaries.json", 
            "loaded_models": "loaded_models.json",
            "loaded_judges": "loaded_judges.json",
            "loaded_skills": "loaded_skills.json"
        }
        
        for key, filename in files.items():
            filepath = self.data_dir / filename
            if not filepath.exists():
                raise FileNotFoundError(f"Required file not found: {filepath}")
            
            with open(filepath) as f:
                data[key] = json.load(f)
        
        return data
    
    def generate_skills_metadata(self, skills_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate skills metadata from loaded skills data."""
        skills_meta = {}
        display_order = 1
        
        # Map skill categories to friendly names
        category_names = {
            "code_generation": "Programming & Development",
            "document_summarization": "Reading Comprehension", 
            "empathy": "Emotional Intelligence",
            "persuasiveness": "Communication Skills",
            "harm_avoidance": "Safety & Ethics",
            "hidden_messages": "Instruction Following", 
            "ethical_loopholes": "Moral Reasoning",
            "respect_no_em_dash_requests": "Constraint Following"
        }
        
        for skill_category, skill_info in skills_data.get("skills", {}).items():
            # Generate friendly skill name
            skill_name = skill_category.replace("_", " ").title()
            category = category_names.get(skill_category, "General")
            
            skills_meta[skill_category] = {
                "id": skill_category,
                "name": skill_name,
                "description": f"Evaluation of {skill_name.lower()} capabilities across multiple scenarios",
                "category": category,
                "displayOrder": display_order,
                "isEnabled": True,
                "methodology": "Swiss-system tournament with head-to-head model comparisons judged by expert models",
                "longDescription": f"This skill evaluates model performance in {skill_name.lower()} through systematic pairwise comparisons. Models compete in Swiss-system tournaments where expert judges evaluate their responses to carefully crafted scenarios. Rankings are calculated using the OpenSkill rating system, providing statistically robust performance measures with confidence intervals."
            }
            display_order += 1
            
        return skills_meta
    
    def calculate_confidence_interval(self, mu: float, sigma: float) -> List[float]:
        """Calculate 95% confidence interval from OpenSkill mu and sigma."""
        # 95% CI is approximately mu ± 1.96 * sigma
        margin = 1.96 * sigma
        return [round(mu - margin, 2), round(mu + margin, 2)]
    
    def generate_model_scores(
        self, 
        skill_ratings: Dict[str, Any],
        tournament_summaries: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate model scores data."""
        model_scores = {}
        
        # Process skill ratings to get scores
        for skill_id, skill_data in skill_ratings.get("skill_ratings", {}).items():
            model_ratings = skill_data.get("model_ratings", {})
            
            # Get tournament data for ranking
            tournament_data = tournament_summaries.get("tournaments", {}).get(skill_id, {})
            rankings = {r["model_id"]: r["rank"] for r in tournament_data.get("model_rankings", [])}
            
            for model_id, rating_data in model_ratings.items():
                if model_id not in model_scores:
                    model_scores[model_id] = {"id": model_id, "scores": {}}
                
                mu = rating_data.get("mu", 1500.0)
                sigma = rating_data.get("sigma", 100.0)
                rank = rankings.get(model_id, 999)  # Default high rank if not found
                
                model_scores[model_id]["scores"][skill_id] = {
                    "rawScore": round(mu, 2),
                    "confidenceInterval": self.calculate_confidence_interval(mu, sigma),
                    "rank": rank,
                    "evaluatedAt": datetime.now().isoformat()
                }
        
        return list(model_scores.values())
    
    def calculate_skill_stats(
        self, 
        skill_ratings: Dict[str, Any],
        tournament_summaries: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate statistics for each skill."""
        skill_stats = {}
        
        for skill_id, skill_data in skill_ratings.get("skill_ratings", {}).items():
            model_ratings = skill_data.get("model_ratings", {})
            
            if not model_ratings:
                continue
            
            scores = [r.get("mu", 1500.0) for r in model_ratings.values()]
            scores.sort(reverse=True)
            
            # Get evaluation count from tournament data
            tournament_data = tournament_summaries.get("tournaments", {}).get(skill_id, {})
            eval_count = len(tournament_data.get("evaluations", []))
            
            # Calculate stats
            total_models = len(scores)
            avg_score = sum(scores) / total_models if total_models > 0 else 0
            top_score = max(scores) if scores else 0
            median_score = scores[total_models // 2] if scores else 0
            
            skill_stats[skill_id] = {
                "totalModels": total_models,
                "avgScore": round(avg_score, 2),
                "topScore": round(top_score, 2),
                "medianScore": round(median_score, 2),
                "evaluationCount": eval_count
            }
        
        return skill_stats
    
    def generate_benchmarks(self) -> Dict[str, Any]:
        """Generate complete benchmarks.json structure."""
        print("Loading AFBench data files...")
        data = self.load_data_files()
        
        print("Generating skills metadata...")
        skills_metadata = self.generate_skills_metadata(data["loaded_skills"])
        
        print("Processing model scores...")
        model_scores = self.generate_model_scores(
            data["skill_ratings"], 
            data["tournament_summaries"]
        )
        
        print("Calculating skill statistics...")
        skill_stats = self.calculate_skill_stats(
            data["skill_ratings"],
            data["tournament_summaries"]
        )
        
        # Generate final benchmark structure
        benchmarks = {
            "metadata": {
                "lastUpdated": datetime.now().isoformat(),
                "benchmarkLink": "https://github.com/your-org/afbench"  # Update this URL
            },
            "skills": skills_metadata,
            "models": model_scores,
            "skillStats": skill_stats
        }
        
        return benchmarks


def main():
    """Main entry point."""
    if "snakemake" in globals():
        # Called by Snakemake
        data_dir = Path(snakemake.input[0]).parent
        output_path = Path(snakemake.output[0])
    else:
        # Called directly - require environment variable
        data_dir_env = os.getenv("AFBENCH_DATA_DIR")
        if not data_dir_env:
            raise ValueError(
                "🚨 SAFETY: generate_benchmarks.py requires explicit data directory.\n"
                "Set AFBENCH_DATA_DIR environment variable or run via Snakemake."
            )
        
        data_dir = Path(data_dir_env)
        output_path = data_dir / "benchmarks.json"
    
    print("🏆 AFBench Benchmark Generator")
    print(f"📁 Data directory: {data_dir}")
    print(f"📄 Output file: {output_path}")
    
    # Generate benchmarks
    generator = BenchmarkGenerator(data_dir)
    benchmarks = generator.generate_benchmarks()
    
    # Save to file
    with open(output_path, "w") as f:
        json.dump(benchmarks, f, indent=2)
    
    skill_count = len(benchmarks["skills"])
    model_count = len(benchmarks["models"])
    
    print(f"✅ Generated benchmarks.json:")
    print(f"   📊 {skill_count} skills")
    print(f"   🤖 {model_count} models")
    print(f"   💾 Saved to {output_path}")


if __name__ == "__main__":
    main()