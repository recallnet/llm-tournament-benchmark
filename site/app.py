import glob
import json
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="AFBench Admin UI", page_icon="🏆", layout="wide", initial_sidebar_state="expanded")


@st.cache_data(ttl=300)
def load_validated_tournament_data():
    """Load tournament data with data integrity validation."""
    # Use environment variable for data directory, with fallback safety check
    data_dir_env = os.getenv("AFBENCH_ADMIN_DATA_DIR")
    if not data_dir_env:
        raise ValueError(
            "🚨 SAFETY: Admin UI requires AFBENCH_ADMIN_DATA_DIR environment variable.\n"
            "Use ./run.sh or set AFBENCH_ADMIN_DATA_DIR=data/quick"
        )
    data_dir = data_dir_env

    # Step 1: Load authoritative skill ratings
    try:
        with open(f"{data_dir}/skill_ratings.json") as f:
            ratings_data = json.load(f)
    except FileNotFoundError:
        st.error("skill_ratings.json not found - pipeline may not have run")
        return None

    valid_skills = set(ratings_data["skill_ratings"].keys())
    current_cache_key = ratings_data["execution_info"]["cache_key"]

    # Step 2: Load tournament summaries
    try:
        with open(f"{data_dir}/tournament_summaries.json") as f:
            tournaments_data = json.load(f)
    except FileNotFoundError:
        st.error("tournament_summaries.json not found")
        return None

    validated_tournaments = {skill: data for skill, data in tournaments_data["tournaments"].items() if skill in valid_skills}

    # Step 3: Load metadata files
    files_to_load = {
        "models": f"{data_dir}/loaded_models.json",
        "judges": f"{data_dir}/loaded_judges.json",
        "skills": f"{data_dir}/loaded_skills.json",
    }

    loaded_data = {}
    for key, filepath in files_to_load.items():
        try:
            with open(filepath) as f:
                loaded_data[key] = json.load(f)
        except FileNotFoundError:
            st.error(f"{filepath} not found")
            return None

    # Step 4: Extract IDs for validation
    model_ids = {m["id"] for m in loaded_data["models"]["models"]}
    judge_ids = {j["id"] for j in loaded_data["judges"]["judges"]}
    eval_ids = {e["id"] for e in loaded_data["skills"]["evals"]}

    return {
        "valid_skills": valid_skills,
        "cache_key": current_cache_key,
        "models": loaded_data["models"],
        "judges": loaded_data["judges"],
        "skills": loaded_data["skills"],
        "tournaments": validated_tournaments,
        "ratings": ratings_data["skill_ratings"],
        "execution_info": ratings_data["execution_info"],
        "model_ids": model_ids,
        "judge_ids": judge_ids,
        "eval_ids": eval_ids,
    }


@st.cache_data(ttl=60)
def load_conversation_log(skill: str, eval_id: str, model_id: str):
    """Load individual conversation log with hash validation."""
    pattern = f"data/conversations/{skill}/{eval_id}_{model_id}_*.json"
    matches = glob.glob(pattern)
    if not matches:
        return None

    latest_file = max(matches, key=os.path.getmtime)
    try:
        with open(latest_file) as f:
            return json.load(f)
    except:
        return None


@st.cache_data(ttl=60)
def load_judge_decision(skill: str, match_id: str, judge_id: str):
    """Load individual judge decision with hash validation."""
    # Use environment variable for data directory
    data_dir_env = os.getenv("AFBENCH_ADMIN_DATA_DIR")
    if not data_dir_env:
        raise ValueError("🚨 SAFETY: Admin UI requires AFBENCH_ADMIN_DATA_DIR environment variable.")
    pattern = f"{data_dir_env}/judge_cache/{skill}/{match_id}_{judge_id}_*.json"
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

    st.sidebar.info(f"🔑 Cache: {data['cache_key'][:8]}...")

    timestamp = data["execution_info"].get("timestamp")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            st.sidebar.info(f"🕐 Updated: {dt.strftime('%H:%M:%S')}")
        except:
            st.sidebar.info(f"🕐 Updated: {timestamp}")


def show_models_page(data):
    """Display models overview and details."""
    st.header("🤖 Models")

    models = data["models"]["models"]
    tournaments = data["tournaments"]
    ratings = data["ratings"]

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
        best_rating = float("-inf")  # Start with negative infinity so first rating becomes best
        worst_rating = float("inf")

        for skill, tournament_data in tournaments.items():
            if model_id in [r["model_id"] for r in tournament_data.get("model_rankings", [])]:
                skills_participated += 1
                total_matches += tournament_data.get("total_matches", 0) // len(tournament_data.get("model_rankings", [1]))

                # Find this model's ranking
                for ranking in tournament_data.get("model_rankings", []):
                    if ranking["model_id"] == model_id:
                        wins = ranking.get("wins", 0)
                        total_wins += wins

                        # Get rating for this skill
                        skill_ratings = ratings.get(skill, {})
                        model_rating = skill_ratings.get("model_ratings", {}).get(model_id, {}).get("mu", 1500)

                        if model_rating > best_rating:
                            best_rating = model_rating
                            best_skill = skill
                        if model_rating < worst_rating:
                            worst_rating = model_rating
                            worst_skill = skill
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
                "Best Skill": best_skill or "None",
                "Worst Skill": worst_skill or "None",
            }
        )

    df = pd.DataFrame(model_stats)
    st.dataframe(df, use_container_width=True)

    # Model selection for detail view
    selected_model = st.selectbox("Select model for details:", [m["Model ID"] for m in model_stats])

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
                        "Rank": tournament_stats.get("rank", "N/A") if tournament_stats else "N/A",
                        "Wins": tournament_stats.get("wins", 0) if tournament_stats else 0,
                        "Losses": tournament_stats.get("losses", 0) if tournament_stats else 0,
                        "Ties": tournament_stats.get("ties", 0) if tournament_stats else 0,
                    }
                )

        if skill_performance:
            perf_df = pd.DataFrame(skill_performance)
            st.dataframe(perf_df, use_container_width=True)


