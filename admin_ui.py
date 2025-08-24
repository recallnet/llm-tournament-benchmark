import glob
import json
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="AFBench Admin UI",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=None)
def load_available_data():
    """Load whatever data is available, gracefully handling missing files."""
    # Configuration: Change this to switch between data directories
    # Options: "data" (legacy), "data/quick" (development), "data/production" (production)
    data_subdir = os.environ.get("AFBENCH_ADMIN_DATA_DIR", "data/quick")
    data_dir = os.path.join(os.path.dirname(__file__), data_subdir)

    data = {
        "data_dir": data_dir,
        "available_data": set(),
        "missing_data": set(),
        "error_messages": [],
    }

    # Try to load each data file
    data_files = {
        "skill_ratings": "skill_ratings.json",
        "tournament_summaries": "tournament_summaries.json",
        "models": "loaded_models.json",
        "judges": "loaded_judges.json",
        "skills": "loaded_skills.json",
    }

    for key, filename in data_files.items():
        filepath = f"{data_dir}/{filename}"
        try:
            with open(filepath) as f:
                file_data = json.load(f)
                data[key] = file_data
                data["available_data"].add(key)
        except FileNotFoundError:
            data["missing_data"].add(key)
            data["error_messages"].append(f"{filename} not found")
        except json.JSONDecodeError as e:
            data["missing_data"].add(key)
            data["error_messages"].append(f"{filename} has invalid JSON: {e}")

    # If we have skill ratings, extract useful info
    if "skill_ratings" in data:
        ratings_data = data["skill_ratings"]
        data["valid_skills"] = set(ratings_data.get("skill_ratings", {}).keys())
        data["cache_key"] = ratings_data.get("execution_info", {}).get(
            "cache_key", "no-cache"
        )

        # If we also have tournaments, validate them
        if "tournament_summaries" in data:
            tournaments_data = data["tournament_summaries"]
            tournaments = tournaments_data.get("tournaments", {})
            data["validated_tournaments"] = {
                skill: skill_data
                for skill, skill_data in tournaments.items()
                if skill in data["valid_skills"]
            }

    # Extract metadata if available
    if "models" in data:
        data["model_ids"] = {m["id"] for m in data["models"].get("models", [])}
    if "judges" in data:
        data["judge_ids"] = {j["id"] for j in data["judges"].get("judges", [])}
    if "skills" in data:
        data["eval_ids"] = {e["id"] for e in data["skills"].get("evals", [])}

    return data


def load_conversation_log(
    skill: str, eval_id: str, model_id: str, data_dir: str = None
):
    """Load individual conversation log with hash validation."""
    # Use provided data_dir or default to quick profile
    if data_dir is None:
        data_dir = os.environ.get("AFBENCH_ADMIN_DATA_DIR", "data/quick")

    # Sanitize model_id for file names (matches pipeline logic)
    safe_model_id = model_id.replace("/", "_").replace(":", "_")
    pattern = f"{data_dir}/conversations/{skill}/{eval_id}_{safe_model_id}_*.json"
    matches = glob.glob(pattern)
    if not matches:
        return None

    latest_file = max(matches, key=os.path.getmtime)
    try:
        with open(latest_file) as f:
            return json.load(f)
    except:
        return None


def load_judge_decision(skill: str, match_id: str, judge_id: str, data_dir: str = None):
    """Load individual judge decision with hash validation."""
    # Use provided data_dir or default to quick profile
    if data_dir is None:
        data_dir = os.environ.get("AFBENCH_ADMIN_DATA_DIR", "data/quick")

    # Sanitize judge_id for file names (matches pipeline logic)
    safe_judge_id = judge_id.replace("/", "_").replace(":", "_")
    pattern = f"{data_dir}/judge_cache/{skill}/{match_id}_{safe_judge_id}_*.json"
    matches = glob.glob(pattern)
    if not matches:
        return None

    latest_file = max(matches, key=os.path.getmtime)
    try:
        with open(latest_file) as f:
            return json.load(f)
    except:
        return None


