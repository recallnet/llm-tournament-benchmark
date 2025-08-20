#!/usr/bin/env python3
"""
Tournament Summarizer - Creates tidy tournament summaries from judge cache files.
Provides per-eval and per-skill tournament results with match details and model rankings.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_judge_cache_files(tournaments_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load all judge cache files organized by match_id."""
    matches = defaultdict(list)

    if not tournaments_dir.exists():
        return {}

    for skill_dir in tournaments_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        for cache_file in skill_dir.glob("*.json"):
            try:
                with open(cache_file) as f:
                    judge_data = json.load(f)

                match_id = judge_data.get("metadata", {}).get("match_id")
                if match_id:
                    matches[match_id].append(judge_data)

            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️  Skipping corrupted cache file {cache_file}: {e}")
                continue

    return dict(matches)


def calculate_match_result(judge_votes: list[dict[str, Any]]) -> tuple[str, dict[str, int], list[dict[str, str]]]:
    """Calculate match result from multiple judge votes."""
    vote_counts = {"A": 0, "B": 0, "TIE": 0}
    judge_details = []

    for judge_data in judge_votes:
        vote = judge_data.get("vote", "TIE")
        judge_id = judge_data.get("metadata", {}).get("judge_id", "unknown")

        if vote in vote_counts:
            vote_counts[vote] += 1
        else:
            vote_counts["TIE"] += 1  # Default invalid votes to TIE
            vote = "TIE"

        judge_details.append({
            "judge_id": judge_id,
            "vote": vote
        })

    # Determine winner by majority
    max_votes = max(vote_counts.values())
    winners = [vote for vote, count in vote_counts.items() if count == max_votes]

    if len(winners) == 1:
        result = winners[0]
    else:
        result = "TIE"  # Multiple categories tied for most votes

    return result, vote_counts, judge_details