def show_judges_page(data):
    """Display judges overview and details."""
    st.header("⚖️ Judges")

    judges = data["judges"]["judges"]
    tournaments = data["tournaments"]

    # Create judges overview table
    judge_stats = []
    for judge in judges:
        judge_id = judge["id"]

        total_decisions = 0
        for skill, tournament_data in tournaments.items():
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


def show_skills_page(data):
    """Display skills overview and evaluation details."""
    st.header("🎯 Skills")

    skills_data = data["skills"]["skills"]
    tournaments = data["tournaments"]

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

        skill_evals = [e for e in data["skills"]["evals"] if e.get("_metadata", {}).get("skill") == selected_skill]

        eval_table = []
        for eval_data in skill_evals:
            eval_table.append(
                {
                    "ID": eval_data["id"],
                    "Name": eval_data["name"],
                    "Type": "Multi-step" if len(eval_data.get("chain", [])) > 1 else "Single-step",
                }
            )

        if eval_table:
            eval_df = pd.DataFrame(eval_table)
            st.dataframe(eval_df, use_container_width=True)

            # Evaluation detail
            selected_eval = st.selectbox("Select evaluation for JSON:", [e["ID"] for e in eval_table])

            if selected_eval:
                eval_json = next((e for e in skill_evals if e["id"] == selected_eval), None)
                if eval_json:
                    st.subheader(f"📄 {selected_eval} Configuration")
                    st.json(eval_json)


def show_tournaments_page(data):
    """Display tournament results and match analysis."""
    st.header("🏆 Tournaments")

    tournaments = data["tournaments"]
    ratings = data["ratings"]

    # Performance matrix heatmap
    st.subheader("📊 Model Performance Matrix")

    matrix_data = []
    skills = list(tournaments.keys())
    models = data["model_ids"]

    for model in models:
        row = {"Model": model}
        for skill in skills:
            skill_ratings = ratings.get(skill, {})
            rating = skill_ratings.get("model_ratings", {}).get(model, {}).get("mu", 1500)
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

        # Rankings table
        st.subheader(f"🏅 {selected_skill} Rankings")
        rankings = tournament_data.get("model_rankings", [])
        if rankings:
            rankings_df = pd.DataFrame(rankings)
            st.dataframe(rankings_df, use_container_width=True)

        # Match history
        st.subheader("📜 Match History")
        matches = tournament_data.get("match_history", [])

        if matches:
            selected_match = st.selectbox(
                "Select match for details:", [f"{m['match_id']}: {m['model_a']} vs {m['model_b']}" for m in matches]
            )

            if selected_match:
                match_id = selected_match.split(":")[0]
                match = next((m for m in matches if m["match_id"] == match_id), None)

                if match:
                    st.subheader(f"🔍 Match {match_id}")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown(f"**Model A:** {match['model_a']}")
                        conv_a = load_conversation_log(selected_skill, match.get("eval_id", ""), match["model_a"])
                        if conv_a:
                            with st.expander("Model A Conversation JSON"):
                                st.json(conv_a)
                        else:
                            st.warning("Conversation log not found")

                    with col2:
                        st.markdown(f"**Model B:** {match['model_b']}")
                        conv_b = load_conversation_log(selected_skill, match.get("eval_id", ""), match["model_b"])
                        if conv_b:
                            with st.expander("Model B Conversation JSON"):
                                st.json(conv_b)
                        else:
                            st.warning("Conversation log not found")

                    # Judge decisions
                    st.subheader("⚖️ Judge Decisions")

                    # Check for early consensus (2 judges with same vote)
                    judge_votes = []
                    for judge_id in match.get("judges", []):
                        judge_decision = load_judge_decision(selected_skill, match_id, judge_id)
                        if judge_decision and "vote" in judge_decision:
                            judge_votes.append(judge_decision["vote"])

                    is_early_consensus = (
                        len(judge_votes) == 2 and len(set(judge_votes)) == 1 and judge_votes[0] in ["A", "B", "TIE"]
                    )

                    if is_early_consensus:
                        st.info(f"🎯 **Early Consensus**: First 2 judges agreed on **{judge_votes[0]}** - 3rd judge skipped")

                    for judge_id in match.get("judges", []):
                        judge_decision = load_judge_decision(selected_skill, match_id, judge_id)
                        if judge_decision:
                            with st.expander(f"Judge: {judge_id}"):
                                st.json(judge_decision)
                        else:
                            st.warning(f"Judge decision not found for {judge_id}")


def main():
    st.title("🏆 AFBench Admin UI")

    # Add cache clear button in sidebar
    if st.sidebar.button("🔄 Clear Cache"):
        load_validated_tournament_data.clear()
        st.rerun()

    # Load and validate data
    data = load_validated_tournament_data()

    if not data:
        st.error("Failed to load tournament data. Check that the pipeline has run successfully.")
        return

    # Show data freshness in sidebar
    show_data_freshness_sidebar(data)

    # Navigation
    pages = {
        "🤖 Models": show_models_page,
        "⚖️ Judges": show_judges_page,
        "🎯 Skills": show_skills_page,
        "🏆 Tournaments": show_tournaments_page,
    }

    selected_page = st.sidebar.selectbox("Navigate to:", list(pages.keys()))

    # Show selected page
    pages[selected_page](data)


if __name__ == "__main__":
    main()