def show_data_freshness_sidebar(data):
    """Show cache key and freshness info in sidebar."""
    if not data:
        return

    cache_key = data.get("cache_key", "no-cache")
    if cache_key and cache_key != "no-cache":
        st.sidebar.info(f"🔑 Cache: {cache_key[:8]}...")
    else:
        st.sidebar.warning("⚠️ No cache key available")

    timestamp = data.get("execution_info", {}).get("timestamp")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            st.sidebar.info(f"🕐 Updated: {dt.strftime('%H:%M:%S')}")
        except:
            st.sidebar.info(f"🕐 Updated: {timestamp}")


def show_models_page(data):
    """Display models overview and details."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "site" / "utils"))
    from github_issue_helper import issue_reporter

    st.header("🤖 Models")

    # Update context for issue reporting
    issue_reporter.update_context("Models")

    models = data["models"]["models"]
    tournaments = data["tournament_summaries"].get("tournaments", {})
    ratings = data["skill_ratings"].get("skill_ratings", {})

    # Create models overview table
    model_stats = []
    for model in models:
        model_id = model["id"]

        # Calculate stats across skills
        skills_participated = 0
        total_matches = 0
        total_wins = 0
        best_skill = None
        worst_skill = None
        best_rating = float("-inf")  # Start with negative infinity
        worst_rating = float("inf")

        # Calculate best/worst skills based on ratings (not tournament participation)
        for skill, skill_data in ratings.items():
            model_ratings = skill_data.get("model_ratings", {})
            if model_id in model_ratings:
                model_rating = model_ratings[model_id]["mu"]

                if model_rating > best_rating:
                    best_rating = model_rating
                    best_skill = skill
                if model_rating < worst_rating:
                    worst_rating = model_rating
                    worst_skill = skill

        # Calculate tournament participation and stats
        for skill, tournament_data in tournaments.items():
            if model_id in [
                r["model_id"] for r in tournament_data.get("model_rankings", [])
            ]:
                skills_participated += 1

                # Find this model's ranking
                for ranking in tournament_data.get("model_rankings", []):
                    if ranking["model_id"] == model_id:
                        # Use the actual matches and wins for this model
                        model_matches = ranking.get("total_matches", 0)
                        wins = ranking.get("wins", 0)

                        total_matches += model_matches
                        total_wins += wins
                        break

        win_rate = (total_wins / total_matches * 100) if total_matches > 0 else 0

        model_stats.append(
            {
                "Model ID": model_id,
                "Author": model.get("author", "Unknown"),
                "Context": model.get("context_window", "Unknown"),
                "Endpoint": model.get("endpoint", "Unknown"),
                "Skills": skills_participated,
                "Matches": total_matches,
                "Win Rate": f"{win_rate:.1f}%",
                "Win Rate (Numeric)": win_rate,  # For proper sorting
                "Best Skill": best_skill or "None",
                "Worst Skill": worst_skill or "None",
            }
        )

    df = pd.DataFrame(model_stats)
    
    # Configure column display and sorting
    column_config = {
        "Win Rate (Numeric)": None,  # Hide the numeric column from display
        "Win Rate": st.column_config.TextColumn(
            "Win Rate",
            help="Win rate percentage based on tournament matches",
            width="small"
        )
    }
    
    # Display dataframe with proper sorting
    st.dataframe(
        df,
        use_container_width=True,
        column_config=column_config,
        hide_index=True
    )

    # Capture models overview table for issue reporting
    issue_reporter.capture_table_data("Models Overview", df)
    issue_reporter.show_issue_button("models_overview")

    # Model selection for detail view
    selected_model = st.selectbox(
        "Select model for details:", [m["Model ID"] for m in model_stats]
    )

    # Update context with selected model
    if selected_model:
        issue_reporter.update_context("Models", selected_model=selected_model)

    if selected_model:
        st.subheader(f"📊 {selected_model} Details")

        # Performance by skill table
        skill_performance = []
        for skill, skill_data in ratings.items():
            model_ratings = skill_data.get("model_ratings", {})
            if selected_model in model_ratings:
                rating = model_ratings[selected_model]["mu"]

                # Get tournament stats if available
                tournament_stats = None
                tournament_data = tournaments.get(skill, {})
                for ranking in tournament_data.get("model_rankings", []):
                    if ranking["model_id"] == selected_model:
                        tournament_stats = ranking
                        break

                skill_performance.append(
                    {
                        "Skill": skill,
                        "Rating": f"{rating:.1f}",
                        "Rank": (
                            tournament_stats.get("rank", "N/A")
                            if tournament_stats
                            else "N/A"
                        ),
                        "Wins": (
                            tournament_stats.get("wins", 0) if tournament_stats else 0
                        ),
                        "Losses": (
                            tournament_stats.get("losses", 0) if tournament_stats else 0
                        ),
                        "Ties": (
                            tournament_stats.get("ties", 0) if tournament_stats else 0
                        ),
                    }
                )

        if skill_performance:
            perf_df = pd.DataFrame(skill_performance)
            st.dataframe(perf_df, use_container_width=True)

            # Capture detailed performance table for issue reporting
            issue_reporter.capture_table_data(f"{selected_model} Performance", perf_df)
            issue_reporter.show_issue_button("model_performance")


def show_judges_page(data):
    """Display judges overview and details."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "site" / "utils"))
    from github_issue_helper import issue_reporter

    st.header("⚖️ Judges")

    # Update context for issue reporting
    issue_reporter.update_context("Judges")

    judges = data["judges"]["judges"]
    tournaments = data["tournament_summaries"].get("tournaments", {})

    # Create judges overview table
    judge_stats = []
    for judge in judges:
        judge_id = judge["id"]

        total_decisions = 0
        for _skill, tournament_data in tournaments.items():
            for match in tournament_data.get("match_history", []):
                if judge_id in match.get("judges", []):
                    total_decisions += 1

        judge_stats.append(
            {
                "Judge ID": judge_id,
                "Author": judge.get("author", "Unknown"),
                "Context": judge.get("context_window", "Unknown"),
                "Decisions": total_decisions,
            }
        )

    df = pd.DataFrame(judge_stats)
    st.dataframe(df, use_container_width=True)

    # Capture judges overview table for issue reporting
    issue_reporter.capture_table_data("Judges Overview", df)
    issue_reporter.show_issue_button("judges_overview")