def create_tournament_summary(matches: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Create tournament summary organized by skill and eval."""
    tournaments_by_skill: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    skill_summaries: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "matches": [],
        "model_scores": defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0, "total": 0}),
        "total_matches": 0
    })

    # Process matches
    for match_id, judge_votes in matches.items():
        if not judge_votes:
            continue

        # Get match metadata from first judge
        metadata = judge_votes[0].get("metadata", {})
        skill_id = metadata.get("skill_id")
        eval_id = metadata.get("eval_id")
        model_a_id = metadata.get("model_a_id")
        model_b_id = metadata.get("model_b_id")

        if not all([skill_id, eval_id, model_a_id, model_b_id]):
            continue

        # Calculate match result
        result, vote_counts, judge_details = calculate_match_result(judge_votes)

        match_summary = {
            "match_id": match_id,
            "model_a": model_a_id,
            "model_b": model_b_id,
            "judges": judge_details,
            "vote_counts": vote_counts,
            "winner": result,
            "judge_count": len(judge_votes),
            "timestamp": metadata.get("timestamp")
        }

        # Add to tournaments
        tournaments_by_skill[skill_id][eval_id].append(match_summary)

        # Update skill-level scores
        skill_summaries[skill_id]["matches"].append(match_summary)
        skill_summaries[skill_id]["total_matches"] += 1

        # Update model scores
        skill_scores = skill_summaries[skill_id]["model_scores"]
        skill_scores[model_a_id]["total"] += 1
        skill_scores[model_b_id]["total"] += 1

        if result == "A":
            skill_scores[model_a_id]["wins"] += 1
            skill_scores[model_b_id]["losses"] += 1
        elif result == "B":
            skill_scores[model_b_id]["wins"] += 1
            skill_scores[model_a_id]["losses"] += 1
        else:  # TIE
            skill_scores[model_a_id]["ties"] += 1
            skill_scores[model_b_id]["ties"] += 1

    # Calculate final rankings
    tournament_summaries = {}

    for skill_id, evals in tournaments_by_skill.items():
        skill_data = skill_summaries[skill_id]

        # Calculate model rankings for this skill
        model_rankings = []
        for model_id, scores in skill_data["model_scores"].items():
            win_rate = scores["wins"] / scores["total"] if scores["total"] > 0 else 0
            points = scores["wins"] + (scores["ties"] * 0.5)  # 1 point for win, 0.5 for tie

            model_rankings.append({
                "model_id": model_id,
                "wins": scores["wins"],
                "losses": scores["losses"],
                "ties": scores["ties"],
                "total_matches": scores["total"],
                "points": points,
                "win_rate": round(win_rate, 3)
            })

        # Sort by points (descending), then by win rate
        model_rankings.sort(key=lambda x: (x["points"], x["win_rate"]), reverse=True)

        # Add rank numbers
        for i, model in enumerate(model_rankings):
            model["rank"] = i + 1

        # Create skill-level match history (all matches across evals, sorted by timestamp)
        all_skill_matches = sorted(skill_data["matches"], key=lambda x: x.get("timestamp", ""))

        tournament_summaries[skill_id] = {
            "skill_id": skill_id,
            "total_matches": skill_data["total_matches"],
            "model_rankings": model_rankings,
            "match_history": all_skill_matches,
            "evals": {}
        }

        # Add per-eval details
        for eval_id, eval_matches in evals.items():
            # Calculate per-eval model scores
            eval_scores: dict[str, dict[str, int]] = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0, "total": 0})

            for match in eval_matches:
                model_a = match["model_a"]
                model_b = match["model_b"]
                winner = match["winner"]

                eval_scores[model_a]["total"] += 1
                eval_scores[model_b]["total"] += 1

                if winner == "A":
                    eval_scores[model_a]["wins"] += 1
                    eval_scores[model_b]["losses"] += 1
                elif winner == "B":
                    eval_scores[model_b]["wins"] += 1
                    eval_scores[model_a]["losses"] += 1
                else:
                    eval_scores[model_a]["ties"] += 1
                    eval_scores[model_b]["ties"] += 1

            # Create eval rankings
            eval_rankings = []
            for model_id, scores in eval_scores.items():
                win_rate = scores["wins"] / scores["total"] if scores["total"] > 0 else 0
                points = scores["wins"] + (scores["ties"] * 0.5)

                eval_rankings.append({
                    "model_id": model_id,
                    "wins": scores["wins"],
                    "losses": scores["losses"],
                    "ties": scores["ties"],
                    "total_matches": scores["total"],
                    "points": points,
                    "win_rate": round(win_rate, 3)
                })

            eval_rankings.sort(key=lambda x: (x["points"], x["win_rate"]), reverse=True)
            for i, model in enumerate(eval_rankings):
                model["rank"] = i + 1

            # Sort matches by timestamp for chronological order
            eval_matches_sorted = sorted(eval_matches, key=lambda x: x.get("timestamp", ""))

            tournament_summaries[skill_id]["evals"][eval_id] = {
                "eval_id": eval_id,
                "total_matches": len(eval_matches),
                "model_rankings": eval_rankings,
                "match_history": eval_matches_sorted,
                "matches": eval_matches_sorted  # Keep both for compatibility
            }

    return tournament_summaries


def main() -> None:
    """Main function for tournament summarization."""
    tournaments_dir = Path("data/tournaments")
    output_file = Path("data/tournament_summaries.json")

    print("📊 Tournament Summarizer Starting!")

    if not tournaments_dir.exists():
        print(f"⚠️  No tournament cache directory found at {tournaments_dir}")
        summary = {
            "tournaments": {},
            "execution_info": {
                "status": "no_tournament_data",
                "message": "No tournament cache files found",
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    else:
        # Load all judge cache files
        print("📂 Loading judge cache files...")
        matches = load_judge_cache_files(tournaments_dir)

        if not matches:
            print("⚠️  No valid tournament matches found")
            summary = {
                "tournaments": {},
                "execution_info": {
                    "status": "no_valid_matches",
                    "message": "No valid tournament matches found in cache",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        else:
            print(f"🔍 Found {len(matches)} tournament matches")

            # Create tournament summaries
            tournament_summaries = create_tournament_summary(matches)

            # Calculate overall stats
            total_matches = sum(skill["total_matches"] for skill in tournament_summaries.values())
            total_skills = len(tournament_summaries)
            total_evals = sum(len(skill["evals"]) for skill in tournament_summaries.values())

            print(f"✅ Processed {total_matches} matches across {total_evals} evals in {total_skills} skills")

            summary = {
                "tournaments": tournament_summaries,
                "execution_info": {
                    "status": "completed",
                    "total_matches": total_matches,
                    "total_skills": total_skills,
                    "total_evals": total_evals,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

            # Print quick summary
            for skill_id, skill_data in tournament_summaries.items():
                print(f"\n🏆 {skill_id}:")
                print(f"   📊 {skill_data['total_matches']} total matches across {len(skill_data['evals'])} evals")
                print("   🥇 Top 3 models:")
                for model in skill_data['model_rankings'][:3]:
                    print(f"      {model['rank']}. {model['model_id']} - {model['points']} pts ({model['wins']}W/{model['losses']}L/{model['ties']}T)")

    # Save results
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n💾 Tournament summaries saved to: {output_file}")


if __name__ == "__main__":
    main()