def show_skills_page(data):
    """Display skills overview and evaluation details."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / "site" / "utils"))
    from github_issue_helper import issue_reporter

    st.header("🎯 Skills")

    # Update context for issue reporting
    issue_reporter.update_context("Skills")

    skills_data = data["skills"]["skills"]
    tournaments = data["tournament_summaries"].get("tournaments", {})

    # Skills grid
    cols = st.columns(2)
    for i, (skill_id, skill_info) in enumerate(skills_data.items()):
        with cols[i % 2]:
            tournament_data = tournaments.get(skill_id, {})
            total_matches = tournament_data.get("total_matches", 0)

            st.container()
            st.markdown(f"### {skill_id.replace('_', ' ').title()}")
            st.metric("Evaluations", skill_info.get("eval_count", 0))
            st.metric("Total Matches", total_matches)

    # Skill selection for details
    selected_skill = st.selectbox("Select skill for details:", list(skills_data.keys()))

    if selected_skill:
        st.subheader(f"📋 {selected_skill} Evaluations")

        skill_evals = [
            e
            for e in data["skills"]["evals"]
            if e.get("_metadata", {}).get("skill") == selected_skill
        ]

        eval_table = []
        for eval_data in skill_evals:
            eval_table.append(
                {
                    "ID": eval_data["id"],
                    "Name": eval_data["name"],
                    "Type": (
                        "Multi-step"
                        if len(eval_data.get("chain", [])) > 1
                        else "Single-step"
                    ),
                }
            )

        if eval_table:
            eval_df = pd.DataFrame(eval_table)
            st.dataframe(eval_df, use_container_width=True)

            # Evaluation detail
            selected_eval = st.selectbox(
                "Select evaluation for JSON:", [e["ID"] for e in eval_table]
            )

            if selected_eval:
                eval_json = next(
                    (e for e in skill_evals if e["id"] == selected_eval), None
                )
                if eval_json:
                    # Update context with selected skill and eval for issue reporting
                    eval_name = eval_json.get("name", selected_eval)
                    issue_reporter.update_context(
                        "Skills",
                        selected_skill=selected_skill,
                        selected_eval=selected_eval,
                        eval_name=eval_name,
                    )

                    # Capture eval data for issue reporting (only key fields to avoid URL length limits)
                    eval_summary = {
                        "id": eval_json.get("id"),
                        "name": eval_json.get("name"),
                        "type": (
                            "Multi-step"
                            if len(eval_json.get("chain", [])) > 1
                            else "Single-step"
                        ),
                        "chain_length": len(eval_json.get("chain", [])),
                        "skill": eval_json.get("_metadata", {}).get("skill"),
                    }
                    issue_reporter.capture_json_data(
                        f"{selected_skill}-{selected_eval} Summary", eval_summary
                    )

                    # Show issue button for this specific eval
                    issue_reporter.show_issue_button(
                        f"eval_{selected_skill}_{selected_eval}"
                    )

                    st.subheader(f"📄 {selected_eval} Configuration")
                    st.json(eval_json)


def show_progress_page(data):
    """Display pipeline progress and status information."""
    st.header("📊 Pipeline Progress")

    # Profile selector
    st.subheader("🔧 Profile Selection")
    
    # Available profiles
    available_profiles = {
        "data/quick": "Quick (Development)",
        "data/production": "Production (Full Evaluation)",
        "data/testonly": "Test Only (Testing)"
    }
    
    # Get current profile from data_dir
    current_profile = data["data_dir"].split("/")[-1] if "/" in data["data_dir"] else data["data_dir"]
    current_profile_path = f"data/{current_profile}" if current_profile in ["quick", "production", "testonly"] else data["data_dir"]
    
    # Create profile dropdown
    profile_options = list(available_profiles.keys())
    try:
        current_index = profile_options.index(current_profile_path)
    except ValueError:
        current_index = 0  # Default to first option if current profile not found
    
    selected_profile = st.selectbox(
        "Select Profile:",
        profile_options,
        index=current_index,
        format_func=lambda x: available_profiles[x],
        help="Switch between different data profiles. Page will refresh to show selected profile data."
    )
    
    # If profile changed, update the environment variable and rerun
    if selected_profile != current_profile_path:
        st.info(f"🔄 Switching to {available_profiles[selected_profile]} profile...")
        os.environ["AFBENCH_ADMIN_DATA_DIR"] = selected_profile
        # Clear the cache and rerun
        load_available_data.clear()
        st.rerun()

    data_dir = data["data_dir"]

    # Pipeline Stage Overview
    st.subheader("🔄 Pipeline Stages")

    stages = [
        {
            "name": "Skills Loading",
            "icon": "🎯",
            "complete": "skills" in data["available_data"],
            "file": "loaded_skills.json",
            "description": "Evaluation definitions loaded"
        },
        {
            "name": "Models Loading", 
            "icon": "🤖",
            "complete": "models" in data["available_data"],
            "file": "loaded_models.json",
            "description": "Model configurations loaded"
        },
        {
            "name": "Judges Loading",
            "icon": "⚖️", 
            "complete": "judges" in data["available_data"],
            "file": "loaded_judges.json",
            "description": "Judge configurations loaded"
        },
        {
            "name": "Conversation Generation",
            "icon": "💬",
            "complete": os.path.exists(f"{data_dir}/conversations_completed.flag"),
            "file": "conversations/",
            "description": "Model responses generated"
        },
        {
            "name": "Tournament Execution",
            "icon": "🏆",
            "complete": "tournament_summaries" in data["available_data"],
            "file": "tournament_summaries.json",
            "description": "Head-to-head competitions"
        },
        {
            "name": "Skill Rating Calculation", 
            "icon": "📈",
            "complete": "skill_ratings" in data["available_data"],
            "file": "skill_ratings.json",
            "description": "OpenSkill ratings computed"
        }
    ]

    # Display stages in a grid
    cols = st.columns(3)
    for i, stage in enumerate(stages):
        with cols[i % 3]:
            status_icon = "✅" if stage["complete"] else "⏳"
            status_color = "green" if stage["complete"] else "orange"
            
            st.markdown(f"""
            <div style="
                border: 2px solid {status_color};
                border-radius: 10px;
                padding: 15px;
                margin: 10px 0;
                background-color: {'#f0f8f0' if stage['complete'] else '#fff8f0'};
            ">
                <h4>{status_icon} {stage['icon']} {stage['name']}</h4>
                <p style="margin: 5px 0; color: #666;">{stage['description']}</p>
                <small style="font-family: monospace; background: #f5f5f5; padding: 2px 4px; border-radius: 3px;">
                    {stage['file']}
                </small>
            </div>
            """, unsafe_allow_html=True)

    # Detailed Progress Metrics
    st.subheader("📋 Detailed Progress")

    # Conversation Generation Progress
    if "models" in data["available_data"] and "skills" in data["available_data"]:
        model_count = len(data["models"]["models"])
        eval_count = len(data["skills"]["evals"])
        expected_conversations = model_count * eval_count

        # Count actual conversation files
        conversation_pattern = f"{data_dir}/conversations/*/*.json"
        actual_conversations = len(glob.glob(conversation_pattern))

        progress_pct = (actual_conversations / expected_conversations * 100) if expected_conversations > 0 else 0
        
        st.metric(
            "Conversation Files",
            f"{actual_conversations:,} / {expected_conversations:,}",
            f"{progress_pct:.1f}% complete"
        )

        # Progress bar (clamp to 0-1 range)
        progress_value = min(1.0, max(0.0, actual_conversations / expected_conversations)) if expected_conversations > 0 else 0.0
        st.progress(progress_value)

    # Model completion tracking
    if "models" in data["available_data"]:
        model_count = len(data["models"]["models"])
        completion_flags = glob.glob(f"{data_dir}/model_conversations_*.completed")
        completed_models = len(completion_flags)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Models Completed", f"{completed_models} / {model_count}")
        with col2:
            completion_pct = (completed_models / model_count * 100) if model_count > 0 else 0
            st.metric("Completion Rate", f"{completion_pct:.1f}%")

    # Skill-level progress
    if "skills" in data["available_data"]:
        st.subheader("🎯 Progress by Skill")
        
        skill_progress = []
        for skill_name, skill_info in data["skills"]["skills"].items():
            # Count conversations for this skill
            skill_conversations = len(glob.glob(f"{data_dir}/conversations/{skill_name}/*.json"))
            expected_skill_conversations = len(data["models"]["models"]) * skill_info["eval_count"] if "models" in data["available_data"] else skill_info["eval_count"]
            
            # Check if tournaments exist
            has_tournaments = "tournament_summaries" in data["available_data"] and skill_name in data.get("validated_tournaments", {})
            
            # Check for judge cache
            judge_cache_files = len(glob.glob(f"{data_dir}/judge_cache/{skill_name}/*.json"))
            
            skill_progress.append({
                "Skill": skill_name.replace("_", " ").title(),
                "Conversations": f"{skill_conversations:,} / {expected_skill_conversations:,}",
                "Tournament": "✅ Complete" if has_tournaments else "⏳ Pending", 
                "Judge Decisions": f"{judge_cache_files:,} cached"
            })

        if skill_progress:
            import pandas as pd
            progress_df = pd.DataFrame(skill_progress)
            st.dataframe(progress_df, use_container_width=True)

    # File System Overview
    st.subheader("📁 File System Status")
    
    # Data directory size and file counts
    try:
        import subprocess
        result = subprocess.run(['du', '-sh', data_dir], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            dir_size = result.stdout.split()[0]
            st.metric("Data Directory Size", dir_size)
    except:
        pass

    # Recent activity
    st.subheader("🕐 Recent Activity")
    
    recent_files = []
    for pattern in ["*.json", "conversations/*/*.json", "judge_cache/*/*.json", "*.completed"]:
        files = glob.glob(f"{data_dir}/{pattern}")
        for file_path in files:
            try:
                mtime = os.path.getmtime(file_path)
                recent_files.append((file_path, mtime))
            except:
                continue
    
    # Sort by modification time and show most recent 10
    recent_files.sort(key=lambda x: x[1], reverse=True)
    
    if recent_files:
        st.write("**Most Recently Modified Files:**")
        for file_path, mtime in recent_files[:10]:
            relative_path = os.path.relpath(file_path, data_dir)
            mod_time = datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
            st.code(f"{mod_time} - {relative_path}")

    # Next Steps
    st.subheader("🚀 Next Steps")
    
    if not stages[0]["complete"]:  # Skills not loaded
        st.info("Run: `snakemake --profile profiles/quick data/quick/loaded_skills.json`")
    elif not stages[1]["complete"]:  # Models not loaded  
        st.info("Run: `snakemake --profile profiles/quick data/quick/loaded_models.json`")
    elif not stages[2]["complete"]:  # Judges not loaded
        st.info("Run: `snakemake --profile profiles/quick data/quick/loaded_judges.json`")
    elif not stages[3]["complete"]:  # Conversations not complete
        st.info("Run: `snakemake --profile profiles/quick generate_conversations`")
    elif not stages[4]["complete"]:  # Tournaments not complete
        st.info("Run: `snakemake --profile profiles/quick run_tournaments`") 
    elif not stages[5]["complete"]:  # Ratings not complete
        st.info("Run: `snakemake --profile profiles/quick calculate_ratings`")
    else:
        st.success("🎉 Pipeline complete! All stages finished.")


def show_tournaments_page(data):
    """Display tournament results and match analysis."""
    st.header("🏆 Tournaments")

    tournaments = data["tournament_summaries"].get("tournaments", {})
    ratings = data["skill_ratings"].get("skill_ratings", {})

    # Performance matrix heatmap
    st.subheader("📊 Model Performance Matrix")

    matrix_data = []
    skills = list(tournaments.keys())
    models = data["model_ids"]

    for model in models:
        row = {"Model": model}
        for skill in skills:
            skill_ratings = ratings.get(skill, {})
            rating = skill_ratings.get("ratings", {}).get(model, 1500)
            row[skill] = rating
        matrix_data.append(row)

    if matrix_data:
        matrix_df = pd.DataFrame(matrix_data)
        matrix_df = matrix_df.set_index("Model")

        fig = px.imshow(
            matrix_df.values,
            x=matrix_df.columns,
            y=matrix_df.index,
            color_continuous_scale="RdYlGn",
            aspect="auto",
            text_auto=".1f",
        )
        fig.update_layout(title="OpenSkill Ratings by Model and Skill")
        st.plotly_chart(fig, use_container_width=True)

    # Tournament navigation
    st.subheader("🎪 Tournament Details")

    selected_skill = st.selectbox("Select skill tournament:", list(tournaments.keys()))

    if selected_skill:
        tournament_data = tournaments[selected_skill]

        # Skill-level rankings (aggregate across all evaluations)
        st.subheader(f"🏅 {selected_skill} Rankings")
        rankings = tournament_data.get("model_rankings", [])
        if rankings:
            rankings_df = pd.DataFrame(rankings)
            st.dataframe(rankings_df, use_container_width=True)

        # Get evaluations for this skill
        skill_evals = [
            e
            for e in data["skills"]["evals"]
            if e.get("_metadata", {}).get("skill") == selected_skill
        ]

        if skill_evals:
            st.subheader("📋 Evaluations")
            eval_options = [f"{e['id']}: {e['name']}" for e in skill_evals]
            selected_eval = st.selectbox(
                "Select evaluation for match details:", eval_options
            )

            if selected_eval:
                eval_id = selected_eval.split(":")[0]
                eval_data = next((e for e in skill_evals if e["id"] == eval_id), None)

                if eval_data:
                    st.subheader(f"🎪 {eval_data['name']} Tournament")

                    # Show evaluation-specific info
                    with st.expander("Evaluation Configuration"):
                        st.json(eval_data)

                    # Match history for this specific evaluation
                    matches = tournament_data.get("match_history", [])

                    if matches:
                        # Create user-friendly match descriptions
                        match_options = []
                        for i, m in enumerate(matches, 1):
                            # Calculate round number (assuming sequential ordering)
                            round_num = (
                                ((i - 1) // (len(matches) // 2)) + 1
                                if len(matches) > 2
                                else 1
                            )
                            match_num = (
                                ((i - 1) % (len(matches) // 2)) + 1
                                if len(matches) > 2
                                else i
                            )

                            # Get model display names (remove org prefix for brevity)
                            model_a_short = (
                                m["model_a"].split("/")[-1]
                                if "/" in m["model_a"]
                                else m["model_a"]
                            )
                            model_b_short = (
                                m["model_b"].split("/")[-1]
                                if "/" in m["model_b"]
                                else m["model_b"]
                            )

                            match_options.append(
                                f"Round {round_num}, Match {match_num}: {model_a_short} vs {model_b_short}"
                            )

                        selected_match = st.selectbox(
                            "Select match for details:", match_options
                        )

                        if selected_match:
                            # Extract match index from selection
                            selected_index = match_options.index(selected_match)
                            match = matches[selected_index]
                            match_id = match["match_id"]

                            if match:
                                # Get winner info
                                winner = match.get("winner", "Unknown")
                                winner_text = {
                                    "A": f"Model A ({match['model_a'].split('/')[-1]})",
                                    "B": f"Model B ({match['model_b'].split('/')[-1]})",
                                    "TIE": "TIE",
                                }.get(winner, winner)

                                # Show vote counts if available
                                vote_counts = match.get("vote_counts", {})
                                vote_summary = (
                                    f" ({vote_counts.get('A', 0)}A-{vote_counts.get('B', 0)}B-{vote_counts.get('TIE', 0)}T)"
                                    if vote_counts
                                    else ""
                                )

                                st.subheader(f"🔍 Match {match_id}")
                                st.success(
                                    f"🏆 **Winner: {winner_text}**{vote_summary}"
                                )

                                # Use the selected evaluation ID
                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown(f"**Model A:** {match['model_a']}")
                                    conv_a = load_conversation_log(
                                        selected_skill,
                                        eval_id,
                                        match["model_a"],
                                        data["data_dir"],
                                    )
                                    if conv_a:
                                        with st.expander("Model A Conversation JSON"):
                                            st.json(conv_a)
                                    else:
                                        safe_model_a = (
                                            match["model_a"]
                                            .replace("/", "_")
                                            .replace(":", "_")
                                        )
                                        st.warning(
                                            f"Conversation log not found: {selected_skill}/{eval_id}_{safe_model_a}_*.json"
                                        )

                                with col2:
                                    st.markdown(f"**Model B:** {match['model_b']}")
                                    conv_b = load_conversation_log(
                                        selected_skill,
                                        eval_id,
                                        match["model_b"],
                                        data["data_dir"],
                                    )
                                    if conv_b:
                                        with st.expander("Model B Conversation JSON"):
                                            st.json(conv_b)
                                    else:
                                        safe_model_b = (
                                            match["model_b"]
                                            .replace("/", "_")
                                            .replace(":", "_")
                                        )
                                        st.warning(
                                            f"Conversation log not found: {selected_skill}/{eval_id}_{safe_model_b}_*.json"
                                        )

                                # Judge decisions
                                st.subheader("⚖️ Judge Decisions")

                                # Check for early consensus
                                judge_votes = []
                                for judge_entry in match.get("judges", []):
                                    vote = (
                                        judge_entry.get("vote", "Unknown")
                                        if isinstance(judge_entry, dict)
                                        else "Unknown"
                                    )
                                    if vote != "Unknown":
                                        judge_votes.append(vote)

                                is_early_consensus = (
                                    len(judge_votes) == 2
                                    and len(set(judge_votes)) == 1
                                    and judge_votes[0] in ["A", "B", "TIE"]
                                )

                                if is_early_consensus:
                                    st.info(
                                        f"🎯 **Early Consensus**: First 2 judges agreed on **{judge_votes[0]}** - 3rd judge skipped to save API costs"
                                    )

                                # Check if tournament directory exists for this skill
                                tournament_dir = (
                                    f"{data['data_dir']}/judge_cache/{selected_skill}"
                                )
                                if not os.path.exists(tournament_dir):
                                    st.info(
                                        f"💡 Detailed judge decisions not available for {selected_skill}. Tournament decision files have not been generated yet."
                                    )

                                    # Show vote summary from match data instead
                                    st.write("**Vote Summary:**")
                                    for judge_entry in match.get("judges", []):
                                        judge_id = (
                                            judge_entry.get("judge_id")
                                            if isinstance(judge_entry, dict)
                                            else judge_entry
                                        )
                                        vote = (
                                            judge_entry.get("vote", "Unknown")
                                            if isinstance(judge_entry, dict)
                                            else "Unknown"
                                        )
                                        st.write(f"- **{judge_id}**: {vote}")
                                else:
                                    # Load detailed judge decisions
                                    for judge_entry in match.get("judges", []):
                                        judge_id = (
                                            judge_entry.get("judge_id")
                                            if isinstance(judge_entry, dict)
                                            else judge_entry
                                        )
                                        vote = (
                                            judge_entry.get("vote", "Unknown")
                                            if isinstance(judge_entry, dict)
                                            else "Unknown"
                                        )

                                        judge_decision = load_judge_decision(
                                            selected_skill,
                                            match_id,
                                            judge_id,
                                            data["data_dir"],
                                        )
                                        if judge_decision:
                                            with st.expander(
                                                f"Judge: {judge_id} (Vote: {vote})"
                                            ):
                                                st.json(judge_decision)
                                        else:
                                            st.write(
                                                f"**{judge_id}**: {vote} *(Decision details not found)*"
                                            )


def main():
    st.title("🏆 AFBench Admin UI")

    # Clear cache on startup to ensure fresh data
    if "cache_cleared" not in st.session_state:
        load_available_data.clear()
        st.session_state.cache_cleared = True

    # Load available data
    data = load_available_data()

    # Show data directory and status
    st.sidebar.info(f"📁 Data Directory: `{data['data_dir']}`")

    # Show what data is available vs missing
    if data["available_data"]:
        st.sidebar.success(f"✅ Available: {', '.join(sorted(data['available_data']))}")

    if data["missing_data"]:
        st.sidebar.warning(f"⚠️ Missing: {', '.join(sorted(data['missing_data']))}")

        # Show helpful messages about missing data
        if "skills" in data["missing_data"]:
            st.sidebar.info(
                "💡 Run `snakemake --profile profiles/quick data/quick/loaded_skills.json` to load skills"
            )
        if "models" in data["missing_data"]:
            st.sidebar.info(
                "💡 Run `snakemake --profile profiles/quick data/quick/loaded_models.json` to load models"
            )
        if "skill_ratings" in data["missing_data"]:
            st.sidebar.info("💡 Run `./run_all.sh` to generate complete results")

    # Show data freshness in sidebar if we have ratings data
    if "skill_ratings" in data:
        show_data_freshness_sidebar(data)

    # Determine available pages based on data
    all_pages = {
        "📊 Progress": (None, show_progress_page),  # Always available
        "🤖 Models": ("models", show_models_page),
        "⚖️ Judges": ("judges", show_judges_page),
        "🎯 Skills": ("skills", show_skills_page),
        "🏆 Tournaments": ("skill_ratings", show_tournaments_page),
    }

    # Only show pages for which we have data (Progress is always available)
    available_pages = {
        name: page_func
        for name, (required_data, page_func) in all_pages.items()
        if required_data is None or required_data in data["available_data"]
    }

    if not available_pages:
        st.error("🚫 No data available to display.")
        st.info("📋 Please run the AFBench pipeline first:")
        st.code("./run_all.sh", language="bash")
        return

    # Navigation
    selected_page = st.sidebar.selectbox("Navigate to:", list(available_pages.keys()))

    # Show selected page
    available_pages[selected_page](data)


if __name__ == "__main__":
    main()
